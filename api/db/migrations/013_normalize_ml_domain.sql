-- Migration 013: Normalize legacy domain values in jobs table
-- ml → ai_ml (parser enum rename from v1.2 to v1.3)
-- healthcare → healthtech (parser enum rename from v1.2 to v1.3)
-- game → gaming (parser enum rename from v1.2 to v1.3)
-- security → cybersecurity (parser enum rename from v1.2 to v1.3)
-- Idempotent: safe to run multiple times.

UPDATE jobs
SET parsed = json_set(parsed, '$.domain', 'ai_ml')
WHERE json_extract(parsed, '$.domain') = 'ml'
  AND parsed IS NOT NULL;

UPDATE jobs SET domain = 'ai_ml' WHERE domain = 'ml';

UPDATE jobs
SET parsed = json_set(parsed, '$.domain', 'healthtech')
WHERE json_extract(parsed, '$.domain') = 'healthcare'
  AND parsed IS NOT NULL;

UPDATE jobs SET domain = 'healthtech' WHERE domain = 'healthcare';

UPDATE jobs
SET parsed = json_set(parsed, '$.domain', 'gaming')
WHERE json_extract(parsed, '$.domain') = 'game'
  AND parsed IS NOT NULL;

UPDATE jobs SET domain = 'gaming' WHERE domain = 'game';

UPDATE jobs
SET parsed = json_set(parsed, '$.domain', 'cybersecurity')
WHERE json_extract(parsed, '$.domain') = 'security'
  AND parsed IS NOT NULL;

UPDATE jobs SET domain = 'cybersecurity' WHERE domain = 'security';
