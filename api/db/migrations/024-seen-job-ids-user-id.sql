-- Migration 024: seen_job_ids — replace profile_id (TEXT) with user_id (INTEGER)
--
-- Strategy: rename existing table → populate user_id from users → delete orphans
-- → recreate with user_id PK → copy clean rows → drop temp table.
-- SQLite does not support DROP COLUMN or ALTER TABLE for PK changes.

-- Step 1: rename old table
ALTER TABLE seen_job_ids RENAME TO seen_job_ids_old;

-- Step 2: add user_id column to old table and populate from users
ALTER TABLE seen_job_ids_old ADD COLUMN user_id INTEGER;

UPDATE seen_job_ids_old
SET user_id = (
    SELECT id FROM users WHERE users.profile_id = seen_job_ids_old.profile_id
);

-- Step 3: delete orphaned rows (profile_id had no matching user)
DELETE FROM seen_job_ids_old WHERE user_id IS NULL;

-- Step 4: recreate table with user_id as part of the PK
CREATE TABLE seen_job_ids (
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id        TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_job_ids_user ON seen_job_ids(user_id);

-- Step 5: copy clean rows
INSERT INTO seen_job_ids (user_id, job_id, first_seen_at)
SELECT user_id, job_id, first_seen_at FROM seen_job_ids_old;

-- Step 6: drop temp table
DROP TABLE seen_job_ids_old;
