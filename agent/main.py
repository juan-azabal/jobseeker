"""
JobAgent - Phase 2: Scrape -> Pre-filter -> Parse -> RAG Score -> Rank

Usage:
  python main.py              # normal run (uses cache for already-processed jobs)
  python main.py --no-score   # skip RAG scoring, heuristic only (fast)
  python main.py --refresh    # clear cache, reprocess everything from scratch
  python main.py --rescore    # keep parsed data, redo all RAG scores (e.g. after rubric change)
"""

import json
import os
import re
import sys
import time
from datetime import datetime

import httpx

import structlog

from logging_setup import configure_logging
from models import RawJob
from merger import merge_jobs
from scraper import run_scraper
from ats_scraper import run_watchlist_scraper
from wttj_scraper import run_wttj_scraper
from prefilter import prefilter_jobs
from parser import parse_all
from jobcache import load_cache, save_cache, split_by_cache, update_cache, cache_stats
from user_config import load_profile, list_profiles, is_profile_active, resolve_profile_paths, compute_seniority_weights

configure_logging()
logger = structlog.get_logger("agent.main")


def _to_dicts(jobs: list[RawJob]) -> list[dict]:
    """Convert list[RawJob] → list[dict] for downstream pipeline compatibility.

    Temporary shim while prefilter/parser/scorer still consume plain dicts.
    Uses model_dump() which includes the computed is_remote field.
    Phase 2 will replace this with a proper merge step.
    """
    result = []
    for j in jobs:
        d = j.model_dump()
        # Ensure is_remote is included as a plain bool (computed field)
        d["is_remote"] = j.is_remote
        result.append(d)
    return result


_ph_client = None  # module-level Posthog singleton; created on first use


def _capture(profile_id: str, event: str, props: dict) -> None:
    """Fire a PostHog server-side event. No-op when POSTHOG_API_KEY is absent.

    Uses Posthog class directly (not the deprecated module-level proxy) so the
    client is created with explicit credentials and not reliant on setup().
    """
    global _ph_client
    key = os.environ.get("POSTHOG_API_KEY")
    if not key:
        return
    try:
        if _ph_client is None:
            from posthog import Posthog  # noqa: PLC0415

            host = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
            _ph_client = Posthog(key, host=host)
            # Also configure the module-level proxy so that posthog.ai wrappers
            # (used in parser.py / scorer.py) can find posthog.default_client.
            # Uses the deprecated proxy setter — intentional, no better alternative.
            try:
                import posthog as _phm  # noqa: PLC0415

                _phm.api_key = key
                _phm.host = host
            except Exception:
                pass
        _ph_client.capture(profile_id, event, props)
    except Exception:
        pass


SEEN_IDS_PATH = "config/seen_ids/juan.txt"  # fallback only; main() always passes profile-derived path

# Hard cap on RAG scoring per profile per run (ADR-006 safety net).
# The heuristic gate is the primary cost control; this cap is a backstop.
MAX_SCORE_PER_RUN = 50


def _heuristic_gate(jobs: list, profile: dict) -> tuple[list, list]:
    """Split parsed jobs into (to_score, skipped) using a cheap heuristic.

    Jobs that clearly don't fit (wrong domain, wrong seniority, no skill
    overlap, too low salary) skip LLM scoring and remain as heuristic-only
    results in the digest (ADR-006).

    Returns (jobs_to_score, jobs_skipped).
    """
    scoring_cfg = profile.get("scoring", {})
    threshold = scoring_cfg.get("rag_threshold", 0)
    salary_min = scoring_cfg.get("salary_min", 0)

    if threshold == 0:
        return jobs, []

    target = profile.get("target", {})
    target_domains = target.get("domains") or {}  # dict: domain → weight (may be negative)
    target_level = (target.get("level") or "").lower()
    profile_skills = {s.lower().replace("-", " ") for s in (profile.get("skills") or [])}

    # Seniority levels that map to senior IC / management
    PRINCIPAL_WORDS = {"principal", "staff", "director", "vp", "head", "chief"}
    SENIOR_WORDS = {"senior", "lead", "sr"}

    to_score, skipped = [], []

    for job in jobs:
        parsed = job.get("parsed") or {}
        score = 0

        # ── Domain (0–20) ─────────────────────────────────────────────────
        domain = (parsed.get("domain") or "").lower()
        if not domain or domain == "other":
            score += 10  # uncertain → partial credit
        else:
            domain_weight = target_domains.get(domain, 0)
            if domain_weight > 0:
                score += 20  # desired domain → full credit
            elif domain_weight < 0:
                score += 0  # explicitly deprioritized → no credit in gate
            # else: domain not in target_domains → 0 (unchanged)

        # ── Seniority (0–20) ──────────────────────────────────────────────
        seniority = (parsed.get("seniority") or "").lower()
        if not seniority:
            score += 10  # unspecified → partial credit
        elif target_level in ("principal", "staff"):
            if any(w in seniority for w in PRINCIPAL_WORDS):
                score += 20
            elif any(w in seniority for w in SENIOR_WORDS):
                score += 10
        elif target_level in ("senior", "lead"):
            if any(w in seniority for w in SENIOR_WORDS | PRINCIPAL_WORDS):
                score += 20
        else:
            score += 10  # no target level → partial credit

        # ── Skill overlap (0–20, 5 pts/match, cap 4) ──────────────────────
        job_skills = [
            s.lower().replace("-", " ")
            for s in (parsed.get("must_have_skills") or []) + (parsed.get("nice_to_have_skills") or [])
        ]
        matches = sum(1 for js in job_skills if any(ps in js or js in ps for ps in profile_skills))
        score += min(20, matches * 5)

        # ── Salary gate (hard block, applied after score) ─────────────────
        if salary_min > 0:
            salary_text = (parsed.get("salary_mentioned") or "").lower()
            nums = re.findall(r"[\d,]+", salary_text)
            if nums:
                try:
                    val = int(nums[0].replace(",", ""))
                    # Treat values under 1000 as "k" (e.g. "80k")
                    if val < 1000:
                        val *= 1000
                    if val < salary_min:
                        skipped.append(job)
                        continue
                except ValueError:
                    pass

        (to_score if score >= threshold else skipped).append(job)

    return to_score, skipped


