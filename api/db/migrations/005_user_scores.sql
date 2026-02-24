-- Per-user scoring: move score/tier/scored from jobs (global) to user_job_scores (per-user).
-- SQLite doesn't support DROP COLUMN before 3.35, so recreate the table.

CREATE TABLE IF NOT EXISTS jobs_new (
  job_id        TEXT PRIMARY KEY,
  title         TEXT,
  company       TEXT,
  location      TEXT,
  url           TEXT,
  location_type TEXT,
  domain        TEXT,
  parsed        TEXT,
  first_seen    TEXT,
  last_seen     TEXT,
  ingested_at   TEXT
);

INSERT OR IGNORE INTO jobs_new (job_id, title, company, location, url, location_type, domain, parsed, first_seen, last_seen, ingested_at)
SELECT job_id, title, company, location, url, location_type, domain, parsed, first_seen, last_seen, ingested_at
FROM jobs;

DROP TABLE IF EXISTS jobs;
ALTER TABLE jobs_new RENAME TO jobs;

CREATE TABLE IF NOT EXISTS user_job_scores (
  user_id    INTEGER REFERENCES users(id),
  job_id     TEXT    REFERENCES jobs(job_id),
  score      INTEGER NOT NULL,
  tier       TEXT    NOT NULL,
  scored     TEXT,
  scored_at  TEXT    NOT NULL,
  PRIMARY KEY (user_id, job_id)
);
