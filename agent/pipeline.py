"""Agent pipeline: scrape → prefilter → parse → score → notify.

Public API:  run_pipeline(profile_id, profile, paths, opts)
             PipelineOptions  — pipeline options dataclass
             save_results(jobs, folder, profile_id)
             _to_dicts(jobs)  — RawJob list → dict list shim
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog

from models import RawJob
from merger import merge_jobs
from ats_scraper import run_watchlist_scraper
from wttj_scraper import run_wttj_scraper
from prefilter import prefilter_jobs
from profile_client import fetch_seen_ids, post_seen_ids
from parser import parse_all
from jobcache import load_cache, save_cache, split_by_cache, update_cache, cache_stats
from scoring import heuristic_gate as _heuristic_gate
from display import print_summary, auto_skip_reloc as _auto_skip_reloc

logger = structlog.get_logger("agent.pipeline")
MAX_SCORE_PER_RUN = 50


@dataclass
class PipelineOptions:
    mode: str
    skip_scoring: bool = False
    full_refresh: bool = False
    rescore_only: bool = False
    send_email: bool = False


_ph_client = None


def _capture(profile_id: str, event: str, props: dict) -> None:
    """Fire a PostHog server-side event. No-op when POSTHOG_API_KEY is absent."""
    global _ph_client
    key = os.environ.get("POSTHOG_API_KEY")
    if not key:
        return
    try:
        if _ph_client is None:
            from posthog import Posthog  # noqa: PLC0415

            host = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")
            _ph_client = Posthog(key, host=host)
            try:
                import posthog as _phm  # noqa: PLC0415

                _phm.api_key = key
                _phm.host = host
            except Exception:
                pass
        _ph_client.capture(profile_id, event, props)
    except Exception:
        pass


def _to_dicts(jobs: list[RawJob]) -> list[dict]:
    """Convert list[RawJob] → list[dict] for downstream pipeline compatibility."""
    return [dict(j.model_dump(), is_remote=j.is_remote) for j in jobs]


def save_results(jobs: list, folder: str = "output", profile_id: str | None = None) -> str:
    """Save jobs to JSON snapshot. Format v2: {_metadata, jobs}."""
    os.makedirs(folder, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(folder, f"jobs_{ts}.json")
    clean_jobs = []
    for job in jobs:
        clean = {k: (None if v != v else v) for k, v in job.items() if not k.startswith("_")}
        if "_fit_score" in job:
            clean["fit_score"] = job["_fit_score"]
        clean_jobs.append(clean)
    payload = {"_metadata": {"profile_id": profile_id, "timestamp": ts, "version": "2"}, "jobs": clean_jobs}
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\n>> Results saved to {filepath}")
    return filepath


def _scrape_all(profile: dict, paths: dict, target_countries: list) -> tuple[list, int]:
    """Steps 1a–1.5: run all scrapers, merge, return (jobs_as_dicts, geo_rejected_count)."""
    all_raw: list[RawJob] = []
    geo_rejected = 0
    try:
        ats_jobs, ats_geo = run_watchlist_scraper(
            config_path=paths["watchlist"], target_countries=target_countries or None
        )
        all_raw.extend(ats_jobs)
        geo_rejected += ats_geo
    except Exception as e:
        print(f"\nWatchlist error (continuing without): {e}")
    try:
        wttj_countries = target_countries or profile.get("target", {}).get("wttj_countries") or ["ES"]
        all_raw.extend(run_wttj_scraper(target_countries=wttj_countries))
    except Exception as e:
        print(f"\nWTTJ error (continuing without): {e}")

    raw_jobs = merge_jobs(all_raw)
    _log_merge_stats(raw_jobs)
    jobs = _to_dicts(raw_jobs)
    logger.info("scrape_complete", total_jobs=len(jobs))
    print(f"\nCombined: {len(jobs)} total jobs")
    return jobs, geo_rejected


def _log_merge_stats(raw_jobs: list[RawJob]) -> None:
    """Log enrichment stats for multi-source merges."""
    src_counts: dict[str, int] = {}
    for j in raw_jobs:
        for s in j.sources or []:
            src_counts[s] = src_counts.get(s, 0) + 1
    if not src_counts:
        return
    multi = sum(1 for j in raw_jobs if len(j.sources or []) > 1)
    ld_gd = sum(1 for j in raw_jobs if j.sources and {"linkedin", "glassdoor"} <= set(j.sources))
    ld_loc = sum(1 for j in raw_jobs if j.sources and {"linkedin", "glassdoor"} <= set(j.sources) and j.location)
    print(f"\n📊 Sources: {', '.join(f'{s}={n}' for s, n in sorted(src_counts.items()))}")
    if multi:
        print(f"   Multi-source merges: {multi} | LinkedIn∩Glassdoor: {ld_gd} ({ld_loc} with location enriched)")
    logger.info(
        "merge_enrichment_stats",
        source_counts=src_counts,
        multi_source=multi,
        linkedin_glassdoor_overlap=ld_gd,
        linkedin_glassdoor_enriched=ld_loc,
    )


def _run_prefilter(
    jobs: list, profile: dict, paths: dict, target_countries: list, geo_rejected_at_scrape: int, seen_ids: set
) -> tuple[list, list, dict]:
    """Step 2: apply all filters. Returns (passed, rejected, prefilter_stats)."""
    home_locations = profile.get("user", {}).get("home_locations", [])
    role_function = (profile.get("target") or {}).get("role_function")
    passed, rejected, stats = prefilter_jobs(
        jobs,
        config_path=paths["preferences"],
        applied_path=paths["applied"],
        seen_ids=seen_ids,
        home_locations=home_locations,
        profile_role_function=role_function,
        target_countries=target_countries or None,
    )
    geo_pf = stats.get("non_target_geo", 0)
    geo_pass = stats.get("passed", 0)
    if geo_rejected_at_scrape or geo_pf:
        print(
            f"\n🌍 Geo filter: {geo_rejected_at_scrape} rejected at scrape, {geo_pf} rejected at prefilter → {geo_pass} passed"
        )
        for j in [j for j in rejected if "non-target geography" in (j.get("reject_reason") or "")][:5]:
            print(f"   ❌ {j['title']} @ {j['company']} → {j.get('reject_reason', '')}")
    logger.info("geo_filter_stats", total_scraped=len(jobs), geo_rejected_at_prefilter=geo_pf, geo_passed=geo_pass)
    return passed, rejected, stats


def _emit_geo_events(profile_id: str, rejected: list, stats: dict, geo_rejected_at_scrape: int) -> None:
    """PostHog per-job geo filter events + aggregate stats."""
    geo_rej = [j for j in rejected if "non-target geography" in (j.get("reject_reason") or "")]
    for j in geo_rej:
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
            "total_scraped": stats.get("passed", 0) + len(rejected),
            "geo_rejected_at_scrape": geo_rejected_at_scrape,
            "geo_rejected_at_prefilter": stats.get("non_target_geo", 0),
            "geo_passed": stats.get("passed", 0),
            "layer_location": sum(1 for j in geo_rej if j.get("_geo_layer") == "prefilter_location"),
            "layer_description": sum(1 for j in geo_rej if j.get("_geo_layer") == "prefilter_description"),
            "layer_signal": sum(1 for j in geo_rej if j.get("_geo_layer") == "prefilter_signal"),
        },
    )


def _load_and_parse(passed: list, cache: dict, full_refresh: bool, rescore_only: bool) -> tuple[list, list, dict, int]:
    """Steps 3–4: cache split, cross-user DB restore, parse. Returns (cached_jobs, new_jobs, cache, n_parsed)."""
    if full_refresh:
        save_cache(cache)
    cached_jobs, new_jobs = split_by_cache(passed, cache)
    logger.info("cache_split", cache_hits=len(cached_jobs), cache_misses=len(new_jobs))
    print(f"\n📦 Cache: {cache_stats(cache)} | {len(cached_jobs)} hits, {len(new_jobs)} new this run")
    if new_jobs:
        from api_cache import fetch_existing_parsed  # noqa: PLC0415

        db_parsed = fetch_existing_parsed([j["id"] for j in new_jobs])
        if db_parsed:
            n_restored = 0
            for j in new_jobs:
                if j["id"] in db_parsed and not j.get("parsed"):
                    j["parsed"] = db_parsed[j["id"]]
                    n_restored += 1
            logger.info("db_cache_restore", jobs_restored=n_restored)
            print(f"   ♻  {n_restored} jobs restored from DB (cross-user cache)")
    if rescore_only and cached_jobs:
        print(f"   --rescore: re-scoring {len(cached_jobs)} cached jobs")
        for j in cached_jobs:
            j.pop("rag_score", None)
            j.pop("rag_error", None)
        new_jobs = cached_jobs + new_jobs
        cached_jobs = []
    to_parse = [j for j in new_jobs if not j.get("parsed")]
    already_parsed = [j for j in new_jobs if j.get("parsed")]
    n_parsed = len(to_parse)
    if to_parse:
        to_parse = parse_all(to_parse, model="gpt-4o-mini")
    else:
        print("   No new jobs to parse.")
    return cached_jobs, already_parsed + to_parse, cache, n_parsed


def _gate_and_score(new_jobs: list, profile: dict, skip_scoring: bool) -> tuple[list, list, int]:
    """Steps 4b–5: heuristic gate, RAG score, gap tracking. Returns (scored, heuristic_only, n_scored)."""
    jobs_to_score, heuristic_only = _heuristic_gate(new_jobs, profile)
    if heuristic_only:
        logger.info("heuristic_gate", to_score=len(jobs_to_score), heuristic_only=len(heuristic_only))
        print(f"\n🔍 Heuristic gate: {len(jobs_to_score)} → RAG, {len(heuristic_only)} → heuristic-only")
    if len(jobs_to_score) > MAX_SCORE_PER_RUN:
        over = len(jobs_to_score) - MAX_SCORE_PER_RUN
        logger.warning("score_cap_applied", total=len(jobs_to_score), cap=MAX_SCORE_PER_RUN, deferred=over)
        print(f"\n⚠️  {len(jobs_to_score)} jobs past gate — capping at {MAX_SCORE_PER_RUN} to limit cost.")
        print(f"   Remaining {over} jobs will be scored in future runs.")
        heuristic_only.extend(jobs_to_score[MAX_SCORE_PER_RUN:])
        jobs_to_score = jobs_to_score[:MAX_SCORE_PER_RUN]
    n_scored = 0
    if jobs_to_score and not skip_scoring:
        try:
            from vectorstore import build_vectorstore  # noqa: PLC0415
            from scorer import score_all  # noqa: PLC0415

            jobs_to_score = score_all(jobs_to_score, build_vectorstore(profile=profile), profile=profile)
            n_scored = sum(1 for j in jobs_to_score if j.get("rag_score"))
        except Exception as e:
            logger.error("rag_score_error", error=str(e), exc_info=True)
            print(f"\nRAG scoring error (continuing with heuristic only): {e}")
        _track_gaps(jobs_to_score, profile)
    return jobs_to_score, heuristic_only, n_scored


def _track_gaps(scored_jobs: list, profile: dict) -> None:
    """Step 5b: persist gap/strength data for trend analysis."""
    scored = [j for j in scored_jobs if j.get("rag_score")]
    if not scored:
        return
    try:
        from gap_tracker import append_gap_history  # noqa: PLC0415

        n_gaps = append_gap_history(scored, profile)
        if n_gaps:
            print(f"   Gap history: +{n_gaps} entries")
    except Exception as e:
        print(f"   Gap history error (non-fatal): {e}")


def _log_completion(
    profile_id: str, mode: str, start_time: float, all_parsed: list, cache: dict, n_parsed: int, n_scored: int
) -> tuple[int, float]:
    """Log pipeline completion stats. Returns (duration_s, cost_usd)."""
    duration_s = int(time.time() - start_time)
    cost_usd = round(n_parsed * 0.001 + n_scored * 0.04, 3)
    tier_a = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "A")
    tier_b = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "B")
    tier_c = sum(1 for j in all_parsed if (j.get("rag_score") or {}).get("tier") == "C")
    kw = dict(
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
    logger.info("pipeline_complete", **kw)
    _capture(profile_id, "agent_pipeline_complete", {"mode": mode, "status": "success", **kw})
    print(f"\n✅ Done in {duration_s}s. Cache: {cache_stats(cache)}")
    if cost_usd > 0:
        print(f"   Estimated cost: ${cost_usd:.3f} ({n_parsed} parsed, {n_scored} scored)")
    return duration_s, cost_usd


def _early_exit(profile_id: str, mode: str, start_time: float, status: str) -> None:
    """Log and emit pipeline_complete for early-exit scenarios."""
    d = int(time.time() - start_time)
    msg = (
        "No jobs found. Check your search config."
        if status == "no_jobs"
        else "All jobs filtered out. Loosen your preferences."
    )
    print(f"\n{msg}")
    ev = {"profile_id": profile_id, "mode": mode, "duration_s": d, "status": status, "n_parsed": 0, "n_scored": 0}
    logger.info("pipeline_complete", **ev)
    _capture(profile_id, "agent_pipeline_complete", ev)


def _sync_to_railway(jobs: list, profile_id: str, railway_url: str, ingest_key: str) -> bool:
    """POST jobs to /api/ingest so GET /api/digest/{profile_id} has today's data (Step 10b).

    Returns True on success, False on failure. Caller continues regardless.
    """
    url = railway_url.rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    endpoint = f"{url}/api/ingest"
    try:
        resp = httpx.post(
            endpoint,
            json={"jobs": jobs, "profile_id": profile_id},
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


def _send_digest(
    profile_id: str, paths: dict, profile: dict, prefilter_stats: dict, duration_s: int, cost_usd: float
) -> bool:
    """Step 11: fetch digest from API and send email. Returns True if sent."""
    import yaml  # noqa: PLC0415

    railway_url = os.environ.get("RAILWAY_URL", "")
    ingest_key = os.environ.get("INGEST_API_KEY", "")
    if not railway_url or not ingest_key:
        print("⚠  RAILWAY_URL or INGEST_API_KEY not set — skipping email digest")
        return False

    n_searches = 0
    n_watchlist = 0
    try:
        with open(paths["watchlist"]) as f:
            wl = yaml.safe_load(f) or {}
            n_watchlist = len(wl.get("greenhouse", []) or []) + len(wl.get("lever", []) or [])
    except Exception:
        pass

    from notifier import send_digest  # noqa: PLC0415

    run_meta = {
        "duration_s": duration_s,
        "cost_usd": cost_usd,
        "n_searches": n_searches,
        "n_watchlist": n_watchlist,
        "date": datetime.now().strftime("%d %b %Y"),
    }
    return send_digest(
        railway_url=railway_url,
        profile_id=profile_id,
        ingest_key=ingest_key,
        rejected_stats=prefilter_stats,
        run_meta=run_meta,
        profile=profile,
    )


def run_pipeline(
    profile_id: str,
    profile: dict,
    paths: dict,
    opts: PipelineOptions,
    pre_scraped_jobs: list[dict] | None = None,
) -> None:
    """Run the full agent pipeline for one user profile.

    pre_scraped_jobs: when provided (unified scraping mode), skip _scrape_all()
                      and use the supplied job list directly.
    """
    from geo import derive_target_countries  # noqa: PLC0415

    start_time = time.time()
    home_locs = profile.get("user", {}).get("home_locations", [])
    target_countries = derive_target_countries(home_locs) or profile.get("target", {}).get("wttj_countries") or []

    logger.info("pipeline_start", profile_id=profile_id, mode=opts.mode, notify=opts.send_email)
    _capture(
        profile_id, "agent_pipeline_start", {"profile_id": profile_id, "mode": opts.mode, "notify": opts.send_email}
    )

    print(f"JobAgent - Phase 2: Scrape > Pre-filter > Parse > RAG Score > Rank  [{profile_id}]")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if opts.full_refresh:
        print("(--refresh: cache cleared, full reprocess)")
    elif opts.rescore_only:
        print("(--rescore: keeping parsed data, redoing RAG scores)")
    elif opts.skip_scoring:
        print("(--no-score: heuristic only)")
    if opts.send_email:
        print("(--notify: email digest will be sent)")
    print("=" * 70)

    if pre_scraped_jobs is not None:
        jobs = pre_scraped_jobs
        geo_rejected = 0
        print(f"\n(Using pre-scraped pool: {len(jobs)} jobs)")
    else:
        jobs, geo_rejected = _scrape_all(profile, paths, target_countries)
    railway_url = os.environ.get("RAILWAY_URL", "")
    ingest_key = os.environ.get("INGEST_API_KEY", "")

    if not jobs:
        return _early_exit(profile_id, opts.mode, start_time, "no_jobs")

    # Step 1d: load seen_ids from Railway DB for prefilter dedup
    seen_ids: set[str] = set()
    if railway_url and ingest_key:
        try:
            seen_ids = fetch_seen_ids(railway_url, ingest_key, profile_id)
            logger.info("seen_ids_loaded", profile_id=profile_id, count=len(seen_ids))
        except RuntimeError as e:
            logger.warning("seen_ids_load_failed", profile_id=profile_id, error=str(e))
            print(f"⚠  Failed to load seen IDs from Railway (will show all jobs): {e}")

    passed, rejected, prefilter_stats = _run_prefilter(jobs, profile, paths, target_countries, geo_rejected, seen_ids)
    _emit_geo_events(profile_id, rejected, prefilter_stats, geo_rejected)
    if not passed:
        return _early_exit(profile_id, opts.mode, start_time, "all_filtered")

    cache = {} if opts.full_refresh else load_cache()
    cached_jobs, new_jobs, cache, n_parsed = _load_and_parse(passed, cache, opts.full_refresh, opts.rescore_only)
    scored_jobs, heuristic_only, n_scored = _gate_and_score(new_jobs, profile, opts.skip_scoring)

    all_new = scored_jobs + heuristic_only
    if all_new:
        added = update_cache(cache, all_new)
        save_cache(cache)
        logger.info("cache_updated", jobs_added=added)
        print(f"   Cache updated: +{added} jobs ({cache_stats(cache)})")

    all_parsed = cached_jobs + scored_jobs + heuristic_only
    _auto_skip_reloc(all_parsed)
    print_summary(all_parsed)
    duration_s, cost_usd = _log_completion(profile_id, opts.mode, start_time, all_parsed, cache, n_parsed, n_scored)

    save_results(all_parsed, profile_id=profile_id)
    if rejected:
        save_results(rejected, folder="output/rejected", profile_id=profile_id)

    # Step 10b: sync to Railway before email so GET /api/digest/{profile_id} has today's data.
    if railway_url and ingest_key:
        _sync_to_railway(all_parsed, profile_id, railway_url, ingest_key)

    # Step 10c: persist seen IDs to Railway DB (replaces file-based seen_ids)
    if railway_url and ingest_key:
        new_ids = [j["id"] for j in all_parsed if j.get("id")]
        if new_ids:
            try:
                added = post_seen_ids(railway_url, ingest_key, profile_id, new_ids)
                logger.info("seen_ids_synced", profile_id=profile_id, count=added)
                print(f"   Seen IDs: +{added} new IDs persisted to Railway DB")
            except RuntimeError as e:
                logger.warning("seen_ids_sync_failed", profile_id=profile_id, error=str(e))
                print(f"⚠  Seen IDs sync failed (non-fatal): {e}")

    email_sent = False
    if opts.send_email:
        try:
            email_sent = _send_digest(profile_id, paths, profile, prefilter_stats, duration_s, cost_usd)
            if not email_sent:
                logger.warning("email_skipped", profile_id=profile_id)
                print("⚠  Email not sent — check GMAIL_*, RAILWAY_URL, and INGEST_API_KEY env vars")
        except Exception as e:
            logger.error("email_error", error=str(e), exc_info=True)
            print(f"⚠  Email notify error (pipeline succeeded): {e}")
        _capture(profile_id, "agent_email_sent", {"profile_id": profile_id, "sent": email_sent})
