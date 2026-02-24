-- Migration 006: persist cv_md in users table so it survives redeploys
ALTER TABLE users ADD COLUMN cv_md TEXT;
