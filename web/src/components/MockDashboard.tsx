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

interface MockJob {
  title: string;
  company: string;
  location: string;
  location_type: string;
  score: number;
  tier: 'A' | 'B' | 'C';
  skills: string[];
}

const MOCK_JOBS: MockJob[] = [
  {
    title: 'Head of Product',
    company: 'Series B · B2B SaaS',
    location: 'Barcelona',
    location_type: 'Remote',
    score: 91,
    tier: 'A',
    skills: ['Product Strategy', 'SQL', 'B2B Platforms'],
  },
  {
    title: 'Product Lead, Payments',
    company: 'Fintech Scale-up',
    location: 'London',
    location_type: 'Hybrid',
    score: 82,
    tier: 'A',
    skills: ['Fintech', 'API Design'],
  },
  {
    title: 'Senior PM, Marketplace',
    company: 'Series A Startup',
    location: 'Berlin',
    location_type: 'Remote',
    score: 68,
    tier: 'B',
    skills: ['Marketplace', 'Growth', 'Analytics'],
  },
  {
    title: 'Group PM, Infrastructure',
    company: 'Enterprise Corp',
    location: 'Amsterdam',
    location_type: 'On-site',
    score: 41,
    tier: 'C',
    skills: ['Cloud Infra', 'Kubernetes'],
  },
];

function MockJobCard({ job }: { job: MockJob }) {
  return (
    <div
      className={`rounded-lg border border-l-4 bg-zinc-900 p-4 border-zinc-800 ${TIER_BORDER[job.tier]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-white">{job.title}</h3>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-zinc-500">
            <span>{job.company}</span>
            <span className="text-zinc-700">·</span>
            <span>{job.location}</span>
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-500 capitalize">
              {job.location_type}
            </span>
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {job.skills.map((skill) => (
              <span key={skill} className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                {skill}
              </span>
            ))}
          </div>
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
    </div>
  );
}

export default function MockDashboard() {
  return (
    <div
      className="pointer-events-none opacity-[0.85]"
      style={{ transform: 'perspective(1200px) rotateY(-2deg)' }}
    >
      {/* Browser frame */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center gap-3 border-b border-zinc-800 bg-zinc-900 px-4 py-3">
          <div className="flex gap-1.5">
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
            <div className="h-2 w-2 rounded-full bg-zinc-700" />
          </div>
          <div className="mx-auto rounded-full bg-zinc-800 px-4 py-1 text-xs text-zinc-500">
            jobseeker-production.up.railway.app/jobs
          </div>
        </div>
        {/* Job list */}
        <div className="flex flex-col gap-3 p-4">
          {MOCK_JOBS.map((job) => (
            <MockJobCard key={job.title} job={job} />
          ))}
        </div>
      </div>
    </div>
  );
}
