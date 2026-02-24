-- Enforce that each profile_id belongs to exactly one user.
-- SQLite does not support ADD CONSTRAINT on existing tables, so we use
-- a UNIQUE index instead (equivalent enforcement, works on existing tables).
--
-- NOTE: This will FAIL at runtime if duplicate profile_ids exist in the DB.
-- Fix duplicates first via the admin set-profile-id endpoint before deploying.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_profile_id_unique
    ON users (profile_id)
    WHERE profile_id IS NOT NULL;
