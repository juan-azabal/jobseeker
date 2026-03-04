"""
Regression test: cross-geo Greenhouse deduplication.

Before the fix, "Senior PM | Canada | Remote" and "Senior PM | Spain | Remote"
from the same company produced different job_ids and were never merged.
After the fix, _normalize_for_id strips the geo suffix before hashing, so
both variants collapse to a single merged RawJob.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RawJob
from scraper import make_job_id
from merger import merge_jobs


COMPANY = "Grafana Labs"
TITLE_CA = "Senior PM | Canada | Remote"
TITLE_ES = "Senior PM | Spain | Remote"
TITLE_EMEA = "Staff Engineer | EMEA | Hybrid"
TITLE_EMEA_ONSITE = "Staff Engineer | EMEA | On-site"


class TestCrossGeoDedup:
    def test_cross_geo_titles_produce_same_id(self):
        """Geo-variant titles hash identically after suffix stripping."""
        assert make_job_id(TITLE_CA, COMPANY) == make_job_id(TITLE_ES, COMPANY)

    def test_cross_geo_merge_produces_single_job(self):
        """Two Greenhouse jobs for the same role in different geos merge to one."""
        shared_id = make_job_id(TITLE_CA, COMPANY)

        job_ca = RawJob(id=shared_id, title=TITLE_CA, company=COMPANY, source="greenhouse")
        job_es = RawJob(id=shared_id, title=TITLE_ES, company=COMPANY, source="greenhouse")

        result = merge_jobs([job_ca, job_es])

        assert len(result) == 1, f"Expected 1 merged job, got {len(result)}"

    def test_merged_job_has_both_title_variants(self):
        """Merged record retains both original geo-variant titles."""
        shared_id = make_job_id(TITLE_CA, COMPANY)

        job_ca = RawJob(id=shared_id, title=TITLE_CA, company=COMPANY, source="greenhouse")
        job_es = RawJob(id=shared_id, title=TITLE_ES, company=COMPANY, source="greenhouse")

        merged = merge_jobs([job_ca, job_es])[0]

        assert merged.title_variants is not None
        assert TITLE_CA in merged.title_variants
        assert TITLE_ES in merged.title_variants

    def test_distinct_roles_not_merged(self):
        """Different roles at same company still produce distinct jobs."""
        id_pm = make_job_id("Senior PM", COMPANY)
        id_eng = make_job_id("Staff Engineer", COMPANY)
        assert id_pm != id_eng

        job_pm = RawJob(id=id_pm, title="Senior PM", company=COMPANY, source="greenhouse")
        job_eng = RawJob(id=id_eng, title="Staff Engineer", company=COMPANY, source="greenhouse")

        result = merge_jobs([job_pm, job_eng])
        assert len(result) == 2

    def test_hybrid_and_onsite_same_role_merge(self):
        """Same role with Hybrid vs On-site work mode also deduplicates."""
        assert make_job_id(TITLE_EMEA, COMPANY) == make_job_id(TITLE_EMEA_ONSITE, COMPANY)
