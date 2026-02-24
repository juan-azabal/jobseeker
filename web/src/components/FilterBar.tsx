export interface Filters {
  tiers: string[];
  period: string;
  hideApplied: boolean;
  hideGeoRestricted: boolean;
}

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
}

const PERIODS = [
  { label: 'Today', value: 'today' },
  { label: 'This week', value: 'week' },
  { label: 'This month', value: 'month' },
  { label: 'All time', value: 'all' },
];

// Apply and Review are normal toggles; Skip is exclusive (replaces A/B when active)
const MAIN_TIERS = ['A', 'B'] as const;

const TIER_ACTIVE: Record<string, string> = {
  A: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
  B: 'bg-amber-400/15 text-amber-300 border-amber-400/40',
};

const TIER_LABELS: Record<string, string> = {
  A: 'Apply',
  B: 'Review',
};

const DEFAULT_TIERS = ['A', 'B'];

export default function FilterBar({ filters, onChange }: Props) {
  const isSkipMode = filters.tiers.length === 1 && filters.tiers[0] === 'C';

  const toggleMainTier = (tier: string) => {
    // Exit skip mode first if active, then toggle the chosen tier
    const base = isSkipMode ? DEFAULT_TIERS : filters.tiers;
    const next = base.includes(tier) ? base.filter((t) => t !== tier) : [...base, tier];
    onChange({ ...filters, tiers: next.length ? next : DEFAULT_TIERS });
  };

  const toggleSkip = () => {
    onChange({ ...filters, tiers: isSkipMode ? DEFAULT_TIERS : ['C'] });
  };

  const setPeriod = (period: string) => onChange({ ...filters, period });
  const toggleHideApplied = () => onChange({ ...filters, hideApplied: !filters.hideApplied });
  const toggleHideGeoRestricted = () => onChange({ ...filters, hideGeoRestricted: !filters.hideGeoRestricted });

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <div className="flex gap-1">
        {PERIODS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => setPeriod(value)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-150 ${
              filters.period === value
                ? 'border border-violet-500/40 bg-violet-500/15 text-violet-300 shadow-sm'
                : 'border border-transparent text-zinc-500 hover:border-zinc-700 hover:text-zinc-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <span className="h-4 w-px bg-zinc-800" />

      <div className="flex gap-1">
        {MAIN_TIERS.map((tier) => (
          <button
            key={tier}
            onClick={() => toggleMainTier(tier)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all duration-150 ${
              !isSkipMode && filters.tiers.includes(tier)
                ? TIER_ACTIVE[tier]
                : 'border-transparent text-zinc-600 hover:border-zinc-700 hover:text-zinc-400'
            }`}
          >
            {TIER_LABELS[tier]}
          </button>
        ))}
        <button
          onClick={toggleSkip}
          className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all duration-150 ${
            isSkipMode
              ? 'bg-zinc-500/15 text-zinc-300 border-zinc-500/40'
              : 'border-transparent text-zinc-600 hover:border-zinc-700 hover:text-zinc-400'
          }`}
        >
          Skip
        </button>
      </div>

      <span className="h-4 w-px bg-zinc-800" />

      <button
        onClick={toggleHideApplied}
        className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-150 ${
          filters.hideApplied
            ? 'border-zinc-600 bg-zinc-700/40 text-zinc-300'
            : 'border-transparent text-zinc-600 hover:border-zinc-700 hover:text-zinc-400'
        }`}
      >
        {filters.hideApplied ? 'Show applied' : 'Hide applied'}
      </button>

      <button
        onClick={toggleHideGeoRestricted}
        className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-150 ${
          filters.hideGeoRestricted
            ? 'border-zinc-600 bg-zinc-700/40 text-zinc-300'
            : 'border-transparent text-zinc-600 hover:border-zinc-700 hover:text-zinc-400'
        }`}
      >
        {filters.hideGeoRestricted ? 'Show relocation' : 'Hide relocation'}
      </button>
    </div>
  );
}
