const DIMENSIONS = [
  { label: 'Domain Fit', value: 24, max: 25 },
  { label: 'Seniority Fit', value: 19, max: 20 },
  { label: 'Technical Depth', value: 17, max: 20 },
  { label: 'Profile Evidence', value: 17, max: 20 },
  { label: 'Strategic Impact', value: 14, max: 15 },
];

const SKILLS: { skill: string; status: 'matched' | 'partial' | 'none' }[] = [
  { skill: 'Product Strategy', status: 'matched' },
  { skill: 'SQL', status: 'matched' },
  { skill: 'B2B Platforms', status: 'matched' },
  { skill: 'Revenue Optimization', status: 'partial' },
  { skill: 'Enterprise Sales Cycles', status: 'none' },
];

const STRENGTHS = [
  {
    claim: 'Deep B2B platform experience',
    evidence: 'Led product for multi-sided marketplace with 50K+ users',
  },
  {
    claim: 'Quantified growth impact',
    evidence: 'Drove 3x ARR expansion via self-serve onboarding redesign',
  },
];

const GAP = {
  gap: 'No direct enterprise sales cycle exposure',
  severity: 'medium',
  mitigation: 'Adjacent experience with B2B onboarding funnels and sales-assist features',
};

const VERDICT =
  'Strong product leader with deep B2B platform experience. The enterprise sales gap is addressable — your growth and self-serve background positions you well.';

function barColor(pct: number): string {
  if (pct >= 75) return 'bg-emerald-500';
  if (pct >= 50) return 'bg-amber-400';
  return 'bg-red-500/70';
}

const SKILL_CLS = {
  matched: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  partial: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  none: 'bg-zinc-800/80 text-zinc-300 border-zinc-700',
};

export default function MockJobDetail() {
  return (
    <div
      className="pointer-events-none opacity-[0.85]"
      style={{ transform: 'perspective(1200px) rotateY(2deg)' }}
    >
      {/* Browser frame */}
      <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
        {/* Top bar */}
        <div className="flex items-center gap-3 border-b border-zinc-800 bg-zinc-900 px-4 py-3">
          <div className="flex gap-1.5">
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
          </div>
          <div className="mx-auto rounded-full bg-zinc-800 px-4 py-1 text-xs text-zinc-500">
            jobseeker-production.up.railway.app/jobs/abc123
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-col gap-4 p-5">

          {/* Header row */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h3 className="text-base font-bold leading-snug text-white">Head of Product</h3>
              <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-xs text-zinc-500">
                <span>Series B · B2B SaaS</span>
                <span className="text-zinc-700">·</span>
                <span>Barcelona · Remote</span>
              </p>
              <div className="mt-2">
                <span className="rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                  Apply
                </span>
              </div>
            </div>
            {/* Score ring */}
            <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-xl bg-zinc-900 ring-1 ring-emerald-500/25">
              <span className="text-lg font-bold tabular-nums leading-none text-emerald-400">91</span>
            </div>
          </div>

          {/* Verdict */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
            <p className="text-xs italic text-zinc-300">{VERDICT}</p>
          </div>

          {/* Score breakdown */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">Score breakdown</p>
            <div className="space-y-3">
              {DIMENSIONS.map(({ label, value, max }) => {
                const pct = Math.round((value / max) * 100);
                return (
                  <div key={label}>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-xs font-medium text-zinc-400">{label}</span>
                      <span className="text-xs tabular-nums text-zinc-500">
                        {value}<span className="text-zinc-700">/{max}</span>
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-800">
                      <div
                        className={`h-1.5 rounded-full ${barColor(pct)}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Skills */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">Skills</p>
            <div className="flex flex-wrap gap-1.5">
              {SKILLS.map(({ skill, status }) => (
                <span
                  key={skill}
                  className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${SKILL_CLS[status]}`}
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>

          {/* Strengths — 2 on desktop, 1 on mobile */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">Strengths</p>
            <ul className="space-y-2">
              {STRENGTHS.map((s, i) => (
                <li
                  key={i}
                  className={`rounded-lg border border-zinc-800 border-l-4 border-l-emerald-500/50 bg-zinc-900/60 p-4${i === 1 ? ' hidden md:block' : ''}`}
                >
                  <p className="text-sm font-medium text-white">{s.claim}</p>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-500">{s.evidence}</p>
                </li>
              ))}
            </ul>
          </div>

          {/* Gap — hidden on mobile */}
          <div className="hidden md:block">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">Gaps</p>
            <div className="rounded-lg border border-zinc-800 border-l-4 border-l-amber-400/50 bg-zinc-900/60 p-4">
              <div className="flex items-start gap-2">
                <p className="flex-1 text-sm text-zinc-200">{GAP.gap}</p>
                <span className="shrink-0 text-xs font-medium capitalize text-amber-400">{GAP.severity}</span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{GAP.mitigation}</p>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
