-- Migration 014: Add domain_override column to user_job_status
-- Allows users to correct the parser-assigned domain on a per-job basis.
-- NULL means no override (use the parsed domain cascade as usual).
ALTER TABLE user_job_status ADD COLUMN domain_override TEXT;
