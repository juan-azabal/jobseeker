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

from scraper import run_scraper
from ats_scraper import run_watchlist_scraper
from wttj_scraper import run_wttj_scraper
from prefilter import prefilter_jobs
from parser import parse_all
from jobcache import load_cache, save_cache, split_by_cache, update_cache, cache_stats
from user_config import load_profile, list_profiles, is_profile_active, resolve_profile_paths, compute_seniority_weights


SEEN_IDS_PATH = "config/seen_ids/juan.txt"  # fallback only; main() always passes profile-derived path


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


# --- Heuristic ranking (no API calls) ---
# Values loaded from user profile at runtime — see config/profiles/<id>.yaml

_PROFILE_SKILLS = None   # populated by _load_heuristic_config()
_DOMAIN_SCORES = None
_SENIORITY_SCORES = None
_SALARY_THRESHOLD = 130000
_HOME_LOCATIONS = []
_HOME_REGIONS = []           # auto-derived from home_locations via country-converter
_HOME_REGION_RE = None       # compiled regex for word-boundary region matching


def _load_heuristic_config(profile: dict):
    """Populate module-level heuristic constants from user profile."""
    from geo import derive_home_regions, build_region_pattern
    global _PROFILE_SKILLS, _DOMAIN_SCORES, _SENIORITY_SCORES
    global _SALARY_THRESHOLD, _HOME_LOCATIONS, _HOME_REGIONS, _HOME_REGION_RE
    _PROFILE_SKILLS   = [s.lower() for s in (profile.get("skills") or [])]
    _DOMAIN_SCORES    = {k.lower(): v for k, v in (profile.get("target", {}).get("domains") or {}).items()}
    # 3-tier fallback: seniority_weights (current) > seniority (legacy) > compute from level+track
    target = profile.get("target", {})
    stored_sw = target.get("seniority_weights") or target.get("seniority")
    if stored_sw:
        _SENIORITY_SCORES = {k.lower(): int(v) for k, v in stored_sw.items()}
    else:
        _SENIORITY_SCORES = compute_seniority_weights(
            target.get("level", ""), target.get("track", "ic")
        )
    _SALARY_THRESHOLD = profile.get("target", {}).get("salary_display_threshold", 130000)
    _HOME_LOCATIONS   = [loc.lower() for loc in (profile.get("user", {}).get("home_locations") or [])]
    _HOME_REGIONS     = derive_home_regions(_HOME_LOCATIONS)
    _HOME_REGION_RE   = build_region_pattern(_HOME_REGIONS)


# Domain override: if parser says "other" but keywords match, reclassify
_DOMAIN_KEYWORDS = {
    "data": ["data platform", "data pipeline", "data warehouse", "data lake",
             "lakehouse", "databricks", "snowflake", "clickhouse", "etl",
             "data product", "data governance", "data quality", "data model"],
    "ml": ["machine learning", "ml model", "ai agent", "llm", "nlp",
           "inference", "training", "deep learning", "neural"],
    "adtech": ["advertising", "ad tech", "programmatic", "dsp", "ssp",
              "header bidding", "rtb", "publisher monetization"],
    "saas": ["saas", "subscription", "b2b platform", "developer tool",
             "devops", "observability", "monitoring", "cloud platform"],
}


def _infer_domain(parsed):
    """Override 'other' domain using keyword detection."""
    domain = parsed.get("domain", "other")
    if domain != "other":
        return domain

    all_text = " ".join([
        parsed.get("responsibilities_summary", ""),
        " ".join(parsed.get("must_have_skills") or []),
        " ".join(parsed.get("technical_stack") or []),
    ]).lower()

    best_domain = "other"
    best_count = 0
    for d, keywords in _DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in all_text)
        if count > best_count:
            best_count = count
            best_domain = d

    return best_domain if best_count >= 1 else "other"


