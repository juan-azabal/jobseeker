import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import JobCard from '../components/JobCard';
import FilterBar, { type Filters } from '../components/FilterBar';
import { type JobSummary, type JobsResponse } from '../types/job';

const TIER_LABELS: Record<string, string> = {
  A: 'Tier A — Apply',
  B: 'Tier B — Review',
  C: 'Tier C — Skip',
};

function filtersToQuery(f: Filters): string {
  const params = new URLSearchParams();
  f.tiers.forEach((t) => params.append('tier', t.toLowerCase()));
  if (f.period !== 'all') params.set('period', f.period);
  return params.toString();
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [filters, setFilters] = useState<Filters>({ tiers: ['A', 'B', 'C'], period: 'all' });
  const navigate = useNavigate();

  useEffect(() => {
    const qs = filtersToQuery(filters);
    fetch(`/api/jobs${qs ? '?' + qs : ''}`)
      .then((r) => r.json())
      .then((data: JobsResponse) => setJobs(data.jobs));

    const url = new URL(window.location.href);
    if (filters.period !== 'all') url.searchParams.set('period', filters.period);
    else url.searchParams.delete('period');
    url.searchParams.delete('tier');
    filters.tiers.forEach((t) => url.searchParams.append('tier', t));
    window.history.replaceState({}, '', url.toString());
  }, [filters]);

  const grouped = (['A', 'B', 'C'] as const).map((tier) => ({
    tier,
    jobs: jobs.filter((j) => j.tier === tier),
  }));

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-white">Jobs</h1>
      <FilterBar filters={filters} onChange={setFilters} />
      <div className="space-y-8">
        {grouped.map(({ tier, jobs: tierJobs }) =>
          tierJobs.length > 0 ? (
            <section key={tier}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">
                {TIER_LABELS[tier]}
              </h2>
              <div className="space-y-2">
                {tierJobs.map((job) => (
                  <JobCard key={job.job_id} job={job} onClick={() => navigate(`/jobs/${job.job_id}`)} />
                ))}
              </div>
            </section>
          ) : null
        )}
      </div>
    </div>
  );
}
