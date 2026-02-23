import { useEffect, useState } from 'react';
import JobCard from '../components/JobCard';
import { JobSummary, JobsResponse } from '../types/job';

const TIER_LABELS: Record<string, string> = {
  A: 'Tier A — Apply',
  B: 'Tier B — Review',
  C: 'Tier C — Skip',
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);

  useEffect(() => {
    fetch('/api/jobs')
      .then((r) => r.json())
      .then((data: JobsResponse) => setJobs(data.jobs));
  }, []);

  const grouped = (['A', 'B', 'C'] as const).map((tier) => ({
    tier,
    jobs: jobs.filter((j) => j.tier === tier),
  }));

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8">
      <h1 className="mb-8 text-2xl font-bold text-white">Jobs</h1>
      <div className="space-y-8">
        {grouped.map(({ tier, jobs: tierJobs }) =>
          tierJobs.length > 0 ? (
            <section key={tier}>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-400">
                {TIER_LABELS[tier]}
              </h2>
              <div className="space-y-2">
                {tierJobs.map((job) => (
                  <JobCard key={job.job_id} job={job} />
                ))}
              </div>
            </section>
          ) : null
        )}
      </div>
    </div>
  );
}
