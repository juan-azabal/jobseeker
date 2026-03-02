import { useEffect, useState } from 'react';
import ScoreBreakdown from '../components/ScoreBreakdown';
import DomainSelector from '../components/DomainSelector';
import { type JobDetail, type SkillMatchItem } from '../types/job';

const TIER_SCORE_COLOR: Record<string, string> = {
  A: 'text-emerald-400',
  B: 'text-amber-400',
  C: 'text-zinc-400',
};

const TIER_SCORE_RING: Record<string, string> = {
  A: 'ring-emerald-500/25',
  B: 'ring-amber-400/25',
  C: 'ring-zinc-500/25',
};

const TIER_LABEL: Record<string, string> = {
  A: 'Apply',
  B: 'Review',
  C: 'Skip',
};

const TIER_BADGE: Record<string, string> = {
  A: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  B: 'bg-amber-400/10 text-amber-300 border-amber-400/30',
  C: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
};

const LOC_TYPE_LABEL: Record<string, string> = {
  remote: 'Remote',
  hybrid: 'Hybrid',
  onsite: 'Onsite',
};

const SEVERITY_COLOR: Record<string, string> = {
  high: 'text-red-400',
  medium: 'text-amber-400',
  low: 'text-zinc-500',
};

const CV_ERROR_MESSAGES: Record<string, string> = {
  no_jd: 'No job description available for this role',
  llm_error: 'CV generation failed, try again',
};

