import { type ScoreBreakdown as SB } from '../types/job';

const DIMENSIONS: { key: keyof SB; label: string; max: number }[] = [
  { key: 'domain_fit', label: 'Domain Fit', max: 25 },
  { key: 'seniority_fit', label: 'Seniority Fit', max: 20 },
  { key: 'technical_depth', label: 'Technical Depth', max: 20 },
  { key: 'profile_evidence', label: 'Profile Evidence', max: 20 },
  { key: 'strategic_impact', label: 'Strategic Impact', max: 15 },
];

interface Props {
  breakdown: SB;
}

export default function ScoreBreakdown({ breakdown }: Props) {
  return (
    <div className="space-y-2">
      {DIMENSIONS.map(({ key, label, max }) => {
        const val = breakdown[key] ?? 0;
        const pct = Math.round((val / max) * 100);
        return (
          <div key={key}>
            <div className="flex justify-between text-sm text-zinc-300 mb-1">
              <span>{label}</span>
              <span className="text-zinc-400">{val}/{max}</span>
            </div>
            <div className="h-2 rounded bg-zinc-800">
              <div
                className="h-2 rounded bg-orange-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