def _heuristic_score(job):
    """Quick fit score 0-100 from parsed data. No API calls."""
    p = job.get("parsed")
    if not p:
        return 0

    score = 0

    # Domain (0-15) with override
    domain = _infer_domain(p)
    p["domain"] = domain  # update for display
    score += _DOMAIN_SCORES.get(domain, 0)

    # Seniority (0-15)
    score += _SENIORITY_SCORES.get(p.get("seniority", "unknown"), 0)

    # Location (0-10)
    # Country-pinned remote gets no bonus — treated as reloc
    loc_type = p.get("location_type", "unknown")
    job_loc = (job.get("location") or "").lower()
    if loc_type == "remote" and not _is_remote_requiring_reloc(job):
        score += 10
    elif loc_type == "hybrid" and any(c in job_loc for c in _HOME_LOCATIONS):
        score += 8
    elif loc_type == "onsite" and any(c in job_loc for c in _HOME_LOCATIONS):
        score += 6

    # Skill overlap (0-30)
    all_text = " ".join(
        [s.lower() for s in p.get("must_have_skills", [])]
        + [s.lower() for s in p.get("nice_to_have_skills", [])]
        + [s.lower() for s in p.get("technical_stack", [])]
        + [p.get("responsibilities_summary", "").lower()]
    )
    matches = sum(1 for skill in _PROFILE_SKILLS if skill in all_text)
    score += min(30, matches * 4)

    # Red flags (-5 each, max -15)
    score -= min(15, len(p.get("red_flags") or []) * 5)

    return max(0, min(100, score))


# --- Currency conversion via ECB data (CurrencyConverter) ---

from currency_converter import CurrencyConverter as _CurrencyConverter
_fx = _CurrencyConverter(fallback_on_missing_rate=True)

# Map text signals → ISO 4217 currency codes
_CURRENCY_SIGNALS: list[tuple[list[str], str]] = [
    (["cad"],                                "CAD"),
    (["usd", "$"],                           "USD"),
    (["pln", "zl", "zlot"],                  "PLN"),
    (["gbp", "£"],                           "GBP"),
    (["chf"],                                "CHF"),
    (["sek"],                                "SEK"),
    (["dkk"],                                "DKK"),
    (["nok"],                                "NOK"),
    (["inr", "₹", "lakh", "lpa"],           "INR"),
    (["brl", "r$"],                          "BRL"),
    (["aud", "a$"],                          "AUD"),
    (["sgd", "s$"],                          "SGD"),
    (["czk", "kč"],                          "CZK"),
    (["huf", "ft"],                          "HUF"),
    (["ron", "lei"],                         "RON"),
    (["jpy", "¥", "yen"],                   "JPY"),
    (["ils", "₪", "shekel"],                "ILS"),
    (["try", "₺", "tl"],                    "TRY"),
]


def _to_eur(amount: float, currency_code: str) -> float:
    """Convert amount to EUR using ECB rates. Returns amount unchanged if already EUR."""
    if currency_code == "EUR":
        return amount
    try:
        return _fx.convert(amount, currency_code, "EUR")
    except Exception:
        return amount  # unknown currency — assume EUR


def _detect_currency(salary_str: str, job: dict) -> str:
    """Detect currency from salary text and job metadata. Returns ISO code."""
    # CAD needs special handling: "$" + Canada location
    if "$" in salary_str and "canada" in (job.get("location") or "").lower():
        return "CAD"
    for signals, code in _CURRENCY_SIGNALS:
        if any(sig in salary_str for sig in signals):
            return code
    return "EUR"


def _extract_max_salary_eur(job):
    """Extract max salary as EUR equivalent. Returns 0 if not available."""
    p = job.get("parsed") or {}
    salary_str = (p.get("salary_mentioned") or "").lower()
    if not salary_str or salary_str == "null":
        max_amt = job.get("max_amount")
        if max_amt and max_amt == max_amt:  # not NaN
            try:
                val = float(max_amt)
                currency = (job.get("currency") or "").upper()
                if not currency or currency == "EUR":
                    return val
                return _to_eur(val, currency)
            except (ValueError, TypeError):
                return 0
        return 0

    # Normalize: remove spaces used as thousand separators (European style: "50 000")
    # and strip commas used as thousand separators (American style: "50,000")
    normalized = re.sub(r'(\d)[ \u00a0](\d)', r'\1\2', salary_str)  # "50 000" → "50000"
    normalized = normalized.replace(',', '')
    # Expand shorthand: "80k" → "80000", "100k" → "100000"
    normalized = re.sub(r'(\d+)\s*k\b', lambda m: str(int(m.group(1)) * 1000), normalized)

    # Extract salary-like numbers: ≥ 4 digits, but exclude years (1900-2099)
    raw_nums = [int(m) for m in re.findall(r'\d+', normalized)]
    vals = [n for n in raw_nums if n >= 1000 and not (1900 <= n <= 2099)]
    if not vals:
        return 0

    max_val = max(vals)
    if max_val < 20000:
        max_val *= 12  # monthly → annual

    # Currency conversion via ECB rates
    currency = _detect_currency(salary_str, job)
    max_val = _to_eur(max_val, currency)

    # Sanity cap: >250K EUR is almost certainly a parse error
    if max_val > 250000:
        return 0

    return max_val


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

    salary_display = f"~EUR {int(salary_eur/1000)}K" if salary_eur > 0 else "no salary"
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
    print(f"   {job.get('location', '?')} ({location_type}) | {seniority} | {domain} | {salary_display} | {score_label}")

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
        j["_display_score"] = rag["score"] if rag else j["_fit_score"]

    # Reloc jobs only appear in Tier A — not worth showing if score doesn't justify moving
    tier_a = sorted([j for j in parsed_jobs if j["_display_score"] >= 50], key=_sort_key)
    tier_b = sorted([j for j in parsed_jobs if 30 <= j["_display_score"] < 50 and not _is_reloc(j)], key=_sort_key)
    tier_c = sorted([j for j in parsed_jobs if j["_display_score"] < 30 and not _is_reloc(j)], key=_sort_key)
    return tier_a, tier_b, tier_c


