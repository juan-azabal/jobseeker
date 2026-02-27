import { type JobSummary } from '../types/job';

const TIER_BORDER: Record<string, string> = {
  A: 'border-l-emerald-500',
  B: 'border-l-amber-400',
  C: 'border-l-zinc-600',
};

const TIER_BADGE: Record<string, string> = {
  A: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  B: 'bg-amber-400/10 text-amber-300 border-amber-400/30',
  C: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
};

const TIER_SCORE: Record<string, string> = {
  A: 'text-emerald-400',
  B: 'text-amber-400',
  C: 'text-zinc-500',
};

const TIER_LABEL: Record<string, string> = {
  A: 'Apply',
  B: 'Review',
  C: 'Skip',
};

function relativeDate(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff}d ago`;
  if (diff < 14) return '1w ago';
  if (diff < 30) return `${Math.floor(diff / 7)}w ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

interface Props {
  job: JobSummary;
  selected?: boolean;
  onSelect?: (selected: boolean) => void;
  onClick?: () => void;
}

export default function JobCard({ job, selected = false, onSelect, onClick }: Props) {
  const isApplied = !!job.applied_at;

  return (
    <div
      onClick={onClick}
      className={`group relative cursor-pointer rounded-lg border border-l-4 bg-zinc-900 p-4 transition-all duration-150
        ${TIER_BORDER[job.tier]}
        ${isApplied
          ? 'border-zinc-800/40 opacity-60 hover:opacity-80'
          : 'border-zinc-800 hover:-translate-y-px hover:border-zinc-700 hover:shadow-lg hover:shadow-black/50'
        }`}
    >
      {/* Selection checkbox */}
      {onSelect && (
        <div
          className="absolute left-3 top-1/2 -translate-y-1/2"
          onClick={(e) => { e.stopPropagation(); onSelect(!selected); }}
        >
          <div className={`flex h-4 w-4 items-center justify-center rounded border transition-all duration-100
            ${selected
              ? 'border-violet-500 bg-violet-500'
              : 'border-zinc-600 bg-transparent group-hover:border-zinc-400'
            }`}
          >
            {selected && (
              <svg className="h-2.5 w-2.5 text-white" viewBox="0 0 10 10" fill="none">
                <path d="M1.5 5L4 7.5L8.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
        </div>
      )}

      <div className={`flex items-start justify-between gap-3 ${onSelect ? 'pl-6' : ''}`}>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-white">{job.title}</h3>
            {isApplied && (
              <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400 border border-emerald-500/20">
                Applied
              </span>
            )}
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-zinc-500">
            <span>{job.company}</span>
            <span className="text-zinc-700">·</span>
            <span>{job.location}</span>
            {job.location_type && job.location_type !== 'unknown' && (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-500 capitalize">
                {job.location_type}
              </span>
            )}
            {job.eligibility_warning ? (
              <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-red-400/80 border border-red-500/20 text-xs">
                Not eligible
              </span>
            ) : job.geo_restricted ? (
              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-500/70 border border-amber-500/20">
                Relocation
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`text-lg font-bold tabular-nums leading-none ${TIER_SCORE[job.tier]}`}>
            {job.score}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TIER_BADGE[job.tier]}`}>
            {TIER_LABEL[job.tier]}
          </span>
        </div>
      </div>
      <p className={`mt-2.5 text-right text-xs text-zinc-600 ${onSelect ? 'pl-6' : ''}`}>
        {relativeDate(job.first_seen)}
      </p>
    </div>
  );
}
