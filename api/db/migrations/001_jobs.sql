CREATE TABLE IF NOT EXISTS jobs (
  job_id        TEXT PRIMARY KEY,
  title         TEXT,
  company       TEXT,
  location      TEXT,
  url           TEXT,
  location_type TEXT,
  domain        TEXT,
  score         INTEGER,
  tier          TEXT,
  parsed        TEXT,
  scored        TEXT,
  first_seen    TEXT,
  last_seen     TEXT,
  ingested_at   TEXT
);
