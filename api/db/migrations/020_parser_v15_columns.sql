-- Migration 020: parser v1.5 columns
-- Adds high-value parsed fields as real columns for filtering/display
-- without JSON parsing. Other v1.5 fields (verbatim_for_cv, truly_required,
-- preferred_skills, company_context.what_they_value) stay in the parsed JSON blob.

ALTER TABLE jobs ADD COLUMN role_in_plain_english TEXT;
ALTER TABLE jobs ADD COLUMN company_stage TEXT;
ALTER TABLE jobs ADD COLUMN company_tone TEXT;
