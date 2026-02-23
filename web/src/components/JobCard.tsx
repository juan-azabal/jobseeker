import { type JobSummary } from '../types/job';

const TIER_STYLES: Record<string, string> = {
  A: 'bg-emerald-500 text-white',
  B: 'bg-amber-400 text-zinc-900',
  C: 'bg-zinc-600 text-zinc-200',
};

interface Props {
  job: JobSummary;
  onClick?: () => void;
}

export default function JobCard({ job, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer rounded-lg border border-zinc-700 bg-zinc-900 p-4 hover:border-zinc-500 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-white">{job.title}</h3>
          <p className="text-sm text-zinc-400">{job.company} · {job.location}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-sm font-bold text-zinc-300">{job.score}</span>
          <span className={`rounded px-2 py-0.5 text-xs font-bold ${TIER_STYLES[job.tier]}`}>
            {job.tier}
          </span>
        </div>
      </div>
      <p className="mt-2 text-xs text-zinc-500">{job.first_seen}</p>
    </div>
  );
}
