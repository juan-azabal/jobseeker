"""
Pre-filter module: fast keyword-based filtering before expensive LLM scoring.
No API calls, just string matching against preferences.
"""

import os
from datetime import date, datetime
import yaml

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

    for entry in (applied_cfg.get("companies") or []):
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
        print(f"\n💡 Expired applied.companies (>{APPLIED_COMPANY_STALE_DAYS}d) — showing again, remove from applied.yaml when ready:")
        for company, applied_date, age_days in expired_companies:
            print(f"   • {company} (applied {applied_date}, {age_days}d ago)")

    # applied.ids: accept both {id:..., note:...} dicts and plain strings
    def _extract_ids(entries):
        ids = set()
        for e in (entries or []):
            if isinstance(e, dict):
                val = e.get("id")
            else:
                val = e
            if val:
                ids.add(str(val))
        return ids

    return {
        "applied_companies": applied_companies,
        "applied_ids":       _extract_ids(applied_cfg.get("ids")),
        "skip_ids":          _extract_ids(not_interested.get("ids")),
        "skip_titles":       [t.lower() for t in (not_interested.get("titles") or [])],
    }


def _is_us_only(job):
    """Detect non-EU roles (US, Canada, APAC) that won't offer visa sponsorship to EU candidates."""
    location = (job.get("location") or "").lower()
    description = (job.get("description") or "").lower()

    us_signals_location = [
        ", al", ", ak", ", az", ", ar", ", ca", ", co", ", ct", ", de", ", fl",
        ", ga", ", hi", ", id", ", il", ", in", ", ia", ", ks", ", ky", ", la",
        ", me", ", md", ", ma", ", mi", ", mn", ", ms", ", mo", ", mt", ", ne",
        ", nv", ", nh", ", nj", ", nm", ", ny", ", nc", ", nd", ", oh", ", ok",
        ", or", ", pa", ", ri", ", sc", ", sd", ", tn", ", tx", ", ut", ", vt",
        ", va", ", wa", ", wv", ", wi", ", wy",
        "united states", "estados unidos", "usa", "nationwide",
        "new york", "san francisco", "los angeles", "chicago", "seattle",
        "austin", "denver", "boston", "miami", "atlanta", "dallas",
        "salt lake city", "minneapolis", "portland", "phoenix",
    ]

    for signal in us_signals_location:
        if signal in location:
            return True

    us_visa_signals = [
        # Explicit US work authorisation requirements
        "authorized to work in the u.s",
        "authorized to work for any employer in the u.s",
        "must be authorized to work in the united states",
        "u.s. work authorization",
        "us work authorization",
        "e-verify",
        # "unable to sponsor" kept but scoped below — common in US postings
        # "must be legally authorized" removed: too broad, appears in EU job descriptions too
        # "401(k)" / "401k" removed: US multinationals include benefits in templates even for
        #   EU roles; filtering on this causes heavy false positives for remote jobs
        # "humana" removed: matches "derechos humanos" / "capital humano" in Spanish descriptions
        # "remote, nationwide" / "remote nationwide" removed without US context: UK/EU companies
        #   legitimately use this phrasing for country-wide remote roles
    ]

    # "unable to sponsor" is very US-specific but occasionally used by EU companies too;
    # only treat as US-only signal when combined with explicit US work-auth language nearby.
    if "unable to sponsor" in description and (
        "united states" in description or "u.s." in description or "visa sponsorship" in description
    ):
        return True

    for signal in us_visa_signals:
        if signal in description:
            return True

    return False


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


def prefilter_jobs(jobs, config_path, applied_path, seen_path, home_locations=None):
    prefs = load_preferences(config_path)
    pf = prefs["prefilter"]
    applied = load_applied(applied_path)
    seen_ids = load_seen_ids(seen_path)

    deal_breakers = [db.lower() for db in pf.get("deal_breakers", [])]
    title_keywords = [kw.lower() for kw in pf.get("title_must_contain_one_of", [])]
    title_exclude = [kw.lower() for kw in pf.get("title_exclude", [])]
    exclude_companies = [c.lower() for c in pf.get("exclude_companies", [])]
    accept_locations = [loc.lower() for loc in pf.get("location", {}).get("accept_onsite_cities", [])]

    # home_locations: user's base locations — used to rescue jobs that appear US-only
    # but actually include the user's home city/country.
    _home_locs = [loc.lower() for loc in (home_locations or [])]

    passed = []
    rejected = []

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
        "us_only": 0,
        "aggregator": 0,
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

        # 4. Filter US-only roles
        if not reason:
            if _is_us_only(job):
                location_lower = (job.get("location") or "").lower()
                if any(loc in location_lower for loc in accept_locations) or any(loc in location_lower for loc in _home_locs):
                    pass
                else:
                    reason = "US-only role (no EU location)"
                    stat_key = "us_only"

        # 5. Filter job aggregators
        if not reason:
            aggregator_companies = ["jobgether", "crossover", "turing", "toptal", "arc.dev"]
            if any(agg in company_lower for agg in aggregator_companies):
                reason = f"job aggregator: {job['company']}"
                stat_key = "aggregator"

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

    print(f"   Rejection breakdown:")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"   ❌ {reason}: {count}")

    if rejected:
        print(f"\n   Sample rejections:")
        for r in rejected[:5]:
            print(f"   ❌ {r['title']} @ {r['company']} → {r['reject_reason']}")

    return passed, rejected, stats