def print_summary(jobs):
    """Print tiered digest: A (≥50) → B (30-49) → C (<30)."""
    has_rag = any(j.get("rag_score") for j in jobs if j.get("parsed"))
    mode = "RAG score" if has_rag else "heuristic fit"

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
                print(f"\n  ✈  RELOC required from here ─────────────────────────────────")
                reloc_header_shown = True
            _print_job(counter, job)
            counter += 1
        return counter

    counter = 1
    counter = _print_tier("TIER A — APPLY  score ≥ 50", tier_a, counter)
    counter = _print_tier("TIER B — EXPLORE  score 30-49", tier_b, counter)
    counter = _print_tier("TIER C — NOISE  score < 30  [skim or skip]", tier_c, counter)

    # Stats
    domains = {}
    for j in parsed_jobs:
        d = j["parsed"].get("domain", "unknown")
        domains[d] = domains.get(d, 0) + 1

    hidden_reloc = sum(1 for j in parsed_jobs if _is_reloc(j) and j["_display_score"] < 50)
    with_salary_count = sum(1 for j in parsed_jobs if j["_salary_eur"] > 0)
    scored_count = sum(1 for j in parsed_jobs if j.get("rag_score"))
    print(f"\n{'=' * 70}")
    print(f"A:{len(tier_a)}  B:{len(tier_b)}  C:{len(tier_c)} | {hidden_reloc} reloc hidden | {with_salary_count} with salary | {scored_count} RAG scored")
    print(f"Domains: {', '.join(f'{k}({v})' for k, v in sorted(domains.items(), key=lambda x: -x[1]))}")
    print(f"{'=' * 70}")


