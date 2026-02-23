import { type ScoreBreakdown as SB } from '../types/job';

const DIMENSIONS: { key: keyof SB; label: string; max: number }[] = [
  { key: 'domain_fit', label: 'Domain Fit', max: 25 },
  { key: 'seniority_fit', label: 'Seniority Fit', max: 20 },
  { key: 'technical_depth', label: 'Technical Depth', max: 20 },
  { key: 'profile_evidence', label: 'Profile Evidence', max: 20 },
  { key: 'strategic_impact', label: 'Strategic Impact', max: 15 },
];

function barColor(pct: number): string {
  if (pct >= 75) return 'bg-emerald-500';
  if (pct >= 50) return 'bg-amber-400';
  return 'bg-red-500/70';
}

interface Props {
  breakdown: SB;
}

export default function ScoreBreakdown({ breakdown }: Props) {
  return (
    <div className="space-y-3.5">
      {DIMENSIONS.map(({ key, label, max }) => {
        const val = breakdown[key] ?? 0;
        const pct = Math.round((val / max) * 100);
        return (
          <div key={key}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium text-zinc-400">{label}</span>
              <span className="text-xs tabular-nums text-zinc-500">
                {val}
                <span className="text-zinc-700">/{max}</span>
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-zinc-800">
              <div
                className={`h-1.5 rounded-full transition-all duration-500 ${barColor(pct)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
