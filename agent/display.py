"""Job display, ranking, and auto-skip functions for agent pipeline.

Reads scoring globals via the scoring module object so updates from
scoring.load_heuristic_config() are always reflected at call time.

Exports (public):
  ranked_jobs(jobs)               — sort into tier_a, tier_b, tier_c
  print_summary(jobs)             — print tiered digest to stdout
  auto_skip_reloc(jobs, ...)      — auto-add low-score reloc to not_interested
"""

import os

import scoring as _scoring_mod
from shared.scoring_core import grade_to_points as _grade_to_points
from reloc import is_reloc as _is_reloc
from salary import extract_max_salary_eur as _extract_max_salary_eur
from scoring import heuristic_score as _heuristic_score


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

    if salary_eur >= _scoring_mod._SALARY_THRESHOLD:
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
        must_have = (p.get("truly_required") or p.get("must_have_skills") or [])[:3]
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

    def _print_tier(label, tier_jobs, counter):
        if not tier_jobs:
            return counter
        print(f"\n{'─' * 70}")
        print(f"  {label} ({len(tier_jobs)} jobs)")
        print(f"{'─' * 70}")
        reloc_header_shown = False
        for job in tier_jobs:
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


def auto_skip_reloc(jobs, applied_path="config/applied.yaml"):
    """Auto-add low-score reloc jobs to not_interested.ids.

    A reloc job that doesn't reach Tier A (score ≤ 60) is not worth relocating
    for — skip it permanently so it never costs parse/score tokens again.
    """
    import yaml  # noqa: PLC0415

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
