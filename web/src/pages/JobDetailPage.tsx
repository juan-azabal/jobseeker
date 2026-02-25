import { useEffect, useState } from 'react';
import ScoreBreakdown from '../components/ScoreBreakdown';
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

  useEffect(() => {
    setLoading(true);
    setError(null);
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
            <span className="text-sm text-zinc-400">{job.company}</span>
            <span className="text-zinc-700">·</span>
            <span className="text-sm text-zinc-500">{job.location}</span>
            {job.location_type && job.location_type !== 'unknown' && (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400 capitalize">
                {LOC_TYPE_LABEL[job.location_type] ?? job.location_type}
              </span>
            )}
            {p?.remote_restriction && (
              job.geo_restricted ? (
                <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-400 border border-amber-500/20">
                  {p.remote_restriction}
                </span>
              ) : (
                <span className="rounded bg-sky-500/10 px-1.5 py-0.5 text-xs text-sky-400 border border-sky-500/20">
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
          </div>

          {/* Meta strip */}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-600">
            {p?.seniority && p.seniority !== 'unknown' && (
              <span className="capitalize">{p.seniority}{expLabel ? ` · ${expLabel}` : ''}</span>
            )}
            {p?.domain && p.domain !== 'other' && (
              <span className="capitalize">{p.domain}</span>
            )}
            {p?.salary_mentioned && (
              <span className="text-zinc-500">{p.salary_mentioned}</span>
            )}
            {p?.team_size_hints && (
              <span>{p.team_size_hints}</span>
            )}
            <span className="text-zinc-700">First seen {relativeDate(job.first_seen)}</span>
          </div>
        </div>

        <div className="space-y-4">

          {/* ── One-line verdict (RAG only) ────────────────────────── */}
          {scored?.one_line_verdict && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
              <p className="text-sm italic text-zinc-300">{scored.one_line_verdict}</p>
            </div>
          )}

          {/* ── About this role ────────────────────────────────────── */}
          {p?.responsibilities_summary && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                About this role
              </h2>
              <p className="text-sm leading-relaxed text-zinc-300">{p.responsibilities_summary}</p>
            </section>
          )}

          {/* ── RAG Analysis ──────────────────────────────────────── */}
          {isRAG && (
            <>
              {/* Score breakdown */}
              {scored.score_breakdown && (
                <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                  <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Score breakdown
                  </h2>
                  <ScoreBreakdown breakdown={scored.score_breakdown} />
                </section>
              )}

              {/* Deal breakers */}
              {scored.deal_breakers && scored.deal_breakers.length > 0 && (
                <section>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Deal breakers
                  </h2>
                  <ul className="space-y-2">
                    {scored.deal_breakers.map((d, i) => (
                      <li key={i} className="rounded-lg border border-red-500/20 border-l-4 border-l-red-500/60 bg-red-500/5 px-4 py-3">
                        <p className="text-sm text-red-300">{d}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Gaps */}
              {scored.gaps && scored.gaps.length > 0 && (
                <section>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Gaps
                  </h2>
                  <ul className="space-y-2">
                    {scored.gaps.map((g, i) => (
                      <li key={i} className="rounded-lg border border-zinc-800 border-l-4 border-l-amber-400/50 bg-zinc-900/60 p-4">
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

              {/* Strengths */}
              {scored.strengths && scored.strengths.length > 0 && (
                <section>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Strengths
                  </h2>
                  <ul className="space-y-2">
                    {scored.strengths.map((s, i) => (
                      <li key={i} className="rounded-lg border border-zinc-800 border-l-4 border-l-emerald-500/50 bg-zinc-900/60 p-4">
                        <p className="text-sm font-medium text-white">{s.claim}</p>
                        <p className="mt-1 text-xs leading-relaxed text-zinc-500">{s.evidence}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Talking points */}
              {scored.talking_points && scored.talking_points.length > 0 && (
                <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    How to pitch yourself
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

              {/* Stories to prepare */}
              {scored.stories_to_prepare && scored.stories_to_prepare.length > 0 && (
                <section>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                    Stories to prepare
                  </h2>
                  <div className="flex flex-wrap gap-1.5">
                    {scored.stories_to_prepare.map((s, i) => (
                      <Chip key={i} label={s} variant="violet" />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* ── Skills (all jobs) ──────────────────────────────────── */}
          {(p?.must_have_skills?.length || p?.nice_to_have_skills?.length) && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Skills
              </h2>
              {p?.must_have_skills && p.must_have_skills.length > 0 && (
                <div className="mb-3">
                  <p className="mb-1.5 text-xs text-zinc-600">Required</p>
                  <div className="flex flex-wrap gap-1.5">
                    {job.skill_matches
                      ? job.skill_matches.must_have.map((m, i) => (
                          <SkillChip
                            key={i}
                            match={m}
                            added={addedSkills.has(m.skill.toLowerCase())}
                            onClick={m.status !== 'matched' ? () => handleAddSkill(m.skill) : undefined}
                          />
                        ))
                      : p.must_have_skills.map((s, i) => <Chip key={i} label={s} variant="skill" />)
                    }
                  </div>
                </div>
              )}
              {p?.nice_to_have_skills && p.nice_to_have_skills.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-zinc-600">Nice to have</p>
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
                      : p.nice_to_have_skills.map((s, i) => <Chip key={i} label={s} />)
                    }
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ── Heuristic-only: requirements ─────────────────────── */}
          {!isRAG && p?.experience_requirements && p.experience_requirements.length > 0 && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Requirements
              </h2>
              <ul className="space-y-1.5">
                {p.experience_requirements.map((r, i) => (
                  <li key={i} className="flex gap-2 text-sm text-zinc-400">
                    <span className="mt-0.5 shrink-0 text-zinc-700">·</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </section>
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
