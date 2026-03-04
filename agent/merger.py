"""
Job merger: combines duplicate RawJob objects from different scrapers.

Each job source has strengths for different field groups. When two scrapers
return the same job (same make_job_id), this module merges them by selecting
the best available data per field group rather than discarding duplicates.

Usage:
    from merger import merge_jobs
    merged: list[RawJob] = merge_jobs(all_raw_jobs)
"""

import re
from collections import defaultdict

from models import RawJob


# Source priority: lower number = higher priority (ATS > structured > social > generic)
SOURCE_RANK: dict[str, int] = {
    "greenhouse": 1,
    "lever": 2,
    "ashby": 3,
    "wttj": 4,
    "linkedin": 5,
    "indeed": 6,
    "glassdoor": 7,
    "google": 8,
}


# For each field group, the preferred source order (first = highest priority)
FIELD_GROUPS: dict[str, list[str]] = {
    "description": ["greenhouse", "lever", "ashby", "linkedin", "wttj", "indeed", "glassdoor", "google"],
    "salary": ["wttj", "indeed", "glassdoor", "linkedin", "google", "greenhouse", "lever", "ashby"],
    "company_meta": ["indeed", "glassdoor", "linkedin", "wttj", "greenhouse", "lever", "ashby", "google"],
    "job_level": ["linkedin", "indeed", "wttj", "greenhouse", "lever", "ashby", "glassdoor", "google"],
    "remote_type": ["wttj", "linkedin", "indeed", "glassdoor", "google", "greenhouse", "lever", "ashby"],
    "org_structure": ["greenhouse", "lever", "ashby", "wttj", "linkedin", "indeed", "glassdoor", "google"],
    "location": ["indeed", "linkedin", "glassdoor", "google", "wttj", "greenhouse", "lever", "ashby"],
}

# Which group each field belongs to (fields not listed use SOURCE_RANK directly)
FIELD_TO_GROUP: dict[str, str] = {
    # description group
    "description": "description",
    # salary group
    "min_amount": "salary",
    "max_amount": "salary",
    "currency": "salary",
    "interval": "salary",
    "salary_source": "salary",
    # company_meta group
    "company_industry": "company_meta",
    "company_employees_label": "company_meta",
    "company_revenue_label": "company_meta",
    "company_url": "company_meta",
    "company_logo": "company_meta",
    # job_level group
    "job_level": "job_level",
    # remote_type group (WTTJ knows remote best + has experience data)
    "remote_type": "remote_type",
    "experience_min": "remote_type",
    "experience_max": "remote_type",
    # org_structure group
    "departments": "org_structure",
    "team": "org_structure",
    # location group
    "country": "location",
    "city": "location",
    "state": "location",
    # locations_structured group (list field — unioned, but WTTJ has it)
    "locations_structured": "location",
}

# Fields that are merged by union (not winner-takes-all)
_LIST_FIELDS = {"departments", "locations_structured", "emails"}

# Fields that are fixed per job (not merged — always taken from best-rank source)
# title_variants is also excluded from the generic loop: it is set explicitly
# in _merge_group_of_jobs() by collecting all original titles from the group.
_IDENTITY_FIELDS = {"id", "title", "company", "source", "sources", "title_variants"}


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def _has_html(text: str) -> bool:
    """Return True if text contains HTML tags."""
    return bool(re.search(r"<[^>]+>", text))


def _description_score(text: str | None) -> tuple[bool, int]:
    """Return (is_plain, char_length) for description comparison.

    Plain text is preferred over HTML. Within same type, longer wins.
    """
    if not text:
        return (True, 0)
    plain = not _has_html(text)
    length = len(_strip_html(text))
    return (plain, length)


def _source_priority(source: str) -> int:
    """Return sort key — lower is better. Unknown sources go last."""
    return SOURCE_RANK.get(source, 99)


def _group_priority_order(group: str, sources_present: list[str]) -> list[str]:
    """Return sources present in this group's preference order."""
    order = FIELD_GROUPS.get(group, [])
    present_set = set(sources_present)
    return [s for s in order if s in present_set]


