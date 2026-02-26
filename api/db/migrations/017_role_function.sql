-- Migration 017: add role_function column to jobs table
-- Backfills from parsed JSON where available.

ALTER TABLE jobs ADD COLUMN role_function TEXT;

UPDATE jobs
SET role_function = json_extract(parsed, '$.role_function')
WHERE parsed IS NOT NULL AND role_function IS NULL;
