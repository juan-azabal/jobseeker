import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import JobCard from '../components/JobCard';
import FilterBar, { type Filters } from '../components/FilterBar';
import { type JobSummary, type JobsResponse } from '../types/job';

const TIER_CONFIG: Record<string, { label: string; dotColor: string }> = {
  A: { label: 'Apply', dotColor: 'bg-emerald-500' },
  B: { label: 'Review', dotColor: 'bg-amber-400' },
  C: { label: 'Skip', dotColor: 'bg-zinc-500' },
};

function filtersToQuery(f: Filters): string {
  const params = new URLSearchParams();
  f.tiers.forEach((t) => params.append('tier', t.toLowerCase()));
  if (f.period !== 'all') params.set('period', f.period);
  if (f.hideApplied) params.set('hide_applied', 'true');
  return params.toString();
}

function buildCVPrompt(jobs: JobSummary[]): string {
  return jobs
    .map(
      (j) =>
        `**${j.title}** at ${j.company} (${j.location})\nScore: ${j.score} | URL: ${j.url}`,
    )
    .join('\n\n');
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>({ tiers: ['A', 'B'], period: 'all', hideApplied: false });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const [applying, setApplying] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    const qs = filtersToQuery(filters);
    fetch(`/api/jobs${qs ? '?' + qs : ''}`)
      .then((r) => r.json())
      .then((data: JobsResponse) => {
        setJobs(data.jobs);
        setLoading(false);
      });

    const url = new URL(window.location.href);
    if (filters.period !== 'all') url.searchParams.set('period', filters.period);
    else url.searchParams.delete('period');
    url.searchParams.delete('tier');
    filters.tiers.forEach((t) => url.searchParams.append('tier', t));
    window.history.replaceState({}, '', url.toString());
  }, [filters]);

  const toggleSelect = (jobId: string, sel: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (sel) next.add(jobId);
      else next.delete(jobId);
      return next;
    });
  };

  const handleBulkApply = async () => {
    setApplying(true);
    await Promise.all(
      [...selected].map((id) =>
        fetch(`/api/jobs/${id}/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ applied: true }),
        }),
      ),
    );
    setApplying(false);
    setSelected(new Set());
    // Refresh list — if hiding applied, they'll disappear; otherwise badge appears
    const qs = filtersToQuery(filters);
    const data: JobsResponse = await fetch(`/api/jobs${qs ? '?' + qs : ''}`).then((r) => r.json());
    setJobs(data.jobs);
  };

  const handleBulkCVCopy = () => {
    const selectedJobs = jobs.filter((j) => selected.has(j.job_id));
    const prompt = `Generate CVs for these roles:\n\n${buildCVPrompt(selectedJobs)}`;
    navigator.clipboard.writeText(prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const grouped = (['A', 'B', 'C'] as const).map((tier) => ({
    tier,
    jobs: jobs.filter((j) => j.tier === tier),
  }));

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-6">
      <div className="mx-auto max-w-2xl">
        <FilterBar filters={filters} onChange={setFilters} />

        {loading ? (
          <div className="mt-16 text-center">
            <p className="text-xs text-zinc-600">Loading…</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="mt-16 text-center">
            <p className="text-sm text-zinc-600">No jobs match your current filters.</p>
            <button
              onClick={() => setFilters({ tiers: ['A', 'B'], period: 'all', hideApplied: false })}
              className="mt-3 text-xs text-zinc-500 underline hover:text-zinc-300 transition-colors"
            >
              Reset filters
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {grouped.map(({ tier, jobs: tierJobs }) =>
              tierJobs.length > 0 ? (
                <section key={tier}>
                  <div className="mb-3 flex items-center gap-2">
                    <span className={`h-1.5 w-1.5 rounded-full ${TIER_CONFIG[tier].dotColor}`} />
                    <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">
                      {TIER_CONFIG[tier].label}
                    </h2>
                    <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-xs font-medium text-zinc-500">
                      {tierJobs.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {tierJobs.map((job) => (
                      <JobCard
                        key={job.job_id}
                        job={job}
                        selected={selected.has(job.job_id)}
                        onSelect={(sel) => toggleSelect(job.job_id, sel)}
                        onClick={() => navigate(`/jobs/${job.job_id}`)}
                      />
                    ))}
                  </div>
                </section>
              ) : null
            )}
          </div>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30">
          <div className="flex items-center gap-3 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 shadow-2xl shadow-black/60">
            <span className="text-sm font-medium text-zinc-300">
              {selected.size} {selected.size === 1 ? 'job' : 'jobs'} selected
            </span>
            <div className="h-4 w-px bg-zinc-700" />
            <button
              onClick={handleBulkCVCopy}
              className="flex items-center gap-2 rounded-lg bg-violet-600 px-3.5 py-1.5 text-sm font-semibold text-white transition-all hover:bg-violet-500"
            >
              {copied ? (
                <>
                  <span className="text-violet-200">✓</span>
                  Copied!
                </>
              ) : (
                <>
                  <span className="text-xs">📄</span>
                  Generate CVs
                </>
              )}
            </button>
            <button
              onClick={handleBulkApply}
              disabled={applying}
              className="flex items-center gap-2 rounded-lg bg-emerald-700 px-3.5 py-1.5 text-sm font-semibold text-white transition-all hover:bg-emerald-600 disabled:opacity-50"
            >
              {applying ? 'Applying…' : 'Mark applied'}
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