def _merge_group(group: RawJob, jobs_by_source: dict[str, RawJob], field: str) -> object:
    """Pick the best value for a grouped field from the available sources."""
    source_order = _group_priority_order(FIELD_TO_GROUP[field], list(jobs_by_source))
    for source in source_order:
        val = getattr(jobs_by_source[source], field, None)
        if val is not None:
            return val
    return None


def _merge_description(jobs_by_source: dict[str, RawJob]) -> str | None:
    """Special merge for description: prefer longer plain text over HTML."""
    candidates = []
    for source, job in jobs_by_source.items():
        if job.description:
            is_plain, length = _description_score(job.description)
            candidates.append((is_plain, length, job.description))
    if not candidates:
        return None
    # Sort: prefer plain (True > False), then longer length
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def _merge_list_field(all_jobs: list[RawJob], field: str) -> list | None:
    """Union list fields across all jobs (deduped for string lists).

    Uses all_jobs (not deduplicated by source) so that same-source duplicates
    (e.g. two WTTJ entries with different offices) are both included.
    """
    result = []
    seen: set = set()

    for job in all_jobs:
        val = getattr(job, field, None)
        if val is None:
            continue
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    if item not in seen:
                        seen.add(item)
                        result.append(item)
                else:
                    # Non-string items (dicts etc.) appended without dedup
                    result.append(item)

    return result if result else None


def _merge_ungrouped_field(jobs_by_source: dict[str, RawJob], field: str) -> object:
    """For fields outside FIELD_TO_GROUP, use the best-ranked source with a value."""
    for source in sorted(jobs_by_source, key=_source_priority):
        val = getattr(jobs_by_source[source], field, None)
        if val is not None:
            return val
    return None


def _merge_group_of_jobs(jobs: list[RawJob]) -> RawJob:
    """Merge a group of RawJob objects with the same id into one."""
    if len(jobs) == 1:
        job = jobs[0]
        if not job.sources:
            # Populate sources on single-source jobs
            object.__setattr__(job, "sources", [job.source])
        return job

    # Build lookup: source → job (best-ranked job per source for scalar fields)
    # Keep all_jobs list for list-field union (handles same-source duplicates)
    jobs_by_source: dict[str, RawJob] = {}
    for j in sorted(jobs, key=lambda j: _source_priority(j.source)):
        jobs_by_source[j.source] = j
    all_jobs = sorted(jobs, key=lambda j: _source_priority(j.source))

    # Use the best-ranked job as the base for identity fields
    best_source = min(jobs_by_source, key=_source_priority)
    base = jobs_by_source[best_source]

    # Collect all unique original titles (preserves cross-geo variant record)
    all_titles = sorted(set(j.title for j in jobs))

    # Collect all fields to merge
    kwargs: dict = {
        "id": base.id,
        "title": base.title,
        "company": base.company,
        "source": base.source,
        "sources": sorted(jobs_by_source.keys(), key=_source_priority),
        "title_variants": all_titles,
    }

    # Get all field names from the model (excluding computed and identity fields)
    all_fields = set(RawJob.model_fields.keys()) - _IDENTITY_FIELDS

    for field in all_fields:
        if field in _LIST_FIELDS:
            kwargs[field] = _merge_list_field(all_jobs, field)
        elif field == "description":
            kwargs[field] = _merge_description(jobs_by_source)
        elif field in FIELD_TO_GROUP:
            kwargs[field] = _merge_group(None, jobs_by_source, field)
        else:
            kwargs[field] = _merge_ungrouped_field(jobs_by_source, field)

    return RawJob(**kwargs)


def merge_jobs(jobs: list[RawJob]) -> list[RawJob]:
    """Merge duplicate RawJob objects (same id) from multiple scrapers.

    Groups by job id, merges each group using source-group field priority,
    returns one RawJob per unique job with the richest available data.

    Args:
        jobs: Raw jobs from all scrapers, may contain duplicates.

    Returns:
        list[RawJob] with one entry per unique job id.
    """
    if not jobs:
        return []

    groups: dict[str, list[RawJob]] = defaultdict(list)
    for job in jobs:
        groups[job.id].append(job)

    result = []
    for job_id, group in groups.items():
        result.append(_merge_group_of_jobs(group))

    return result