function relativeDate(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (diff === 0) return 'today';
  if (diff === 1) return 'yesterday';
  if (diff < 7) return `${diff} days ago`;
  if (diff < 14) return '1 week ago';
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function freshnessDisplay(firstSeen: string, lastSeen?: string): { text: string; color: string } {
  const now = Date.now();
  const lastMs = lastSeen ? new Date(lastSeen).getTime() : new Date(firstSeen).getTime();
  const ageDays = Math.floor((now - lastMs) / 86_400_000);
  const firstPart = `First seen ${relativeDate(firstSeen)}`;
  if (ageDays < 7) return { text: `${firstPart} · Active`, color: 'text-emerald-400' };
  const lastPart = lastSeen ? ` · Last seen ${relativeDate(lastSeen)}` : '';
  if (ageDays <= 21) return { text: `${firstPart}${lastPart}`, color: 'text-amber-400' };
  return { text: `${firstPart}${lastPart}`, color: 'text-red-400' };
}

function formatSalary(job: JobDetail): { text: string; estimated: boolean } | null {
  if (job.salary_min != null) {
    const curr = job.salary_currency ?? '';
    const intv = job.salary_interval ?? 'year';
    const fmt = (n: number) => n.toLocaleString('en-US');
    const range = job.salary_max != null
      ? `${curr}${fmt(job.salary_min)}–${curr}${fmt(job.salary_max)}`
      : `${curr}${fmt(job.salary_min)}+`;
    return { text: `${range}/${intv}`, estimated: job.salary_source === 'estimated' };
  }
  const mentioned = job.parsed?.salary_mentioned;
  if (mentioned) return { text: mentioned, estimated: false };
  return null;
}

function filterRequirements(requirements: string[], roleFunction?: string): string[] {
  if (!requirements.length) return [];
  const dominated: RegExp[] = [
    /^\d+\+?\s*years?\s*(of\s+)?(overall\s+)?professional\s+experience/i,
    /bachelor'?s?\s+degree/i,
    /master'?s?\s+degree/i,
  ];
  if (roleFunction) {
    const roleTerms: Record<string, RegExp> = {
      product: /product\s+management/i,
      engineering: /software\s+(engineering|development)/i,
      data: /data\s+(science|engineering|analytics)/i,
      design: /(ux|ui|product)\s+design/i,
    };
    const roleRe = roleTerms[roleFunction];
    if (roleRe) dominated.push(new RegExp(`\\d+\\+?\\s*years?.*${roleRe.source}`, 'i'));
  }
  return requirements.filter(r => !dominated.some(re => re.test(r)));
}

function filterSkills(skills: string[], roleFunction?: string): string[] {
  const roleRedundant: Record<string, string[]> = {
    product: ['product management', 'product strategy', 'roadmap', 'stakeholder management'],
    engineering: ['software engineering', 'software development', 'coding'],
    data: ['data analysis', 'data analytics'],
    design: ['ux design', 'ui design', 'product design'],
  };
  const blacklist = new Set((roleRedundant[roleFunction ?? ''] ?? []).map(s => s.toLowerCase()));
  return skills.filter(s => !blacklist.has(s.toLowerCase()));
}

function Chip({ label, variant = 'default' }: { label: string; variant?: 'default' | 'skill' | 'warn' | 'violet' }) {
  const cls = {
    default: 'bg-zinc-800 text-zinc-400',
    skill: 'bg-zinc-800/80 text-zinc-300 border border-zinc-700',
    warn: 'bg-red-500/10 text-red-400 border border-red-500/20',
    violet: 'bg-violet-500/10 text-violet-400 border border-violet-500/20',
  }[variant];
  return <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

function SkillChip({
  match,
  onClick,
  added,
}: {
  match: SkillMatchItem;
  onClick?: () => void;
  added?: boolean;
}) {
  const status = added ? 'matched' : match.status;
  const matchedTo = added ? 'Just added' : match.matched_to;

  const cls = {
    matched: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
    partial: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
    none: 'bg-zinc-800/80 text-zinc-300 border-zinc-700',
  }[status];

  const tooltip = status === 'matched'
    ? `Matches: ${matchedTo}`
    : status === 'partial'
      ? `Similar to "${matchedTo}" (${Math.round(match.similarity * 100)}%) — click to add exact skill`
      : 'Click to add to your skills';

  const isClickable = (status === 'none' || status === 'partial') && !!onClick;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium transition-colors ${cls} ${isClickable ? 'cursor-pointer hover:border-violet-500/40 hover:text-violet-300' : ''}`}
      title={tooltip}
      role={isClickable ? 'button' : undefined}
      onClick={isClickable ? onClick : undefined}
    >
      {match.skill}
      {isClickable && <span className="text-zinc-600">+</span>}
    </span>
  );
}

interface Props {
  jobId: string;
  onBack?: () => void;
  prevId?: string;
  nextId?: string;
  onNavigate?: (id: string) => void;
}

export default function JobDetailPage({ jobId, onBack, prevId, nextId, onNavigate }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isApplied, setIsApplied] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [cvLoading, setCvLoading] = useState(false);
  const [cvSuccess, setCvSuccess] = useState(false);
  const [cvError, setCvError] = useState<string | null>(null);
  const [addedSkills, setAddedSkills] = useState<Set<string>>(new Set());
  const [fitFilter, setFitFilter] = useState<'all' | 'gaps' | 'strengths'>('all');
  const [userCvMd, setUserCvMd] = useState('');

  useEffect(() => {
    setLoading(true);
    setError(null);
    setFitFilter('all');
    fetch(`/api/jobs/${jobId}`)
      .then((r) => {
        if (r.status === 404) throw new Error('not_found');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: JobDetail) => {
        setJob(data);
        setIsApplied(!!data.applied_at);
        setIsDismissed(!!data.dismissed_at);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'unknown';
        if (msg === 'not_found') {
          setError('not_found');
        } else {
          setError('Failed to load job details');
        }
      })
      .finally(() => setLoading(false));
  }, [jobId]);

  useEffect(() => {
    fetch('/api/onboard/profile')
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.cv_markdown) setUserCvMd(data.cv_markdown.toLowerCase()); })
      .catch(() => {});
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center gap-3">
          <svg className="h-6 w-6 animate-spin text-violet-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm text-zinc-500">Loading job…</span>
        </div>
      </div>
    );
  }

  if (error === 'not_found') {
    return (
      <div className="min-h-screen bg-zinc-950 px-4 py-6">
        <div className="mx-auto max-w-2xl">
          <button
            onClick={onBack}
            className="mb-8 flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
          >
            ← Back to jobs
          </button>
          <div className="flex flex-col items-center gap-3 py-20">
            <span className="text-3xl">🔍</span>
            <p className="text-sm text-zinc-400">Job not found</p>
            <p className="text-xs text-zinc-600">It may have been removed or the link is invalid.</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-zinc-950 px-4 py-6">
        <div className="mx-auto max-w-2xl">
          <button
            onClick={onBack}
            className="mb-8 flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
          >
            ← Back to jobs
          </button>
          <div className="flex flex-col items-center gap-3 py-20">
            <span className="text-3xl">⚠️</span>
            <p className="text-sm text-zinc-400">{error || 'Something went wrong'}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-2 rounded-lg border border-zinc-700 px-4 py-2 text-xs text-zinc-400 transition-colors hover:border-zinc-500 hover:text-white"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const scored = job.scored;
  const p = job.parsed;
  const isRAG = !!scored;

  const handleApplyToggle = async () => {
    setApplyLoading(true);
    const next = !isApplied;
    await fetch(`/api/jobs/${jobId}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applied: next }),
    });
    setIsApplied(next);
    setApplyLoading(false);
  };

  const handleDismiss = async () => {
    await fetch(`/api/jobs/${jobId}/dismiss`, { method: 'POST' });
    setIsDismissed((prev) => !prev);
  };

  const handleGenerateCV = async () => {
    setCvLoading(true);
    setCvError(null);
    setCvSuccess(false);

    try {
      const resp = await fetch(`/api/jobs/${jobId}/generate-cv`, { method: 'POST' });

      if (!resp.ok) {
        let errorCode = 'generic';
        try {
          const body = await resp.json();
          errorCode = body.error || 'generic';
        } catch {
          // ignore JSON parse error
        }
        const message = CV_ERROR_MESSAGES[errorCode] ?? 'Something went wrong';
        setCvError(message);
        return;
      }

      const blob = await resp.blob();
      const contentDisp = resp.headers.get('content-disposition') ?? '';
      const filenameMatch = contentDisp.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      const filename = filenameMatch ? filenameMatch[1].replace(/['"]/g, '') : 'cv.docx';

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setCvSuccess(true);
      setTimeout(() => setCvSuccess(false), 3000);
    } catch {
      setCvError('Something went wrong');
    } finally {
      setCvLoading(false);
    }
  };

  const handleAddSkill = async (skill: string) => {
    const key = skill.toLowerCase();
    if (addedSkills.has(key)) return;

    // Optimistic update
    setAddedSkills((prev) => new Set(prev).add(key));

    try {
      const resp = await fetch('/api/onboard/profile/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill }),
      });
      if (!resp.ok) {
        // Revert on error
        setAddedSkills((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    } catch {
      setAddedSkills((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  // Build experience label
  const expLabel = p?.years_experience_min != null
    ? p.years_experience_max
      ? `${p.years_experience_min}–${p.years_experience_max} yrs`
      : `${p.years_experience_min}+ yrs`
    : null;

  // Derived: filtered requirements and skills (v1.5 names with backward compat)
  const mustHaveSkills = p?.truly_required ?? p?.must_have_skills ?? [];
  const niceToHaveSkills = p?.preferred_skills ?? p?.nice_to_have_skills ?? [];
  const filteredRequirements = filterRequirements(p?.experience_requirements ?? [], p?.role_function);
  const filteredMustHave = filterSkills(mustHaveSkills, p?.role_function);
  const allSkillsLower = new Set(
    [...mustHaveSkills, ...niceToHaveSkills].map(s => s.toLowerCase())
  );
  const techStackOnly = (p?.technical_stack ?? []).filter(s => !allSkillsLower.has(s.toLowerCase()));

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-6">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex items-center justify-between">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
          >
            <span>←</span>
            <span>Back to jobs</span>
          </button>
          {(prevId || nextId) && onNavigate && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => prevId && onNavigate(prevId)}
                disabled={!prevId}
                className="rounded-lg border border-zinc-800 px-2.5 py-1 text-xs text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Previous job"
              >
                ← Prev
              </button>
              <button
                onClick={() => nextId && onNavigate(nextId)}
                disabled={!nextId}
                className="rounded-lg border border-zinc-800 px-2.5 py-1 text-xs text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Next job"
              >
                Next →
              </button>
            </div>
          )}
        </div>

        {/* ── Header ─────────────────────────────────────────────── */}
        <div className="mb-6">
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-xl font-bold leading-snug text-white">{job.title}</h1>
            <div
              className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-zinc-900 ring-1 ${TIER_SCORE_RING[job.tier]}`}
            >
              <span className={`text-lg font-bold tabular-nums leading-none ${TIER_SCORE_COLOR[job.tier]}`}>
                {job.score}
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-sm text-zinc-400">
              {job.company}{job.company_size && <span className="text-zinc-600"> · {job.company_size}</span>}
            </span>
            <span className="text-zinc-700">·</span>
            <span className="text-sm text-zinc-500">{job.location}</span>
            {job.location_type && job.location_type !== 'unknown' && (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400 capitalize">
                {LOC_TYPE_LABEL[job.location_type] ?? job.location_type}
              </span>
            )}
            {p?.remote_restriction && (
              job.eligibility_warning ? (
                <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-xs text-red-400 border border-red-500/20">
                  {p.remote_restriction}
                </span>
              ) : job.geo_restricted ? (
                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-400 border border-amber-500/20">
                  {p.remote_restriction}
                </span>
              ) : (
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400 border border-zinc-700">
                  {p.remote_restriction}
                </span>
              )
            )}
            <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TIER_BADGE[job.tier]}`}>
              {TIER_LABEL[job.tier]}
            </span>
            {isApplied && (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
                Applied
              </span>
            )}
            {job.scoring_method && (
              <span className={`rounded border px-2 py-0.5 text-xs ${
                job.scoring_method !== 'heuristic'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-zinc-800 border-zinc-700 text-zinc-400'
              }`}>
                {job.scoring_method !== 'heuristic' ? 'AI scored' : 'Estimated'}
              </span>
            )}
          </div>

          {/* Meta strip */}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-600">
            {p?.seniority && p.seniority !== 'unknown' && (
              <span className="capitalize">{p.seniority}{expLabel ? ` · ${expLabel}` : ''}</span>
            )}
            <DomainSelector
              jobId={jobId}
              parsedDomain={p?.domain}
              domainOverride={job.domain_override}
            />
            {(() => {
              const sal = formatSalary(job);
              if (!sal) return null;
              return (
                <span className={sal.estimated ? 'italic text-zinc-500' : 'text-zinc-500'}>
                  {sal.text}{sal.estimated ? ' (estimated)' : ''}
                </span>
              );
            })()}
            {p?.team_size_hints && (
              <span>{p.team_size_hints}</span>
            )}
            {(() => {
              const f = freshnessDisplay(job.first_seen, job.last_seen);
              return <span className={f.color}>{f.text}</span>;
            })()}
          </div>

          {/* Verdict in hero (RAG only) */}
          {scored?.one_line_verdict && (
            <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
              <p className="text-sm italic text-zinc-300">{scored.one_line_verdict}</p>
            </div>
          )}
        </div>

        <div className="space-y-4">

          {/* ── Section 1: The Role ─────────────────────────────────── */}
          {(p?.role_in_plain_english || p?.responsibilities_summary || p?.company_context || filteredRequirements.length > 0 || (p?.key_phrases && p.key_phrases.length > 0)) && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                The Role
              </h2>
              {(p?.role_in_plain_english || p?.responsibilities_summary) && (
                <p className="text-sm leading-relaxed text-zinc-300">
                  {p?.role_in_plain_english ?? p?.responsibilities_summary}
                </p>
              )}
              {p?.company_context && (p.company_context.stage || p.company_context.tone || (p.company_context.what_they_value && p.company_context.what_they_value.length > 0)) && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  {p.company_context.stage && (
                    <span className="rounded border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-xs text-zinc-400">
                      {p.company_context.stage}
                    </span>
                  )}
                  {p.company_context.tone && (
                    <span className="rounded border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-xs text-zinc-400">
                      {p.company_context.tone.replace(/_/g, ' ')}
                    </span>
                  )}
                  {p.company_context.what_they_value && p.company_context.what_they_value.length > 0 && (
                    <span className="text-xs text-zinc-500">
                      {p.company_context.what_they_value.join(' · ')}
                    </span>
                  )}
                </div>
              )}
              {p?.key_phrases && p.key_phrases.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {p.key_phrases.map((kp, i) => <Chip key={i} label={kp} />)}
                </div>
              )}
              {filteredRequirements.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {filteredRequirements.map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-zinc-400">
                      <span className="mt-0.5 shrink-0 text-zinc-700">·</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* ── Section 2: Your Fit ─────────────────────────────────── */}
          {isRAG ? (
            <>
              {scored.score_breakdown && (
                <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                  <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Score breakdown
                  </h2>
                  <ScoreBreakdown breakdown={scored.score_breakdown} />
                </section>
              )}
              {((scored.deal_breakers?.length ?? 0) > 0 || (scored.gaps?.length ?? 0) > 0 || (scored.strengths?.length ?? 0) > 0) && (
                <section>
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
                      Your fit
                    </h2>
                    <div className="flex gap-0.5">
                      {(['all', 'gaps', 'strengths'] as const).map(f => (
                        <button
                          key={f}
                          onClick={() => setFitFilter(f)}
                          className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                            fitFilter === f
                              ? 'bg-zinc-800 text-zinc-200'
                              : 'text-zinc-600 hover:text-zinc-400'
                          }`}
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>
                  <ul className="space-y-2">
                    {fitFilter !== 'strengths' && scored.deal_breakers?.map((d, i) => (
                      <li key={`db-${i}`} className="rounded-lg border border-red-500/20 border-l-4 border-l-red-500/60 bg-red-500/5 px-4 py-3">
                        <p className="text-sm text-red-300">{d}</p>
                      </li>
                    ))}
                    {fitFilter !== 'strengths' && scored.gaps?.filter(g => g.severity === 'high').map((g, i) => (
                      <li key={`gh-${i}`} className="rounded-lg border border-zinc-800 border-l-4 border-l-amber-400/50 bg-zinc-900/60 p-4">
                        <div className="flex items-start gap-2">
                          <p className="flex-1 text-sm text-zinc-200">{g.gap}</p>
                          <span className="shrink-0 text-xs font-medium capitalize text-red-400">high</span>
                        </div>
                        {g.mitigation && (
                          <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{g.mitigation}</p>
                        )}
                      </li>
                    ))}
                    {fitFilter !== 'gaps' && scored.strengths?.map((s, i) => (
                      <li key={`str-${i}`} className="rounded-lg border border-zinc-800 border-l-4 border-l-emerald-500/50 bg-zinc-900/60 p-4">
                        <p className="text-sm font-medium text-white">{s.claim}</p>
                        <p className="mt-1 text-xs leading-relaxed text-zinc-500">{s.evidence}</p>
                      </li>
                    ))}
                    {fitFilter !== 'strengths' && scored.gaps?.filter(g => g.severity !== 'high').map((g, i) => (
                      <li key={`gml-${i}`} className="rounded-lg border border-zinc-800 border-l-4 border-l-amber-400/50 bg-zinc-900/60 p-4">
                        <div className="flex items-start gap-2">
                          <p className="flex-1 text-sm text-zinc-200">{g.gap}</p>
                          <span className={`shrink-0 text-xs font-medium capitalize ${SEVERITY_COLOR[g.severity] ?? 'text-zinc-500'}`}>
                            {g.severity}
                          </span>
                        </div>
                        {g.mitigation && (
                          <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{g.mitigation}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          ) : (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Your fit
              </h2>
              <div className="flex items-center gap-2">
                <span className="text-sm text-zinc-400">Quick Estimate</span>
                <span className="text-zinc-700">·</span>
                <span className={`text-lg font-bold tabular-nums ${TIER_SCORE_COLOR[job.tier]}`}>{job.score}/100</span>
              </div>
              {job.skill_matches && (
                <p className="mt-2 text-xs text-zinc-500">
                  {job.skill_matches.must_have.filter(m => m.status !== 'none').length}/{job.skill_matches.must_have.length} required skills matched
                </p>
              )}
            </section>
          )}

          {/* ── Section 3: Skills (all jobs) ───────────────────────── */}
          {(filteredMustHave.length > 0 || niceToHaveSkills.length > 0 || techStackOnly.length > 0) && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Skills
              </h2>
              {filteredMustHave.length > 0 && (
                <div className={niceToHaveSkills.length > 0 || techStackOnly.length > 0 ? 'mb-3' : ''}>
                  <p className="mb-1.5 text-xs text-zinc-600">Required</p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.skill_matches
                      ? job.skill_matches.must_have
                          .filter(m => filteredMustHave.map(s => s.toLowerCase()).includes(m.skill.toLowerCase()))
                          .map((m, i) => (
                            <SkillChip
                              key={i}
                              match={m}
                              added={addedSkills.has(m.skill.toLowerCase())}
                              onClick={m.status !== 'matched' ? () => handleAddSkill(m.skill) : undefined}
                            />
                          ))
                      : filteredMustHave.map((s, i) => <Chip key={i} label={s} variant="skill" />)
                    }
                  </div>
                </div>
              )}
              {niceToHaveSkills.length > 0 && (
                <div className={techStackOnly.length > 0 ? 'mb-3' : ''}>
                  <p className="mb-1.5 text-xs text-zinc-600">Preferred</p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.skill_matches
                      ? job.skill_matches.nice_to_have.map((m, i) => (
                          <SkillChip
                            key={i}
                            match={m}
                            added={addedSkills.has(m.skill.toLowerCase())}
                            onClick={m.status !== 'matched' ? () => handleAddSkill(m.skill) : undefined}
                          />
                        ))
                      : niceToHaveSkills.map((s, i) => <Chip key={i} label={s} />)
                    }
                  </div>
                </div>
              )}
              {techStackOnly.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-zinc-600">Tech stack</p>
                  <div className="flex flex-wrap gap-1.5">
                    {techStackOnly.map((s, i) => <Chip key={i} label={s} variant="skill" />)}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ── Keywords to match ─────────────────────────────────── */}
          {p?.verbatim_for_cv && p.verbatim_for_cv.length > 0 && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Keywords to match
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {p.verbatim_for_cv.map((phrase, i) => {
                  const inCv = userCvMd ? userCvMd.includes(phrase.toLowerCase()) : null;
                  return (
                    <span
                      key={i}
                      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs ${
                        inCv === true
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                          : inCv === false
                            ? 'border-zinc-700 bg-violet-500/10 text-violet-300'
                            : 'border-zinc-700 bg-violet-500/10 text-violet-300'
                      }`}
                      title={inCv === true ? 'In your CV' : inCv === false ? 'Missing from CV' : ''}
                    >
                      {inCv === true && <span className="text-emerald-500">✓</span>}
                      {inCv === false && <span className="text-zinc-500">·</span>}
                      {phrase}
                    </span>
                  );
                })}
              </div>
            </section>
          )}

          {/* ── Prep zone: Interview Prep (RAG, tier A/B only) ─────── */}
          {isRAG && (job.tier === 'A' || job.tier === 'B') && ((scored.talking_points?.length ?? 0) > 0 || (scored.stories_to_prepare?.length ?? 0) > 0) && (
            <>
              {scored.talking_points && scored.talking_points.length > 0 && (
                <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Interview prep
                  </h2>
                  <ul className="space-y-2">
                    {scored.talking_points.map((t, i) => (
                      <li key={i} className="flex gap-2 text-sm text-zinc-300">
                        <span className="mt-0.5 shrink-0 text-zinc-600">→</span>
                        <span className="leading-relaxed">{t}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {scored.stories_to_prepare && scored.stories_to_prepare.length > 0 && (
                <section>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Stories to prepare
                  </h2>
                  <div className="flex flex-wrap gap-1.5">
                    {scored.stories_to_prepare.map((s, i) => (
                      <Chip key={i} label={s} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* ── Red flags (always, if any) ─────────────────────────── */}
          {p?.red_flags && p.red_flags.length > 0 && (
            <section>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Red flags
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {p.red_flags.map((f, i) => <Chip key={i} label={f} variant="warn" />)}
              </div>
            </section>
          )}

          {/* ── Actions ───────────────────────────────────────────── */}
          <div className="pt-2">
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={handleGenerateCV}
                disabled={cvLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-all duration-150 hover:bg-violet-500 hover:shadow-lg hover:shadow-violet-900/40 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {cvLoading ? (
                  <>
                    <svg className="h-4 w-4 animate-spin text-violet-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Generating CV...
                  </>
                ) : cvSuccess ? (
                  <><span className="text-violet-200">✓</span>CV downloaded</>
                ) : (
                  <><span className="text-sm">📄</span>Generate CV</>
                )}
              </button>

              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-semibold text-zinc-300 transition-all duration-150 hover:border-zinc-500 hover:text-white"
              >
                View posting
                <span className="text-xs text-zinc-500">↗</span>
              </a>
              {job.last_seen && Math.floor((Date.now() - new Date(job.last_seen).getTime()) / 86_400_000) > 21 && (
                <span className="text-xs text-red-400">This posting may no longer be active</span>
              )}

              <button
                onClick={handleApplyToggle}
                disabled={applyLoading}
                className={`inline-flex items-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-semibold transition-all duration-150
                  ${isApplied
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                    : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                  }`}
              >
                {isApplied ? <><span>✓</span>Applied</> : 'Mark as applied'}
              </button>

              <button
                onClick={handleDismiss}
                className={`inline-flex items-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-semibold transition-all duration-150
                  ${isDismissed
                    ? 'border-red-500/40 bg-red-500/10 text-red-400'
                    : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                  }`}
              >
                {isDismissed ? 'Skipped ✓' : 'Skip'}
              </button>
            </div>

            {cvLoading && (
              <p className="mt-2 text-xs text-zinc-500">This usually takes 15-20 seconds</p>
            )}
            {cvError && !cvLoading && (
              <p className="mt-2 text-xs text-red-400">{cvError}</p>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
