-- Migration 022: Async CV processing state
ALTER TABLE users ADD COLUMN cv_processing_status TEXT DEFAULT NULL;
ALTER TABLE users ADD COLUMN cv_processing_started_at TEXT DEFAULT NULL;
ALTER TABLE users ADD COLUMN cv_pending_result TEXT DEFAULT NULL;
