-- Migration 021: Master CV JSON — structured career history
ALTER TABLE users ADD COLUMN master_cv_json TEXT;
