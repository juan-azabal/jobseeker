import { useEffect, useState } from 'react';
import ScoreBreakdown from '../components/ScoreBreakdown';
import { type JobDetail } from '../types/job';

const TIER_BADGE: Record<string, string> = {
  A: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  B: 'bg-amber-400/10 text-amber-300 border-amber-400/30',
  C: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
};

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

function relativeDate(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (diff === 0) return 'today';
  if (diff === 1) return 'yesterday';
  if (diff < 7) return `${diff} days ago`;
  if (diff < 14) return '1 week ago';
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function buildCVPrompt(job: JobDetail): string {
  const parsed = job.parsed as Record<string, string> | null;
  const jd =
    parsed?.description ||
    parsed?.full_text ||
    parsed?.body ||
    'No job description available';
  return `Generate CV for this role:

**Title:** ${job.title}
**Company:** ${job.company}
**Location:** ${job.location}
**Score:** ${job.score}
**URL:** ${job.url}

**Job Description:**
${jd}`;
}

interface Props {
  jobId: string;
  onBack?: () => void;
}

export default function JobDetailPage({ jobId, onBack }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [isApplied, setIsApplied] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [cvCopied, setCvCopied] = useState(false);

  useEffect(() => {
    fetch(`/api/jobs/${jobId}`)
      .then((r) => r.json())
      .then((data: JobDetail) => {
        setJob(data);
        setIsApplied(!!data.applied_at);
      });
  }, [jobId]);

  if (!job) return <div className="min-h-screen bg-zinc-950" />;

  const scored = job.scored;

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

  const handleGenerateCV = () => {
    const prompt = buildCVPrompt(job);
    navigator.clipboard.writeText(prompt).then(() => {
      setCvCopied(true);
      setTimeout(() => setCvCopied(false), 2500);
    });
  };

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-6">
      <div className="mx-auto max-w-2xl">
        <button
          onClick={onBack}
          className="mb-8 flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
        >
          <span>←</span>
          <span>Back to jobs</span>
        </button>

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-xl font-bold leading-snug text-white">{job.title}</h1>
            <div
              className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-zinc-900 ring-1 ${TIER_SCORE_RING[job.tier]}`}
            >
              <span
                className={`text-lg font-bold tabular-nums leading-none ${TIER_SCORE_COLOR[job.tier]}`}
              >
                {job.score}
              </span>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-sm text-zinc-400">{job.company}</span>
            <span className="text-zinc-700">·</span>
            <span className="text-sm text-zinc-500">{job.location}</span>
            <span
              className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TIER_BADGE[job.tier]}`}
            >
              {TIER_LABEL[job.tier]}
            </span>
            {isApplied && (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
                Applied
              </span>
            )}
          </div>
          <p className="mt-1.5 text-xs text-zinc-600">First seen {relativeDate(job.first_seen)}</p>
        </div>

        <div className="space-y-5">
          {/* Score Breakdown */}
          {scored?.score_breakdown && (
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Score breakdown
              </h2>
              <ScoreBreakdown breakdown={scored.score_breakdown} />
            </section>
          )}

          {/* Strengths */}
          {scored?.strengths && scored.strengths.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Strengths
              </h2>
              <ul className="space-y-2">
                {scored.strengths.map((s, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-zinc-800 border-l-4 border-l-emerald-500/50 bg-zinc-900/60 p-4"
                  >
                    <p className="text-sm font-semibold text-white">{s.claim}</p>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-500">{s.evidence}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Gaps */}
          {scored?.gaps && scored.gaps.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
                Gaps
              </h2>
              <ul className="space-y-2">
                {scored.gaps.map((g, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-zinc-800 border-l-4 border-l-amber-400/50 bg-zinc-900/60 p-4"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{g.skill}</span>
                      <span
                        className={`text-xs font-medium ${
                          g.severity === 'critical'
                            ? 'text-red-400'
                            : g.severity === 'moderate'
                              ? 'text-amber-400'
                              : 'text-zinc-500'
                        }`}
                      >
                        {g.severity}
                      </span>
                    </div>
                    {g.mitigation && (
                      <p className="mt-1 text-xs leading-relaxed text-zinc-500">{g.mitigation}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {/* Generate CV */}
            <button
              onClick={handleGenerateCV}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-all duration-150 hover:bg-violet-500 hover:shadow-lg hover:shadow-violet-900/40"
            >
              {cvCopied ? (
                <>
                  <span className="text-violet-200">✓</span>
                  Prompt copied!
                </>
              ) : (
                <>
                  <span className="text-sm">📄</span>
                  Generate CV
                </>
              )}
            </button>

            {/* View posting */}
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-semibold text-zinc-300 transition-all duration-150 hover:border-zinc-500 hover:text-white"
            >
              View posting
              <span className="text-xs text-zinc-500">↗</span>
            </a>

            {/* Mark as applied */}
            <button
              onClick={handleApplyToggle}
              disabled={applyLoading}
              className={`inline-flex items-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-semibold transition-all duration-150
                ${isApplied
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                  : 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                }`}
            >
              {isApplied ? (
                <>
                  <span>✓</span>
                  Applied
                </>
              ) : (
                'Mark as applied'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
