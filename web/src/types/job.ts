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
  url: string;
  applied_at: string | null;
  geo_restricted: boolean;  // true = remote restriction excludes user's home region
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

export interface ParsedJob {
  seniority?: string;
  years_experience_min?: number | null;
  years_experience_max?: number | null;
  location_type?: string;
  locations_mentioned?: string[];
  must_have_skills?: string[];
  nice_to_have_skills?: string[];
  technical_stack?: string[];
  experience_requirements?: string[];
  domain?: string;
  responsibilities_summary?: string;
  team_size_hints?: string | null;
  salary_mentioned?: string | null;
  remote_restriction?: string | null;
  red_flags?: string[];
  key_phrases?: string[];
}

export interface JobDetail extends JobSummary {
  parsed: ParsedJob | null;
  scored: ScoredResult | null;
  last_seen: string;
  ingested_at: string;
  applied_at: string | null;
  dismissed_at: string | null;
}

export interface JobsResponse {
  jobs: JobSummary[];
  total: number;
  total_in_db: number;
  filters: { tier: string[]; period: string };
}
