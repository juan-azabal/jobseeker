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
  { label: 'This Week', value: 'week' },
  { label: 'This Month', value: 'month' },
  { label: 'All', value: 'all' },
];

const TIERS = ['A', 'B', 'C'];

const TIER_ACTIVE: Record<string, string> = {
  A: 'bg-emerald-500 text-white',
  B: 'bg-amber-400 text-zinc-900',
  C: 'bg-zinc-500 text-white',
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
    <div className="flex flex-wrap items-center gap-3 pb-4">
      <div className="flex gap-1">
        {PERIODS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => setPeriod(value)}
            className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
              filters.period === value
                ? 'bg-orange-500 text-white'
                : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex gap-1">
        {TIERS.map((tier) => (
          <button
            key={tier}
            onClick={() => toggleTier(tier)}
            className={`rounded px-3 py-1 text-sm font-bold transition-colors ${
              filters.tiers.includes(tier)
                ? TIER_ACTIVE[tier]
                : 'bg-zinc-800 text-zinc-500 hover:bg-zinc-700'
            }`}
          >
            {tier}
          </button>
        ))}
      </div>
    </div>
  );
}
