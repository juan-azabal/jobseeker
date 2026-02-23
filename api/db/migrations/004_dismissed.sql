-- Add dismissed_at to user_job_status to track jobs the user skipped/rejected.
-- Dismissed jobs are hidden from normal A/B views and stored as negative
-- training examples for future scorer calibration.
ALTER TABLE user_job_status ADD COLUMN dismissed_at TEXT;
