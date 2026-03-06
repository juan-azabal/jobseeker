"""
Pre-filter module: fast keyword-based filtering before expensive LLM scoring.
No API calls, just string matching against preferences.
"""

import os
import re
from datetime import date, datetime
import yaml

from geo import resolve_location_country

APPLIED_COMPANY_STALE_DAYS = 90  # warn after ~3 months


def load_preferences(path: str):
    """Load prefilter preferences from the given path. Path is required — use
    resolve_profile_paths() in user_config.py to get the correct per-user path."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_applied(path: str):
    """Load applied/not-interested config. Returns empty defaults if file missing.

    applied.companies entries: {name: str, date: YYYY-MM-DD}
      - Active (< APPLIED_COMPANY_STALE_DAYS old): skip all roles, no warning.
      - Stale (>= APPLIED_COMPANY_STALE_DAYS old): still skip, but print a reminder
        so the user knows they can safely remove or keep the entry.

    applied.ids entries: {id: str, note: str}  (or plain strings for back-compat)
    not_interested.ids / not_interested.titles: skip without expiry.
    """
    if not os.path.exists(path):
        return {"applied_companies": [], "applied_ids": set(), "skip_ids": set(), "skip_titles": []}
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    applied_cfg = data.get("applied") or {}
    not_interested = data.get("not_interested") or {}

    today = date.today()
    applied_companies = []
    expired_companies = []

    for entry in applied_cfg.get("companies") or []:
        if isinstance(entry, dict):
            name = (entry.get("name") or "").lower()
            raw_date = entry.get("date")
            try:
                applied_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
                age_days = (today - applied_date).days
                if age_days >= APPLIED_COMPANY_STALE_DAYS:
                    # Expired — skip silently (don't filter this company anymore)
                    expired_companies.append((entry.get("name", name), applied_date, age_days))
                    continue
            except (ValueError, TypeError):
                pass  # no date or unparseable — keep filtering
        else:
            name = str(entry).lower()
        if name:
            applied_companies.append(name)

    if expired_companies:
        print(
            f"\n💡 Expired applied.companies (>{APPLIED_COMPANY_STALE_DAYS}d) — showing again, remove from applied.yaml when ready:"
        )
        for company, applied_date, age_days in expired_companies:
            print(f"   • {company} (applied {applied_date}, {age_days}d ago)")

    # applied.ids: accept both {id:..., note:...} dicts and plain strings
    def _extract_ids(entries):
        ids = set()
        for e in entries or []:
            if isinstance(e, dict):
                val = e.get("id")
            else:
                val = e
            if val:
                ids.add(str(val))
        return ids

    return {
        "applied_companies": applied_companies,
        "applied_ids": _extract_ids(applied_cfg.get("ids")),
        "skip_ids": _extract_ids(not_interested.get("ids")),
        "skip_titles": [t.lower() for t in (not_interested.get("titles") or [])],
    }


# Location-signaling context words for Layer 2 description scan (city mentions)
_LOC_CONTEXT_WORDS = re.compile(
    r"\b(based in|located in|office in|offices in|headquarters in|hq in|our .{0,20} office)\b",
    re.IGNORECASE,
)

# US-specific signals in descriptions for Layer 3
_US_DESC_SIGNALS = [
    "authorized to work in the u.s",
    "authorized to work for any employer in the u.s",
    "must be authorized to work in the united states",
    "u.s. work authorization",
    "us work authorization",
    "e-verify",
    "remote within the us",
    "us-based",
    "us total target compensation",
]


def _is_non_target_geo(
    job: dict,
    target_countries: list[str],
) -> tuple[bool, str | None, str | None]:
    """Return (should_reject, detected_country, filter_layer) for a job.

    filter_layer values (for PostHog tracking):
      "prefilter_location"    — Layer 1: structured location field
      "prefilter_description" — Layer 2: city mention in description
      "prefilter_signal"      — Layer 3: US visa/auth language in description
      None                    — job passed (not rejected)

    Detection chain:
    Layer 1 — Structured location (highest confidence):
        resolve_location_country(job.location) → if resolved and NOT in target_countries
        and job is not remote-fulltime → reject.
    Layer 2 — Description city/country mentions (medium confidence, null location):
        Scan description for city names from geonamescache near location-signaling
        context words OR in the first 500 chars.
    Layer 3 — Region-specific signals (supplementary, lowest confidence):
        Check description for US-specific visa/auth language.
        Reject only when detected country NOT in target_countries.

    Remote-fulltime exception: jobs with remote_type="fulltime" always pass
    regardless of location.

    Conservative: unresolved location AND no signals → pass (return False).
    """
    import geonamescache as _gnc  # lazy import — module already loaded

    _gc = _gnc.GeonamesCache()

    remote_type = (job.get("remote_type") or "").lower()
    is_remote_fulltime = remote_type == "fulltime"
    if is_remote_fulltime:
        return False, None, None

    # Layer 1: structured location field
    location = (job.get("location") or "").strip()
    if location:
        country = resolve_location_country(location)
        if country and country not in target_countries:
            return True, country, "prefilter_location"
        if country and country in target_countries:
            return False, None, None
        # country is None → fall through to description layers

    # Layer 2: city/country mentions in description near location-signaling context words
    description = job.get("description") or ""
    desc_lower = description.lower()

    # Only scan if location is null/empty (already handled above if location exists)
    if not location and description:
        # Extract lines containing location context words (e.g. "based in Berlin")
        context_lines: list[str] = []
        for line in description.split("\n"):
            if _LOC_CONTEXT_WORDS.search(line):
                context_lines.append(line)

        # Only proceed if there are actual location-signaling context lines
        if context_lines:
            seen_countries: set[str] = set()
            for line in context_lines:
                # Find capitalized words ≥5 chars in this context line.
                # Min 5 chars (1 capital + 4 lowercase) avoids common English words like
                # "Our", "The", "For" matching city alternate names.
                words = re.findall(r"\b[A-Z][a-z]{4,}\b", line)
                for word in words:
                    cities = _gc.search_cities(word, case_sensitive=False)
                    if not cities:
                        continue
                    top = max(cities, key=lambda c: c.get("population", 0))
                    if top.get("population", 0) < 200_000:
                        continue  # too small or ambiguous
                    cc = top.get("countrycode", "")
                    if not cc or cc in seen_countries:
                        continue
                    seen_countries.add(cc)
                    if cc not in target_countries:
                        return True, cc, "prefilter_description"

    # Layer 3: US-specific signals in description
    for signal in _US_DESC_SIGNALS:
        if signal in desc_lower:
            if "US" not in target_countries:
                return True, "US", "prefilter_signal"
            return False, None, None  # US signal but US is target → pass

    # "unable to sponsor" only when combined with US context
    if "unable to sponsor" in desc_lower and (
        "united states" in desc_lower or "u.s." in desc_lower or "visa sponsorship" in desc_lower
    ):
        if "US" not in target_countries:
            return True, "US", "prefilter_signal"

    return False, None, None


def _is_relevant_title(title_lower, title_keywords, title_exclude):
    """Check if title matches PM roles and exclude non-PM roles."""
    has_pm_keyword = any(kw in title_lower for kw in title_keywords)
    if not has_pm_keyword:
        return False, "no PM keyword in title"

    for exc in title_exclude:
        if exc in title_lower:
            return False, f"title contains excluded term: '{exc}'"

    return True, None


def load_seen_ids(path="config/seen_ids.txt"):
    """Load set of job IDs that have already appeared in a digest."""
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return {line.strip() for line in f if line.strip()}


def prefilter_jobs(
    jobs,
    config_path,
    applied_path,
    seen_ids: set[str] | None = None,
    home_locations=None,
    profile_role_function=None,
    target_countries: list[str] | None = None,
):
    """Filter jobs using keyword, geo, and role-function rules.

    Args:
        jobs: List of job dicts.
        config_path: Path to preferences YAML.
        applied_path: Path to applied.yaml.
        seen_ids: Set of already-seen job IDs. Loaded from Railway DB by the caller.
        home_locations: User's home locations (used when target_countries not provided).
        profile_role_function: Profile role function (e.g. "product") for soft gate.
        target_countries: ISO2 codes for geo filtering (e.g. ["ES", "NL"]).
            If None, geo filtering uses the preferences file's reject_if_requires_relocation_outside.
    """
    prefs = load_preferences(config_path)
    pf = prefs["prefilter"]
    applied = load_applied(applied_path)
    seen_ids = seen_ids or set()

    deal_breakers = [db.lower() for db in pf.get("deal_breakers", [])]
    title_keywords = [kw.lower() for kw in pf.get("title_must_contain_one_of", [])]
    title_exclude = [kw.lower() for kw in pf.get("title_exclude", [])]
    exclude_companies = [c.lower() for c in pf.get("exclude_companies", [])]

    # home_locations: user's base locations (kept for legacy rescue logic)
    _home_locs = [loc.lower() for loc in (home_locations or [])]

    passed = []
    rejected = []

    _profile_rf = (profile_role_function or "").strip().lower()

    stats = {
        "total": len(jobs),
        "passed": 0,
        "already_seen": 0,
        "already_applied": 0,
        "not_interested": 0,
        "excluded_company": 0,
        "deal_breaker": 0,
        "no_pm_keyword": 0,
        "title_excluded": 0,
        "non_target_geo": 0,
        "aggregator": 0,
        "role_function_mismatch": 0,
    }

    for job in jobs:
        # Normalize unicode spaces (e.g. \u202f narrow no-break space from WTTJ) to ASCII space
        title_lower = job["title"].replace("\u202f", " ").replace("\u00a0", " ").lower()
        desc_lower = (job.get("description") or "").lower()
        company_lower = job["company"].lower()
        reason = None
        stat_key = None

        # 0a. Already seen in a previous digest (automatic dedup across runs)
        if job.get("id") in seen_ids:
            reason = "already seen in previous digest"
            stat_key = "already_seen"

        # 0b. Already applied or not interested (manual)
        elif job.get("id") in applied["applied_ids"]:
            reason = "already applied (id match)"
            stat_key = "already_applied"
        elif any(ac in company_lower for ac in applied["applied_companies"]):
            reason = f"already applied: {job['company']}"
            stat_key = "already_applied"
        elif job.get("id") in applied["skip_ids"]:
            reason = "not interested (id match)"
            stat_key = "not_interested"
        elif any(st in title_lower for st in applied["skip_titles"]):
            reason = f"not interested (title): {next(st for st in applied['skip_titles'] if st in title_lower)}"
            stat_key = "not_interested"

        # 1. Excluded companies (Gartner, G2, etc.)
        if not reason and any(exc in company_lower for exc in exclude_companies):
            reason = f"excluded company: {job['company']}"
            stat_key = "excluded_company"

        # 2. Deal breakers in title or early description
        if not reason:
            for db in deal_breakers:
                if db in title_lower or db in desc_lower[:500]:
                    reason = f"deal breaker: '{db}'"
                    stat_key = "deal_breaker"
                    break

        # 3. Title must be a PM role (and not an excluded role)
        if not reason:
            is_relevant, title_reason = _is_relevant_title(title_lower, title_keywords, title_exclude)
            if not is_relevant:
                reason = title_reason
                stat_key = "no_pm_keyword" if title_reason == "no PM keyword in title" else "title_excluded"

        # 4. Unified geo filter (replaces _is_us_only + _is_non_target_onsite)
        if not reason and target_countries:
            should_reject, detected_country, geo_layer = _is_non_target_geo(job, target_countries)
            if should_reject:
                reason = f"non-target geography: {detected_country} (location={job.get('location', '')})"
                stat_key = "non_target_geo"
                job["_geo_layer"] = geo_layer  # layer for PostHog tracking

        # 5. Filter job aggregators
        if not reason:
            aggregator_companies = ["jobgether", "crossover", "turing", "toptal", "arc.dev"]
            if any(agg in company_lower for agg in aggregator_companies):
                reason = f"job aggregator: {job['company']}"
                stat_key = "aggregator"

        # 6. role_function soft gate (only when both profile and job declare the field)
        if not reason and _profile_rf:
            job_rf = (job.get("role_function") or "").strip().lower()
            if job_rf and job_rf != _profile_rf:
                reason = f"role_function mismatch: profile={_profile_rf} job={job_rf}"
                stat_key = "role_function_mismatch"

        if reason:
            job["reject_reason"] = reason
            rejected.append(job)
            if stat_key:
                stats[stat_key] = stats.get(stat_key, 0) + 1
        else:
            passed.append(job)

    stats["passed"] = len(passed)

    print(f"\n📋 Pre-filter: {len(passed)} passed, {len(rejected)} rejected out of {len(jobs)}")

    reasons = {}
    for r in rejected:
        key = r["reject_reason"].split(":")[0].strip()
        reasons[key] = reasons.get(key, 0) + 1

    print("   Rejection breakdown:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"   ❌ {reason}: {count}")

    if rejected:
        print("\n   Sample rejections:")
        for r in rejected[:5]:
            print(f"   ❌ {r['title']} @ {r['company']} → {r['reject_reason']}")

    return passed, rejected, stats
