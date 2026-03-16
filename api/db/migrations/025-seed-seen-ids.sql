-- Migration 025: seed seen_job_ids from all existing jobs for active users
--
-- Context: Phase UID migration (024) renamed profile_id→user_id but the
-- file-based seen_ids history (config/seen_ids/*.txt) was never loaded
-- into the DB table. After Phase UID, seen_job_ids had only ~50 entries
-- (from runs since March 11). This left hundreds of old jobs not in seen_ids,
-- causing them to pass prefilter every day, be re-synced to Railway with
-- their original first_seen dates, and produce empty digests.
--
-- Fix: seed seen_job_ids with ALL current jobs for every active user.
-- "Active user" = has at least one entry in seen_job_ids or user_job_scores
-- (i.e., has been processed by the agent at least once since Phase UID).
-- After this migration, only genuinely new jobs (not yet in the jobs table)
-- will pass the prefilter and appear in the digest.

INSERT OR IGNORE INTO seen_job_ids (user_id, job_id)
SELECT DISTINCT active_users.user_id, j.job_id
FROM (
    SELECT DISTINCT user_id FROM seen_job_ids
    UNION
    SELECT DISTINCT user_id FROM user_job_scores
) AS active_users
CROSS JOIN jobs j;
