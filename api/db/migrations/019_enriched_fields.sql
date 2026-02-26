-- Migration 019: add enriched scraper fields to jobs table
-- These fields come from RawJob (structured scraper data) and are persisted
-- to avoid re-extraction on every query. Nullable: not all scrapers provide all fields.
-- On upsert conflict: COALESCE preserves richer data (see queries.upsert_job).

ALTER TABLE jobs ADD COLUMN company_url TEXT;
ALTER TABLE jobs ADD COLUMN company_logo TEXT;
ALTER TABLE jobs ADD COLUMN company_industry TEXT;
ALTER TABLE jobs ADD COLUMN company_size TEXT;
ALTER TABLE jobs ADD COLUMN job_level TEXT;
ALTER TABLE jobs ADD COLUMN salary_min REAL;
ALTER TABLE jobs ADD COLUMN salary_max REAL;
ALTER TABLE jobs ADD COLUMN salary_currency TEXT;
ALTER TABLE jobs ADD COLUMN salary_interval TEXT;
ALTER TABLE jobs ADD COLUMN salary_source TEXT;
ALTER TABLE jobs ADD COLUMN country TEXT;
ALTER TABLE jobs ADD COLUMN city TEXT;
ALTER TABLE jobs ADD COLUMN remote_type TEXT;
ALTER TABLE jobs ADD COLUMN sources TEXT;  -- JSON array of scraper origins
