-- Migration 023: seen_job_ids table
-- Replaces file-based config/seen_ids/*.txt per-user seen job tracking.
-- Indexed by profile_id for fast per-user lookups.
CREATE TABLE IF NOT EXISTS seen_job_ids (
    profile_id TEXT NOT NULL,
    job_id     TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (profile_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_job_ids_profile ON seen_job_ids(profile_id);