def _sync_to_railway(jobs: list, profile_id: str, railway_url: str, ingest_key: str) -> bool:
    """POST jobs to /api/ingest on Railway so the digest endpoint has today's data.

    Called as Step 10b, before the email digest (Step 11), to ensure Railway DB
    is populated before GET /api/digest/{profile_id} is called.

    Returns True on success, False on any failure (caller continues regardless).
    """
    url = railway_url.rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    endpoint = f"{url}/api/ingest"
    payload = {"jobs": jobs, "profile_id": profile_id}

    try:
        resp = httpx.post(
            endpoint,
            json=payload,
            headers={"X-Ingest-Key": ingest_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        logger.info("railway_sync_ok", profile_id=profile_id, jobs=len(jobs), status=resp.status_code)
        print(f"   Railway sync: {len(jobs)} jobs → {resp.status_code}")
        return True
    except httpx.TimeoutException as exc:
        logger.warning("railway_sync_timeout", profile_id=profile_id, error=str(exc))
        print("⚠  Railway sync timeout — email digest may have stale data")
        return False
    except Exception as exc:
        logger.warning("railway_sync_failed", profile_id=profile_id, error=str(exc))
        print(f"⚠  Railway sync failed ({exc}) — email digest may have stale data")
        return False


def _append_seen_ids(jobs, path=SEEN_IDS_PATH):
    """Append job IDs from this run to seen_ids.txt so future runs skip them."""
    # Load existing IDs to avoid duplicates
    existing = set()
    if os.path.exists(path):
        with open(path, "r") as f:
            existing = {line.strip() for line in f if line.strip()}

    new_ids = [job["id"] for job in jobs if job.get("id") and job["id"] not in existing]
    if not new_ids:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for job_id in new_ids:
            f.write(job_id + "\n")

    print(f"   Seen IDs: +{len(new_ids)} appended to {path} ({len(existing) + len(new_ids)} total)")


def save_results(jobs, folder="output", profile_id=None):
    """Save results to JSON for later phases.

    Output format v2: ``{"_metadata": {...}, "jobs": [...]}``
    The metadata envelope embeds profile_id so the GHA sync step can
    attribute results to the correct user during cron (all-profiles) runs.
    """
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(folder, f"jobs_{timestamp}.json")

    clean_jobs = []
    for job in jobs:
        clean = {}
        for k, v in job.items():
            if k.startswith("_"):
                continue  # skip internal fields
            if v != v:  # NaN check
                clean[k] = None
            else:
                clean[k] = v
        # Persist heuristic score so downstream consumers (e.g. jobseeker ingest)
        # can use it as fallback when rag_score is absent.
        if "_fit_score" in job:
            clean["fit_score"] = job["_fit_score"]
        clean_jobs.append(clean)

    output = {
        "_metadata": {
            "profile_id": profile_id,
            "timestamp": timestamp,
            "version": "2",
        },
        "jobs": clean_jobs,
    }

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n>> Results saved to {filepath}")
    return filepath


# --- Grade-to-points conversion (delegates to shared/scoring_core) ---
from shared.scoring_core import grade_to_points as _grade_to_points  # noqa: E402  (backward-compat alias for notifier.py)


# --- Heuristic ranking (no API calls) ---
# Values loaded from user profile at runtime — see config/profiles/<id>.yaml

_PROFILE_SKILLS = None  # populated by _load_heuristic_config()
_DOMAIN_SCORES = None
_SENIORITY_SCORES = None
_SALARY_THRESHOLD = 130000
_HOME_LOCATIONS = []
_HOME_REGIONS = []  # auto-derived from home_locations via country-converter
_HOME_REGION_RE = None  # compiled regex for word-boundary region matching
_COUNTRY_WEIGHTS: dict = {}  # populated by _load_heuristic_config(); e.g. {"remote": 10, "netherlands": -10}
_LOCATION_PREFERENCE: str = "b"  # populated by _load_heuristic_config()



def _load_heuristic_config(profile: dict):
    """Populate module-level heuristic constants from user profile."""
    from geo import derive_home_regions, build_region_pattern

    global _PROFILE_SKILLS, _DOMAIN_SCORES, _SENIORITY_SCORES
    global _SALARY_THRESHOLD, _HOME_LOCATIONS, _HOME_REGIONS, _HOME_REGION_RE
    global _COUNTRY_WEIGHTS, _LOCATION_PREFERENCE
    _PROFILE_SKILLS = [s.lower() for s in (profile.get("skills") or [])]
    _DOMAIN_SCORES = {k.lower(): v for k, v in (profile.get("target", {}).get("domains") or {}).items()}
    # 3-tier fallback: seniority_weights (current) > seniority (legacy) > compute from level+track
    target = profile.get("target", {})
    stored_sw = target.get("seniority_weights") or target.get("seniority")
    if stored_sw:
        _SENIORITY_SCORES = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        _SENIORITY_SCORES = compute_seniority_weights(target.get("level", ""), target.get("track", "ic"))
    _SALARY_THRESHOLD = profile.get("target", {}).get("salary_display_threshold", 130000)
    _HOME_LOCATIONS = [loc.lower() for loc in (profile.get("user", {}).get("home_locations") or [])]
    _HOME_REGIONS = derive_home_regions(_HOME_LOCATIONS)
    _HOME_REGION_RE = build_region_pattern(_HOME_REGIONS)
    _COUNTRY_WEIGHTS = {k.lower(): int(v) for k, v in (target.get("country_weights") or {}).items()}
    _LOCATION_PREFERENCE = (profile.get("user", {}).get("location_preference") or "b").lower()


# Domain data — single source of truth now in shared/scoring_core.
from shared.scoring_core import (  # noqa: E402
    DOMAIN_KEYWORDS as _DOMAIN_KEYWORDS,
    DOMAIN_ALIASES as _DOMAIN_ALIASES,
    infer_domain as _infer_domain,
    compute_eligibility_penalty as _shared_eligibility_penalty,
    heuristic_score as _shared_heuristic_score,
)


def _heuristic_score(job):
    """Quick fit score 0-100 from parsed data. No API calls.

    Delegates to shared/scoring_core.heuristic_score() with:
      - Agent-specific skill scoring: simple keyword overlap (matches * 4, cap 30)
      - Profile dict built from module-level globals set by _load_heuristic_config()
    """
    p = job.get("parsed")
    if not p:
        return 0

    # Agent-specific skill scoring — simple overlap, not semantic (matches * 4, cap 30)
    all_text = " ".join(
        [s.lower() for s in p.get("must_have_skills", [])]
        + [s.lower() for s in p.get("nice_to_have_skills", [])]
        + [s.lower() for s in p.get("technical_stack", [])]
        + [p.get("responsibilities_summary", "").lower()]
    )
    matches = sum(1 for skill in (_PROFILE_SKILLS or []) if skill in all_text)
    skill_score = min(30, matches * 4)

    # Update parsed domain for display (infer_domain may refine "other")
    p["domain"] = _infer_domain(p)

    profile = {
        "domains": _DOMAIN_SCORES or {},
        "seniority": _SENIORITY_SCORES or {},
        "home_locations": _HOME_LOCATIONS,
        "home_regions": _HOME_REGIONS,
        "location_preference": _LOCATION_PREFERENCE,
        "country_weights": _COUNTRY_WEIGHTS,
    }
    return _shared_heuristic_score(profile, p, job, skill_score=skill_score)


# --- Currency / salary extraction (agent/salary.py) ---

from salary import extract_max_salary_eur as _extract_max_salary_eur  # noqa: E402


# --- Display ---


def _is_remote_requiring_reloc(job, home_locations=None, home_regions=None, region_pattern=None):
    """Return True if a remote job pins the worker to a place outside home.

    Checks three signals (title, location, restriction) against the user's
    home_locations and home_regions (auto-derived via country-converter).
    A remote job is reloc-free only if:
      1. The user's home location explicitly appears in the combined text, OR
      2. The user's home region appears (word-boundary safe via regex), OR
      3. A universal term appears (worldwide, global, anywhere), OR
      4. There is NO country/city pinning at all (truly global remote).
    Everything else counts as relocation.
    """
    from geo import matches_region, UNIVERSAL_TERMS, build_region_pattern

    home_locs = home_locations if home_locations is not None else _HOME_LOCATIONS
    re_pattern = region_pattern if region_pattern is not None else _HOME_REGION_RE
    # Build pattern on the fly if caller passed regions list but no compiled pattern
    if re_pattern is None and home_regions:
        re_pattern = build_region_pattern(home_regions)

    p = job.get("parsed") or {}
    title_lower = (job.get("title") or "").lower()
    job_loc = (job.get("location") or "").lower()
    restriction = (p.get("remote_restriction") or "").lower()
    if restriction in ("null", "none"):
        restriction = ""

    combined = f"{title_lower} {job_loc} {restriction}"

    # 1. User's home is mentioned → accessible, not reloc
    if home_locs and any(home in combined for home in home_locs):
        return False

    # 2. User's home region is mentioned (word-boundary regex) → not reloc
    if matches_region(combined, re_pattern):
        return False

    # 3. Universally inclusive → not reloc
    if any(term in combined for term in UNIVERSAL_TERMS):
        return False

    # 4. "Remote from X" pattern in title → country-pinned → reloc
    if re.search(r"remote from \w", title_lower):
        return True

    # 5. Location is "SomePlace (remote)" → country-pinned → reloc
    if "(remote)" in job_loc and job_loc.replace("(remote)", "").strip():
        return True

    # 6. Restriction names a specific place (not just a timezone)
    if restriction:
        from geo import is_pure_timezone

        if not is_pure_timezone(restriction):
            return True

    # 7. No signals → truly global remote → not reloc
    return False


def _is_reloc(job):
    """Return True if role requires relocating.

    Remote jobs: checks restriction/title/location for country pinning.
    Non-remote: checks if the job location matches user's home locations.
    """
    p = job.get("parsed") or {}
    loc_type = p.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    if loc_type == "remote":
        return _is_remote_requiring_reloc(job)
    if any(c in job_loc for c in _HOME_LOCATIONS):
        return False
    return True


def _sort_key(j):
    """Sort: no-reloc first, then reloc. Within each group: salary desc, then score desc."""
    reloc = 1 if _is_reloc(j) else 0
    salary = j["_salary_eur"]
    score = j["_display_score"]
    return (reloc, -salary, -score)


def _print_job(i, job):
    p = job["parsed"]
    seniority = p.get("seniority", "?")
    domain = p.get("domain", "?")
    location_type = p.get("location_type", "?")
    salary_eur = job["_salary_eur"]
    score = job["_display_score"]
    rag = job.get("rag_score")

    salary_display = f"~EUR {int(salary_eur / 1000)}K" if salary_eur > 0 else "no salary"
    score_label = f"rag:{score}" if rag else f"fit:{score}"

    if salary_eur >= _SALARY_THRESHOLD:
        indicator = "[+++]"
    elif salary_eur >= 80000:
        indicator = "[++ ]"
    elif salary_eur > 0:
        indicator = "[+  ]"
    elif score >= 70:
        indicator = "[ **]"
    elif score >= 50:
        indicator = "[ * ]"
    else:
        indicator = "[ . ]"

    print(f"\n{indicator} {i}. {job['title']} @ {job['company']}")
    print(
        f"   {job.get('location', '?')} ({location_type}) | {seniority} | {domain} | {salary_display} | {score_label}"
    )

    if rag:
        verdict = rag.get("one_line_verdict", "")
        if verdict:
            print(f"   {verdict}")
        stories = rag.get("stories_to_prepare") or []
        deal_breakers = rag.get("deal_breakers") or []
        parts = []
        if stories:
            parts.append(f"Stories: {', '.join(stories)}")
        if deal_breakers:
            parts.append(f"⚠ {deal_breakers[0]}")
        if parts:
            print(f"   {' | '.join(parts)}")
    else:
        must_have = (p.get("must_have_skills") or [])[:3]
        red_flags = p.get("red_flags") or []
        if must_have:
            print(f"   Must have: {', '.join(must_have)}")
        if red_flags:
            print(f"   ⚠ {red_flags[0]}")

    print(f"   {job.get('job_url', 'N/A')}")


def ranked_jobs(jobs):
    """Return jobs sorted into digest order (tier A→B→C, then by location+score).
    Adds _salary_eur, _fit_score, _display_score fields in-place.
    Used by both print_summary and track.py to guarantee consistent numbering."""
    parsed_jobs = [j for j in jobs if j.get("parsed")]
    for j in parsed_jobs:
        j["_salary_eur"] = _extract_max_salary_eur(j)
        j["_fit_score"] = _heuristic_score(j)
        rag = j.get("rag_score")
        if rag is not None and "technical_depth" in rag:
            # v2: hybrid = heuristic + grade points, clamped [0, 100]
            tech_pts = _grade_to_points(rag.get("technical_depth"))
            prof_pts = _grade_to_points(rag.get("profile_evidence"))
            j["_display_score"] = min(100, max(0, j["_fit_score"] + tech_pts + prof_pts))
        else:
            # v1 or unscored: heuristic only (v1 stored scores not used directly)
            j["_display_score"] = j["_fit_score"]

    # Reloc jobs only appear in Tier A — not worth showing if score doesn't justify moving
    tier_a = sorted([j for j in parsed_jobs if j["_display_score"] > 60], key=_sort_key)
    tier_b = sorted([j for j in parsed_jobs if 40 < j["_display_score"] <= 60 and not _is_reloc(j)], key=_sort_key)
    tier_c = sorted([j for j in parsed_jobs if j["_display_score"] <= 40 and not _is_reloc(j)], key=_sort_key)
    return tier_a, tier_b, tier_c


def print_summary(jobs):
    """Print tiered digest: A (>60) → B (41-60) → C (≤40)."""
    has_v2 = any("technical_depth" in (j.get("rag_score") or {}) for j in jobs if j.get("parsed"))
    mode = "hybrid score" if has_v2 else "heuristic fit"

    tier_a, tier_b, tier_c = ranked_jobs(jobs)
    parsed_jobs = tier_a + tier_b + tier_c

    print("\n" + "=" * 70)
    print(f"DAILY DIGEST ({mode}) — {len(parsed_jobs)} jobs")
    print("=" * 70)

    def _print_tier(label, jobs, counter):
        if not jobs:
            return counter
        print(f"\n{'─' * 70}")
        print(f"  {label} ({len(jobs)} jobs)")
        print(f"{'─' * 70}")
        reloc_header_shown = False
        for job in jobs:
            if _is_reloc(job) and not reloc_header_shown:
                print("\n  ✈  RELOC required from here ─────────────────────────────────")
                reloc_header_shown = True
            _print_job(counter, job)
            counter += 1
        return counter

    counter = 1
    counter = _print_tier("TIER A — APPLY  score > 60", tier_a, counter)
    counter = _print_tier("TIER B — EXPLORE  score 41-60", tier_b, counter)
    counter = _print_tier("TIER C — NOISE  score ≤ 40  [skim or skip]", tier_c, counter)

    # Stats
    domains = {}
    for j in parsed_jobs:
        d = j["parsed"].get("domain", "unknown")
        domains[d] = domains.get(d, 0) + 1

    hidden_reloc = sum(1 for j in parsed_jobs if _is_reloc(j) and j["_display_score"] <= 60)
    with_salary_count = sum(1 for j in parsed_jobs if j["_salary_eur"] > 0)
    scored_count = sum(1 for j in parsed_jobs if j.get("rag_score"))
    print(f"\n{'=' * 70}")
    print(
        f"A:{len(tier_a)}  B:{len(tier_b)}  C:{len(tier_c)} | {hidden_reloc} reloc hidden | {with_salary_count} with salary | {scored_count} RAG scored"
    )
    print(f"Domains: {', '.join(f'{k}({v})' for k, v in sorted(domains.items(), key=lambda x: -x[1]))}")
    print(f"{'=' * 70}")


def _auto_skip_reloc(jobs, applied_path="config/applied.yaml"):
    """Auto-add low-score reloc jobs to not_interested.ids.

    A reloc job that doesn't reach Tier A (score ≤ 60) is not worth relocating
    for — skip it permanently so it never costs parse/score tokens again.
    """
    import yaml

    # Ensure _display_score is set (may not be if job came straight from cache)
    for j in jobs:
        if j.get("parsed") and "_display_score" not in j:
            j["_salary_eur"] = _extract_max_salary_eur(j)
            j["_fit_score"] = _heuristic_score(j)
            rag = j.get("rag_score")
            if rag is not None and "technical_depth" in rag:
                tech_pts = _grade_to_points(rag.get("technical_depth"))
                prof_pts = _grade_to_points(rag.get("profile_evidence"))
                j["_display_score"] = min(100, max(0, j["_fit_score"] + tech_pts + prof_pts))
            else:
                # v1 or unscored: heuristic only (v1 stored scores not used directly)
                j["_display_score"] = j["_fit_score"]

    # Find reloc jobs with score ≤ 60 that aren't already tracked
    candidates = [
        j for j in jobs if j.get("parsed") and _is_reloc(j) and j.get("_display_score", 0) <= 60 and j.get("id")
    ]
    if not candidates:
        return

    # Load existing skip IDs to avoid duplicates
    if os.path.exists(applied_path):
        with open(applied_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data.setdefault("applied", {"companies": [], "ids": []})
    data.setdefault("not_interested", {"ids": [], "titles": []})
    existing_ids = {(e.get("id") if isinstance(e, dict) else e) for e in (data["not_interested"].get("ids") or [])}

    newly_skipped = []
    for j in candidates:
        if j["id"] not in existing_ids:
            note = f"{j['title'][:40]} @ {j['company']} (reloc, score {j['_display_score']})"
            data["not_interested"]["ids"].append({"id": j["id"], "note": note})
            existing_ids.add(j["id"])
            newly_skipped.append(j)

    if newly_skipped:
        with open(applied_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\n🚫 Auto-skipped {len(newly_skipped)} low-score reloc jobs (won't reappear)")


def main():
    args = sys.argv[1:]
    skip_scoring = "--no-score" in args
    full_refresh = "--refresh" in args  # nuke cache, reprocess everything
    rescore_only = "--rescore" in args  # keep parsed, redo RAG scores only
    send_email = "--notify" in args  # send email digest after run

    # Resolve profile: --profile <id> or default to first in config/profiles/
    profile_id = None
    if "--profile" in args:
        idx = args.index("--profile")
        if idx + 1 < len(args):
            profile_id = args[idx + 1]
    if not profile_id:
        available = list_profiles()
        if not available:
            print("ERROR: No profiles found in config/profiles/. Create one first.")
            return
        profile_id = available[0]

    profile = load_profile(profile_id)

    if not is_profile_active(profile):
        print(f"Profile '{profile_id}' is inactive (user.active: false) — skipping.")
        return

    _load_heuristic_config(profile)

    # Resolve profile-specific paths — single source of truth in resolve_profile_paths()
    paths = resolve_profile_paths(profile_id, profile)
    seen_ids_path = paths["seen_ids"]
    preferences_path = paths["preferences"]
    searches_path = paths["searches"]
    watchlist_path = paths["watchlist"]
    applied_path = paths["applied"]

    start_time = time.time()

    mode = "full"
    if full_refresh:
        mode = "refresh"
    elif rescore_only:
        mode = "rescore"
    elif skip_scoring:
        mode = "no_score"

    logger.info(
        "pipeline_start",
        profile_id=profile_id,
        mode=mode,
        notify=send_email,
    )
    _capture(
        profile_id,
        "agent_pipeline_start",
        {
            "profile_id": profile_id,
            "mode": mode,
            "notify": send_email,
        },
    )

    print(f"JobAgent - Phase 2: Scrape > Pre-filter > Parse > RAG Score > Rank  [{profile_id}]")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if full_refresh:
        print("(--refresh: cache cleared, full reprocess)")
    elif rescore_only:
        print("(--rescore: keeping parsed data, redoing RAG scores)")
    elif skip_scoring:
        print("(--no-score: heuristic only)")
    if send_email:
        print("(--notify: email digest will be sent)")
    print("=" * 70)

    # Derive target_countries for geo filtering — single source of truth for all filters
    home_locations_for_geo = profile.get("user", {}).get("home_locations", [])
    from geo import derive_target_countries as _derive_target_countries  # noqa: PLC0415

    target_countries: list[str] = _derive_target_countries(home_locations_for_geo)
    if not target_countries:
        # Fallback: read wttj_countries from profile as proxy for target countries
        target_countries = profile.get("target", {}).get("wttj_countries") or []

    # Step 1a: Scrape job boards → list[RawJob]
    all_raw: list[RawJob] = run_scraper(config_path=searches_path)

    # Step 1b: Poll ATS watchlist → list[RawJob]
    geo_rejected_at_scrape = 0
    try:
        ats_jobs, ats_geo_rejected = run_watchlist_scraper(
            config_path=watchlist_path,
            target_countries=target_countries or None,
        )
        all_raw.extend(ats_jobs)
        geo_rejected_at_scrape += ats_geo_rejected
    except Exception as e:
        print(f"\nWatchlist error (continuing without): {e}")

    # Step 1c: Welcome to the Jungle → list[RawJob]
    try:
        # WTTJ uses target_countries directly (same ISO2 codes)
        wttj_countries = target_countries or profile.get("target", {}).get("wttj_countries") or ["ES"]
        wttj_jobs = run_wttj_scraper(target_countries=wttj_countries)
        all_raw.extend(wttj_jobs)
    except Exception as e:
        print(f"\nWTTJ error (continuing without): {e}")

    # Step 1.5: Merge duplicates across sources (field-group priority)
    raw_jobs: list[RawJob] = merge_jobs(all_raw)

    # Enrichment stats: measure Glassdoor ↔ LinkedIn overlap after merge
    _src_counts: dict[str, int] = {}
    for j in raw_jobs:
        for s in j.sources or []:
            _src_counts[s] = _src_counts.get(s, 0) + 1
    _multi_src = sum(1 for j in raw_jobs if len(j.sources or []) > 1)
    _ld_gd = sum(1 for j in raw_jobs if j.sources and "linkedin" in j.sources and "glassdoor" in j.sources)
    _ld_gd_enriched = sum(
        1 for j in raw_jobs if j.sources and "linkedin" in j.sources and "glassdoor" in j.sources and j.location
    )
    if _src_counts:
        src_summary = ", ".join(f"{s}={n}" for s, n in sorted(_src_counts.items()))
        print(f"\n📊 Sources: {src_summary}")
        if _multi_src:
            print(
                f"   Multi-source merges: {_multi_src} | LinkedIn∩Glassdoor: {_ld_gd} ({_ld_gd_enriched} with location enriched)"
            )
        logger.info(
            "merge_enrichment_stats",
            source_counts=_src_counts,
            multi_source=_multi_src,
            linkedin_glassdoor_overlap=_ld_gd,
            linkedin_glassdoor_enriched=_ld_gd_enriched,
        )

    # Convert to dicts for downstream (prefilter/parser/scorer still use plain dicts)
    jobs = _to_dicts(raw_jobs)

    logger.info("scrape_complete", total_jobs=len(jobs))
    print(f"\nCombined: {len(jobs)} total jobs")

    if not jobs:
        print("\nNo jobs found. Check your search config.")
        _d = int(time.time() - start_time)
        logger.info(
            "pipeline_complete",
            profile_id=profile_id,
            mode=mode,
            duration_s=_d,
            status="no_jobs",
            n_parsed=0,
            n_scored=0,
        )
        _capture(
            profile_id,
            "agent_pipeline_complete",
            {
                "profile_id": profile_id,
                "mode": mode,
                "duration_s": _d,
                "status": "no_jobs",
                "n_parsed": 0,
                "n_scored": 0,
            },
        )
        return

    # Step 2: Pre-filter (always runs on all jobs — applies latest applied.yaml/preferences.yaml)
    home_locations = profile.get("user", {}).get("home_locations", [])
    _profile_role_function = (profile.get("target") or {}).get("role_function")
    passed, rejected, prefilter_stats = prefilter_jobs(
        jobs,
        config_path=preferences_path,
        applied_path=applied_path,
        seen_path=seen_ids_path,
        home_locations=home_locations,
        profile_role_function=_profile_role_function,
        target_countries=target_countries or None,
    )

    # Geo filter summary (15.7)
    geo_rejected_at_prefilter = prefilter_stats.get("non_target_geo", 0)
    geo_passed = prefilter_stats.get("passed", 0)
    total_scraped = len(jobs)
    if geo_rejected_at_scrape or geo_rejected_at_prefilter:
        print(
            f"\n🌍 Geo filter: {geo_rejected_at_scrape} rejected at scrape, "
            f"{geo_rejected_at_prefilter} rejected at prefilter → {geo_passed} passed"
        )
        geo_rejected_jobs = [j for j in rejected if "non-target geography" in (j.get("reject_reason") or "")]
        if geo_rejected_jobs:
            print("   Sample geo rejections:")
            for j in geo_rejected_jobs[:5]:
                print(f"   ❌ {j['title']} @ {j['company']} → {j.get('reject_reason', '')}")
    logger.info(
        "geo_filter_stats",
        total_scraped=total_scraped,
        geo_rejected_at_scrape=geo_rejected_at_scrape,
        geo_rejected_at_prefilter=geo_rejected_at_prefilter,
        geo_passed=geo_passed,
    )

    # PostHog per-job geo filter tracking (15.8)
    geo_rejected_jobs = [j for j in rejected if "non-target geography" in (j.get("reject_reason") or "")]
    for j in geo_rejected_jobs:
        _capture(
            profile_id,
            "geo_filter_applied",
            {
                "job_id": j.get("id"),
                "company": j.get("company"),
                "location": j.get("location"),
                "detected_country": (j.get("reject_reason") or "").split("geography:")[-1].strip().split(" ")[0],
                "filter_layer": j.get("_geo_layer"),
                "source": j.get("source"),
            },
        )
    _capture(
        profile_id,
        "geo_filter_run_stats",
        {
            "total_scraped": total_scraped,
            "geo_rejected_at_scrape": geo_rejected_at_scrape,
            "geo_rejected_at_prefilter": geo_rejected_at_prefilter,
            "geo_passed": geo_passed,
            "layer_location": sum(1 for j in geo_rejected_jobs if j.get("_geo_layer") == "prefilter_location"),
            "layer_description": sum(1 for j in geo_rejected_jobs if j.get("_geo_layer") == "prefilter_description"),
            "layer_signal": sum(1 for j in geo_rejected_jobs if j.get("_geo_layer") == "prefilter_signal"),
        },
    )

    if not passed:
        print("\nAll jobs filtered out. Loosen your preferences.")
        _d = int(time.time() - start_time)
        logger.info(
            "pipeline_complete",
            profile_id=profile_id,
            mode=mode,
            duration_s=_d,
            status="all_filtered",
            n_parsed=0,
            n_scored=0,
        )
        _capture(
            profile_id,
            "agent_pipeline_complete",
            {
                "profile_id": profile_id,
                "mode": mode,
                "duration_s": _d,
                "status": "all_filtered",
                "n_parsed": 0,
                "n_scored": 0,
            },
        )
        return

    # Step 3: Load cache (or start fresh if --refresh)
    cache = {} if full_refresh else load_cache()
    if full_refresh:
        save_cache(cache)  # wipe the file immediately
    cached_jobs, new_jobs = split_by_cache(passed, cache)
    logger.info("cache_split", cache_hits=len(cached_jobs), cache_misses=len(new_jobs))
    print(f"\n📦 Cache: {cache_stats(cache)} | {len(cached_jobs)} hits, {len(new_jobs)} new this run")

    # Step 3b: Cross-user dedup — check Railway DB for jobs already parsed by another user
    if new_jobs:
        from api_cache import fetch_existing_parsed

        db_parsed = fetch_existing_parsed([j["id"] for j in new_jobs])
        if db_parsed:
            n_restored = 0
            for job in new_jobs:
                if job["id"] in db_parsed and not job.get("parsed"):
                    job["parsed"] = db_parsed[job["id"]]
                    n_restored += 1
            logger.info("db_cache_restore", jobs_restored=n_restored)
            print(f"   ♻  {n_restored} jobs restored from DB (cross-user cache)")

    # --rescore: move cached jobs back to new_jobs but keep their parsed data
    if rescore_only and cached_jobs:
        print(f"   --rescore: re-scoring {len(cached_jobs)} cached jobs")
        for j in cached_jobs:
            j.pop("rag_score", None)
            j.pop("rag_error", None)
        new_jobs = cached_jobs + new_jobs
        cached_jobs = []

    # Step 4: Parse only new jobs (cached ones already have 'parsed')
    jobs_needing_parse = [j for j in new_jobs if not j.get("parsed")]
    jobs_with_parse = [j for j in new_jobs if j.get("parsed")]
    n_parsed = len(jobs_needing_parse)
    if jobs_needing_parse:
        jobs_needing_parse = parse_all(jobs_needing_parse, model="gpt-4o-mini")
    else:
        print("   No new jobs to parse.")
    new_jobs = jobs_with_parse + jobs_needing_parse

    # Step 4b: Heuristic gate — skip RAG for jobs that clearly don't fit (ADR-006).
    # Skipped jobs are still saved and visible in the digest with heuristic tier.
    jobs_to_score, heuristic_only = _heuristic_gate(new_jobs, profile)
    if heuristic_only:
        logger.info("heuristic_gate", to_score=len(jobs_to_score), heuristic_only=len(heuristic_only))
        print(f"\n🔍 Heuristic gate: {len(jobs_to_score)} → RAG, {len(heuristic_only)} → heuristic-only")
    new_jobs = jobs_to_score

    # Step 5: RAG score new jobs (and re-scored ones)
    # Hard cap as a backstop — the heuristic gate should do most of the work.
    if len(new_jobs) > MAX_SCORE_PER_RUN:
        logger.warning(
            "score_cap_applied",
            total=len(new_jobs),
            cap=MAX_SCORE_PER_RUN,
            deferred=len(new_jobs) - MAX_SCORE_PER_RUN,
        )
        print(f"\n⚠️  {len(new_jobs)} jobs past gate — capping at {MAX_SCORE_PER_RUN} to limit cost.")
        print(f"   Remaining {len(new_jobs) - MAX_SCORE_PER_RUN} jobs will be scored in future runs.")
        heuristic_only.extend(new_jobs[MAX_SCORE_PER_RUN:])
        new_jobs = new_jobs[:MAX_SCORE_PER_RUN]

    n_scored = 0
    if new_jobs and not skip_scoring:
        try:
            from vectorstore import build_vectorstore
            from scorer import score_all

            collection = build_vectorstore(profile=profile)
            new_jobs = score_all(new_jobs, collection, profile=profile)
            n_scored = sum(1 for j in new_jobs if j.get("rag_score"))
        except Exception as e:
            logger.error("rag_score_error", error=str(e), exc_info=True)
            print(f"\nRAG scoring error (continuing with heuristic only): {e}")

        # Step 5b: Persist gap/strength data for trend analysis
        scored_jobs = [j for j in new_jobs if j.get("rag_score")]
        if scored_jobs:
            try:
                from gap_tracker import append_gap_history

                n_gaps = append_gap_history(scored_jobs, profile)
                if n_gaps:
                    print(f"   Gap history: +{n_gaps} entries")
            except Exception as e:
                print(f"   Gap history error (non-fatal): {e}")

    # Step 6: Update cache with newly processed jobs (RAG-scored + heuristic-only)
    all_new = new_jobs + heuristic_only
    if all_new:
        added = update_cache(cache, all_new)
        save_cache(cache)
        logger.info("cache_updated", jobs_added=added)
        print(f"   Cache updated: +{added} jobs ({cache_stats(cache)})")

    # Step 7: Combine cached + new for digest (RAG-scored jobs ranked first)
    all_parsed = cached_jobs + new_jobs + heuristic_only

    # Step 8: Auto-skip low-score reloc jobs (score < 50 → not worth relocating for)
    # Writes their IDs to applied.yaml so the prefilter drops them in future runs.
    _auto_skip_reloc(all_parsed)

    # Step 9: Summary
    print_summary(all_parsed)

    # Step 10: Save snapshot
    save_results(all_parsed, profile_id=profile_id)

    if rejected:
        save_results(rejected, folder="output/rejected", profile_id=profile_id)

    # Step 10b: Sync to Railway before email so GET /api/digest/{profile_id} has today's data.
    # The GHA workflow curl POST /api/ingest is an idempotent backup (ON CONFLICT no-ops).
    _railway_url = os.environ.get("RAILWAY_URL", "")
    _ingest_key = os.environ.get("INGEST_API_KEY", "")
    if _railway_url and _ingest_key:
        _sync_to_railway(all_parsed, profile_id, _railway_url, _ingest_key)

    # Mark jobs as seen immediately after saving results.
    # Actual persistence to git only happens in GHA *after* successful Railway sync,
    # so if sync fails the seen_ids file is not pushed and jobs will reappear next run.
    _append_seen_ids(all_parsed, path=seen_ids_path)

    duration_s = int(time.time() - start_time)
    # Rough cost estimate: gpt-4o-mini parse ~$0.001/job, gpt-4o RAG score ~$0.04/job
    cost_usd = round(n_parsed * 0.001 + n_scored * 0.04, 3)

    tier_a = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "A")
    tier_b = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "B")
    tier_c = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "C")

    logger.info(
        "pipeline_complete",
        profile_id=profile_id,
        duration_s=duration_s,
        cost_usd=cost_usd,
        total_jobs=len(all_parsed),
        n_parsed=n_parsed,
        n_scored=n_scored,
        tier_a=tier_a,
        tier_b=tier_b,
        tier_c=tier_c,
    )
    _capture(
        profile_id,
        "agent_pipeline_complete",
        {
            "profile_id": profile_id,
            "mode": mode,
            "status": "success",
            "duration_s": duration_s,
            "cost_usd": cost_usd,
            "total_jobs": len(all_parsed),
            "n_parsed": n_parsed,
            "n_scored": n_scored,
            "tier_a": tier_a,
            "tier_b": tier_b,
            "tier_c": tier_c,
        },
    )

    print(f"\n✅ Done in {duration_s}s. Cache: {cache_stats(cache)}")
    if cost_usd > 0:
        print(f"   Estimated cost: ${cost_usd:.3f} ({n_parsed} parsed, {n_scored} scored)")

    # Step 11: Email digest (--notify only)
    if send_email:
        try:
            import yaml

            n_searches = 0
            n_watchlist = 0
            try:
                with open(searches_path) as f:
                    searches_cfg = yaml.safe_load(f) or {}
                n_searches = len(searches_cfg.get("searches", []))
            except Exception:
                pass
            try:
                with open(watchlist_path) as f:
                    wl_cfg = yaml.safe_load(f) or {}
                n_watchlist = len(wl_cfg.get("greenhouse", []) or []) + len(wl_cfg.get("lever", []) or [])
            except Exception:
                pass

            from notifier import send_digest

            run_meta = {
                "duration_s": duration_s,
                "cost_usd": cost_usd,
                "n_searches": n_searches,
                "n_watchlist": n_watchlist,
                "date": datetime.now().strftime("%d %b %Y"),
            }
            _email_railway_url = os.environ.get("RAILWAY_URL", "")
            _email_ingest_key = os.environ.get("INGEST_API_KEY", "")
            if _email_railway_url and _email_ingest_key:
                email_sent = send_digest(
                    railway_url=_email_railway_url,
                    profile_id=profile_id,
                    ingest_key=_email_ingest_key,
                    rejected_stats=prefilter_stats,
                    run_meta=run_meta,
                    profile=profile,
                )
            else:
                print("⚠  RAILWAY_URL or INGEST_API_KEY not set — skipping email digest")
                email_sent = False
            if not email_sent:
                logger.warning("email_skipped", reason="api_unavailable_or_no_jobs")
                print("⚠  Email not sent")
        except Exception as e:
            logger.error("email_error", error=str(e), exc_info=True)
            print(f"⚠  Email notify error (pipeline succeeded): {e}")


if __name__ == "__main__":
    main()