def _auto_skip_reloc(jobs, applied_path="config/applied.yaml"):
    """Auto-add low-score reloc jobs to not_interested.ids.

    A reloc job that doesn't reach Tier A (score < 50) is not worth relocating
    for — skip it permanently so it never costs parse/score tokens again.
    """
    import yaml

    # Ensure _display_score is set (may not be if job came straight from cache)
    for j in jobs:
        if j.get("parsed") and "_display_score" not in j:
            j["_salary_eur"] = _extract_max_salary_eur(j)
            j["_fit_score"] = _heuristic_score(j)
            rag = j.get("rag_score")
            j["_display_score"] = rag["score"] if rag else j["_fit_score"]

    # Find reloc jobs with score < 50 that aren't already tracked
    candidates = [
        j for j in jobs
        if j.get("parsed") and _is_reloc(j) and j.get("_display_score", 0) < 50 and j.get("id")
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
    existing_ids = {
        (e.get("id") if isinstance(e, dict) else e)
        for e in (data["not_interested"].get("ids") or [])
    }

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
    skip_scoring   = "--no-score"      in args
    full_refresh   = "--refresh"       in args  # nuke cache, reprocess everything
    rescore_only   = "--rescore"       in args  # keep parsed, redo RAG scores only
    send_email     = "--notify"        in args  # send email digest after run

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
    seen_ids_path    = paths["seen_ids"]
    preferences_path = paths["preferences"]
    searches_path    = paths["searches"]
    watchlist_path   = paths["watchlist"]
    applied_path     = paths["applied"]

    start_time = time.time()

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

    # Step 1a: Scrape job boards
    jobs = run_scraper(config_path=searches_path)

    # Step 1b: Poll ATS watchlist
    existing_ids = {j["id"] for j in jobs}
    try:
        ats_jobs = run_watchlist_scraper(config_path=watchlist_path)
        for j in ats_jobs:
            if j["id"] not in existing_ids:
                jobs.append(j)
                existing_ids.add(j["id"])
    except Exception as e:
        print(f"\nWatchlist error (continuing without): {e}")

    # Step 1c: Welcome to the Jungle
    try:
        wttj_jobs = run_wttj_scraper()
        for j in wttj_jobs:
            if j["id"] not in existing_ids:
                jobs.append(j)
                existing_ids.add(j["id"])
    except Exception as e:
        print(f"\nWTTJ error (continuing without): {e}")

    print(f"\nCombined: {len(jobs)} total jobs")

    if not jobs:
        print("\nNo jobs found. Check your search config.")
        return

    # Step 2: Pre-filter (always runs on all jobs — applies latest applied.yaml/preferences.yaml)
    home_locations = profile.get("user", {}).get("home_locations", [])
    passed, rejected, prefilter_stats = prefilter_jobs(
        jobs,
        config_path=preferences_path,
        applied_path=applied_path,
        seen_path=seen_ids_path,
        home_locations=home_locations,
    )

    if not passed:
        print("\nAll jobs filtered out. Loosen your preferences.")
        return

    # Step 3: Load cache (or start fresh if --refresh)
    cache = {} if full_refresh else load_cache()
    if full_refresh:
        save_cache(cache)  # wipe the file immediately
    cached_jobs, new_jobs = split_by_cache(passed, cache)
    print(f"\n📦 Cache: {cache_stats(cache)} | {len(cached_jobs)} hits, {len(new_jobs)} new this run")

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
    jobs_with_parse    = [j for j in new_jobs if j.get("parsed")]
    n_parsed = len(jobs_needing_parse)
    if jobs_needing_parse:
        jobs_needing_parse = parse_all(jobs_needing_parse, model="gpt-4o-mini")
    else:
        print("   No new jobs to parse.")
    new_jobs = jobs_with_parse + jobs_needing_parse

    # Step 5: RAG score new jobs (and re-scored ones)
    n_scored = 0
    if new_jobs and not skip_scoring:
        try:
            from vectorstore import build_vectorstore
            from scorer import score_all
            collection = build_vectorstore(profile=profile)
            new_jobs = score_all(new_jobs, collection, profile=profile)
            n_scored = sum(1 for j in new_jobs if j.get("rag_score"))
        except Exception as e:
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

    # Step 6: Update cache with newly processed jobs
    if new_jobs:
        added = update_cache(cache, new_jobs)
        save_cache(cache)
        print(f"   Cache updated: +{added} jobs ({cache_stats(cache)})")

    # Step 7: Combine cached + new for digest
    all_parsed = cached_jobs + new_jobs

    # Step 8: Auto-skip low-score reloc jobs (score < 50 → not worth relocating for)
    # Writes their IDs to applied.yaml so the prefilter drops them in future runs.
    _auto_skip_reloc(all_parsed)

    # Step 9: Summary
    print_summary(all_parsed)

    # Step 10: Save snapshot
    save_results(all_parsed, profile_id=profile_id)

    if rejected:
        save_results(rejected, folder="output/rejected", profile_id=profile_id)

    # seen_ids persisted only after confirmed email delivery — see Step 11 below

    duration_s = int(time.time() - start_time)
    # Rough cost estimate: gpt-4o-mini parse ~$0.001/job, gpt-4o RAG score ~$0.04/job
    cost_usd = round(n_parsed * 0.001 + n_scored * 0.04, 3)

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
            email_sent = send_digest(all_parsed, prefilter_stats, run_meta, profile=profile)
            if email_sent:
                # Only mark jobs as seen once the user has actually received the email
                _append_seen_ids(all_parsed, path=seen_ids_path)
            else:
                print("⚠  Email not sent — seen_ids NOT updated (jobs will reappear next run)")
        except Exception as e:
            print(f"⚠  Email notify error (pipeline succeeded): {e}")
            print("   seen_ids NOT updated — jobs will reappear next run")


if __name__ == "__main__":
    main()
