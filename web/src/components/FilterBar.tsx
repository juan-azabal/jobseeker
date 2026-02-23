export interface Filters {
  tiers: string[];
  period: string;
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

const TIERS = ['A', 'B', 'C'];

const TIER_ACTIVE: Record<string, string> = {
  A: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
  B: 'bg-amber-400/15 text-amber-300 border-amber-400/40',
  C: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/40',
};

const TIER_LABELS: Record<string, string> = {
  A: 'Apply',
  B: 'Review',
  C: 'Skip',
};

export default function FilterBar({ filters, onChange }: Props) {
  const toggleTier = (tier: string) => {
    const next = filters.tiers.includes(tier)
      ? filters.tiers.filter((t) => t !== tier)
      : [...filters.tiers, tier];
    onChange({ ...filters, tiers: next });
  };

  const setPeriod = (period: string) => onChange({ ...filters, period });

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
        {TIERS.map((tier) => (
          <button
            key={tier}
            onClick={() => toggleTier(tier)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all duration-150 ${
              filters.tiers.includes(tier)
                ? TIER_ACTIVE[tier]
                : 'border-transparent text-zinc-600 hover:border-zinc-700 hover:text-zinc-400'
            }`}
          >
            {TIER_LABELS[tier]}
          </button>
        ))}
      </div>
    </div>
  );
}
