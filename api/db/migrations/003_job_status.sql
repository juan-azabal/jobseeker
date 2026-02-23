CREATE TABLE IF NOT EXISTS user_job_status (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id     TEXT    NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
  applied_at TEXT,
  PRIMARY KEY (user_id, job_id)
);
