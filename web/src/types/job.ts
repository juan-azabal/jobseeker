export interface JobSummary {
  job_id: string;
  title: string;
  company: string;
  location: string;
  location_type: string;
  domain: string | null;
  score: number;
  tier: 'A' | 'B' | 'C';
  first_seen: string;
  last_seen?: string;
  url: string;
  applied_at: string | null;
  geo_restricted: boolean;  // true = remote restriction excludes user's home region
  eligibility_warning?: string | null;
  // Parser v1.5 fields (conditionally present when non-null)
  role_in_plain_english?: string;
  company_stage?: string;
  company_tone?: string;
  truly_required?: string[];
  preferred_skills?: string[];
  verbatim_for_cv?: string[];
  company_context?: CompanyContext;
}

export interface ScoreBreakdown {
  domain_fit: number;
  seniority_fit: number;
  technical_depth: number;
  profile_evidence: number;
  strategic_impact: number;
}

export interface Strength {
  claim: string;
  evidence: string;
}

export interface Gap {
  gap: string;
  severity: 'high' | 'medium' | 'low';
  category?: string;
  mitigation?: string;
}

export interface ScoredResult {
  score: number;
  score_breakdown: ScoreBreakdown;
  strengths: Strength[];
  gaps: Gap[];
  deal_breakers?: string[];
  talking_points?: string[];
  stories_to_prepare?: string[];
  one_line_verdict?: string;
}

export interface CompanyContext {
  stage?: string;
  what_they_value?: string[];
  tone?: string;
}

export interface ParsedJob {
  seniority?: string;
  years_experience_min?: number | null;
  years_experience_max?: number | null;
  location_type?: string;
  locations_mentioned?: string[];
  // v1.5 field names (new)
  truly_required?: string[];
  preferred_skills?: string[];
  // backward-compat field names (old jobs in DB)
  must_have_skills?: string[];
  nice_to_have_skills?: string[];
  technical_stack?: string[];
  experience_requirements?: string[];
  domain?: string;
  role_function?: string;
  role_in_plain_english?: string;
  company_context?: CompanyContext;
  verbatim_for_cv?: string[];
  responsibilities_summary?: string;
  description?: string;
  team_size_hints?: string | null;
  salary_mentioned?: string | null;
  remote_restriction?: string | null;
  red_flags?: string[];
  key_phrases?: string[];
}

export interface SkillMatchItem {
  skill: string;
  status: 'matched' | 'partial' | 'none';
  matched_to: string | null;
  similarity: number;
}

export interface SkillMatches {
  must_have: SkillMatchItem[];
  nice_to_have: SkillMatchItem[];
}

export interface JobDetail extends JobSummary {
  parsed: ParsedJob | null;
  scored: ScoredResult | null;
  skill_matches: SkillMatches | null;
  ingested_at: string;
  applied_at: string | null;
  dismissed_at: string | null;
  domain_override?: string | null;
  scoring_method?: 'rag_v1' | 'rag_v2' | 'heuristic';
  role_function?: string;
  // Enriched fields (conditionally returned when non-null)
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  salary_interval?: string;
  salary_source?: string;
  company_size?: string;
  country?: string;
  city?: string;
  sources?: string[];
}

export interface JobsResponse {
  jobs: JobSummary[];
  total: number;
  total_in_db: number;
  filters: { tier: string[]; period: string };
}
