"""
RawJob: standardised intermediate representation of a scraped job posting.

Each scraper (JobSpy, WTTJ, ATS) produces list[RawJob]. After merge,
the pipeline converts to dicts for downstream (prefilter, parser, scorer).

All fields optional except: id, title, company, source.
Extra fields from sources are ignored (model_config extra='ignore').
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


#: Known source identifiers — one per scraper origin.
VALID_SOURCES = frozenset({"indeed", "linkedin", "google", "glassdoor", "greenhouse", "lever", "ashby", "wttj"})


class RawJob(BaseModel):
    """Standardised scraped job record, source-specific fields included.

    Produced by each scraper before merge. Post-merge, `sources` lists all
    origin scrapers for this job.
    """

    model_config = ConfigDict(extra="ignore")

    # ── Required ─────────────────────────────────────────────────────────────
    id: str
    title: str
    company: str
    source: str  # one of VALID_SOURCES

    # ── Core job fields ───────────────────────────────────────────────────────
    job_url: str | None = None
    location: str | None = None  # display string (e.g. "Barcelona, Spain")
    description: str | None = None
    job_type: str | None = None
    date_posted: str | None = None
    search_term_used: str | None = None

    # ── Remote / location type ────────────────────────────────────────────────
    remote_type: str | None = None  # "fulltime" | "partial" | "no" | None

    # ── Structured location (from WTTJ offices[]; null from JobSpy) ──────────
    country: str | None = None  # ISO 2-letter code (e.g. "ES")
    city: str | None = None
    state: str | None = None
    locations_structured: list[dict] | None = None  # raw offices[] from WTTJ

    # ── Salary ────────────────────────────────────────────────────────────────
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    interval: str | None = None  # "yearly" | "monthly" | "hourly"
    salary_source: str | None = None  # "direct_data" | "description" | None

    # ── Company metadata (mostly Indeed + LinkedIn) ───────────────────────────
    company_url: str | None = None
    company_industry: str | None = None
    company_employees_label: str | None = None  # JobSpy: company_num_employees
    company_revenue_label: str | None = None  # JobSpy: company_revenue
    company_logo: str | None = None

    # ── Role metadata ─────────────────────────────────────────────────────────
    job_level: str | None = None  # LinkedIn: "Mid-Senior Level", "Director", …
    job_function: str | None = None  # LinkedIn/JobSpy job_function field

    # ── Experience (WTTJ structured) ─────────────────────────────────────────
    experience_min: int | None = None
    experience_max: int | None = None

    # ── Language (WTTJ) ──────────────────────────────────────────────────────
    language: str | None = None

    # ── Org structure (ATS) ───────────────────────────────────────────────────
    departments: list[str] | None = None
    team: str | None = None

    # ── Contact ───────────────────────────────────────────────────────────────
    emails: list[str] | None = None

    # ── Merge tracking ────────────────────────────────────────────────────────
    sources: list[str] = Field(default_factory=list)
    # All original titles collected when cross-geo variants merge into one record.
    # None for single-source jobs; populated by merger when len(group) > 1.
    title_variants: list[str] | None = None
    # Category reference from WTTJ Algolia (new_profession.sub_category_reference)
    source_category: str | None = None

    # ── Computed ──────────────────────────────────────────────────────────────
    @computed_field  # type: ignore[misc]
    @property
    def is_remote(self) -> bool:
        """Backward-compatible remote flag derived from remote_type."""
        return self.remote_type in ("fulltime", "partial")
