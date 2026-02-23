import { useEffect, useState } from 'react';
import ScoreBreakdown from '../components/ScoreBreakdown';
import { JobDetail } from '../types/job';

const TIER_STYLES: Record<string, string> = {
  A: 'bg-emerald-500 text-white',
  B: 'bg-amber-400 text-zinc-900',
  C: 'bg-zinc-600 text-zinc-200',
};

interface Props {
  jobId: string;
  onBack?: () => void;
}

export default function JobDetailPage({ jobId, onBack }: Props) {
  const [job, setJob] = useState<JobDetail | null>(null);

  useEffect(() => {
    fetch(`/api/jobs/${jobId}`)
      .then((r) => r.json())
      .then(setJob);
  }, [jobId]);

  if (!job) return <div className="min-h-screen bg-zinc-950" />;

  const scored = job.scored;

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8">
      <button
        onClick={onBack}
        className="mb-6 text-sm text-zinc-400 hover:text-white transition-colors"
      >
        ← Back
      </button>

      <div className="mx-auto max-w-2xl space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <h1 className="text-2xl font-bold text-white">{job.title}</h1>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xl font-bold text-zinc-200">{job.score}</span>
              <span className={`rounded px-2 py-0.5 text-sm font-bold ${TIER_STYLES[job.tier]}`}>
                {job.tier}
              </span>
            </div>
          </div>
          <p className="mt-1 text-zinc-400">{job.company} · {job.location}</p>
          <p className="mt-1 text-sm text-zinc-500">First seen {job.first_seen}</p>
        </div>

        {/* Score Breakdown */}
        {scored?.score_breakdown && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">Score Breakdown</h2>
            <ScoreBreakdown breakdown={scored.score_breakdown} />
          </section>
        )}

        {/* Strengths */}
        {scored?.strengths && scored.strengths.length > 0 && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">Strengths</h2>
            <ul className="space-y-2">
              {scored.strengths.map((s, i) => (
                <li key={i} className="rounded border border-zinc-700 bg-zinc-900 p-3">
                  <p className="font-medium text-white">{s.claim}</p>
                  <p className="mt-1 text-sm text-zinc-400">{s.evidence}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Gaps */}
        {scored?.gaps && scored.gaps.length > 0 && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">Gaps</h2>
            <ul className="space-y-2">
              {scored.gaps.map((g, i) => (
                <li key={i} className="rounded border border-zinc-700 bg-zinc-900 p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white">{g.skill}</span>
                    <span className="text-xs text-zinc-500">{g.severity}</span>
                  </div>
                  {g.mitigation && <p className="mt-1 text-sm text-zinc-400">{g.mitigation}</p>}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Actions */}
        <div className="pt-2">
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block rounded bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-400 transition-colors"
          >
            View original posting
          </a>
        </div>
      </div>
    </div>
  );
}
