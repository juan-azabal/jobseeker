/** Master CV JSON v1.0 — canonical professional history schema. */

export interface MasterCvLocation {
  city: string;
  country: string; // ISO 3166 A-2
}

export interface MasterCvProfile {
  network: string;
  url: string;
}

export interface MasterCvBasics {
  name: string;
  email?: string | null;
  phone?: string | null;
  location?: MasterCvLocation;
  url?: string | null;
  profiles?: MasterCvProfile[];
}

export interface MasterCvWork {
  id: string; // work_NNN
  company: string;
  position: string;
  location?: string | null;
  start_date?: string | null; // YYYY-MM | YYYY
  end_date?: string | null; // null = current
  summary?: string | null;
  highlights: string[];
  skills_used: string[];
  source: 'cv_upload' | 'linkedin_pdf' | 'manual' | 'merged';
}

export interface MasterCvEducation {
  id: string; // edu_NNN
  institution: string;
  area: string;
  study_type: string;
  start_date?: string | null;
  end_date?: string | null;
  source: string;
}

export interface MasterCvSkill {
  name: string;
  level?: string | null;
  keywords?: string[];
  source?: string;
}

export interface MasterCvLanguage {
  language: string;
  fluency: string;
}

export interface MasterCvCertification {
  id: string; // cert_NNN
  name: string;
  issuer?: string | null;
  date?: string | null;
  source: string;
}

export interface MasterCvProject {
  id: string; // proj_NNN
  name: string;
  description?: string | null;
  highlights: string[];
  keywords: string[];
  start_date?: string | null;
  end_date?: string | null;
  url?: string | null;
  source: string;
}

export interface MasterCv {
  version: string;
  updated_at?: string;
  sources?: string[];
  basics: MasterCvBasics;
  work: MasterCvWork[];
  education: MasterCvEducation[];
  skills: MasterCvSkill[];
  languages: MasterCvLanguage[];
  certifications: MasterCvCertification[];
  projects: MasterCvProject[];
}

/** Payload for POST /api/onboard/add-entry */
export interface AddEntryPayload {
  type: 'work' | 'project';
  // work fields
  company?: string;
  position?: string;
  location?: string;
  // project fields
  name?: string;
  url?: string;
  // shared
  start_date?: string;
  end_date?: string | null;
  summary?: string;
  description?: string;
  highlights: string[];
  skills_used?: string[]; // work
  keywords?: string[]; // project
}
