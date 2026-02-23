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
  skill: string;
  severity: string;
  mitigation: string;
}

export interface ScoredResult {
  score: number;
  score_breakdown: ScoreBreakdown;
  strengths: Strength[];
  gaps: Gap[];
  talking_points?: string[];
  stories_to_prepare?: string[];
}

export interface JobDetail extends JobSummary {
  parsed: Record<string, unknown> | null;
  scored: ScoredResult | null;
  last_seen: string;
  ingested_at: string;
}

export interface JobsResponse {
  jobs: JobSummary[];
  total: number;
  filters: { tier: string[]; period: string };
}
