-- Migration 007: persist profile YAML in users table so it survives redeploys
ALTER TABLE users ADD COLUMN profile_yaml TEXT;
