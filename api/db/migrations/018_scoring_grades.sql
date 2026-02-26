-- Migration 018: add LLM grade columns to user_job_scores
-- technical_grade and profile_grade store A/B/C from scoring-rubric-v2.md
-- scored_v2 flags rows scored with rubric v2 (for hybrid_score to detect)

ALTER TABLE user_job_scores ADD COLUMN technical_grade TEXT;
ALTER TABLE user_job_scores ADD COLUMN profile_grade TEXT;
ALTER TABLE user_job_scores ADD COLUMN scored_v2 INTEGER NOT NULL DEFAULT 0;
