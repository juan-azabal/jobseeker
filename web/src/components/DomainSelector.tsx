import { useEffect, useRef, useState } from 'react';
import { DOMAIN_GROUPS, DOMAIN_LABELS, domainLabel } from '../constants/domains';

interface Props {
  jobId: string;
  /** Current value from parser (e.g. job.parsed?.domain) */
  parsedDomain: string | null | undefined;
  /** User override stored in DB (job.domain_override) */
  domainOverride: string | null | undefined;
}

export default function DomainSelector({ jobId, parsedDomain, domainOverride }: Props) {
  const effectiveDomain = domainOverride ?? parsedDomain ?? 'other';

  const [selected, setSelected] = useState<string>(effectiveDomain);
  const [override, setOverride] = useState<string | null | undefined>(domainOverride);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch('');
      }
    }
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, []);

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false);
        setSearch('');
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (open && searchRef.current) {
      searchRef.current.focus();
    }
  }, [open]);

  const isOther = selected === 'other';
  const hasOverride = override != null;

  const chipClass = [
    'inline-flex cursor-pointer items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium transition-colors select-none',
    isOther
      ? 'border-amber-500 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20'
      : 'border-zinc-700 text-zinc-400 bg-zinc-800 hover:border-zinc-500 hover:text-zinc-200',
  ].join(' ');

  const handleSelect = async (domain: string | null) => {
    const prev = selected;
    const prevOverride = override;

    // Optimistic update
    const newDomain = domain ?? parsedDomain ?? 'other';
    setSelected(newDomain);
    setOverride(domain);
    setOpen(false);
    setSearch('');
    setError(null);

    try {
      const resp = await fetch(`/api/jobs/${jobId}/domain`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain }),
      });
      if (!resp.ok) {
        // Revert
        setSelected(prev);
        setOverride(prevOverride);
        setError('Failed to update domain');
      }
    } catch {
      // Revert
      setSelected(prev);
      setOverride(prevOverride);
      setError('Failed to update domain');
    }
  };

  // Filter groups by search query
  const query = search.toLowerCase().trim();
  const filteredGroups = DOMAIN_GROUPS
    .map((group) => ({
      ...group,
      domains: group.domains.filter((d) => {
        if (!query) return true;
        const label = (DOMAIN_LABELS as Record<string, string>)[d] ?? d;
        return label.toLowerCase().includes(query) || d.toLowerCase().includes(query);
      }),
    }))
    .filter((g) => g.domains.length > 0);

  return (
    <div ref={ref} className="relative inline-flex flex-col">
      <button
        type="button"
        className={chipClass}
        onClick={() => { setOpen((o) => !o); setError(null); }}
        title="Click to correct domain"
      >
        <span className="capitalize">{domainLabel(selected)}</span>
        {hasOverride && <span className="text-zinc-500 text-xs">✏</span>}
        {isOther && !hasOverride && (
          <span className="text-amber-500/70 text-xs" title="Parser couldn't determine domain — click to correct">?</span>
        )}
      </button>

      {error && (
        <span className="mt-1 text-xs text-red-400">{error}</span>
      )}

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl shadow-black/40">
          {/* Search */}
          <div className="border-b border-zinc-800 p-2">
            <input
              ref={searchRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search domains…"
              className="w-full rounded bg-zinc-800 px-3 py-1.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
            />
          </div>

          {/* Groups */}
          <div className="max-h-72 overflow-y-auto py-1">
            {filteredGroups.length === 0 && (
              <p className="px-3 py-3 text-xs text-zinc-600">No domains match</p>
            )}
            {filteredGroups.map((group) => (
              <div key={group.label}>
                <p className="px-3 pb-0.5 pt-2 text-xs uppercase tracking-wide text-zinc-500">
                  {group.label}
                </p>
                {group.domains.map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={[
                      'w-full px-3 py-1.5 text-left text-sm transition-colors',
                      d === selected
                        ? 'bg-zinc-800 text-violet-400'
                        : 'cursor-pointer text-zinc-300 hover:bg-zinc-800',
                    ].join(' ')}
                    onClick={() => handleSelect(d)}
                  >
                    {(DOMAIN_LABELS as Record<string, string>)[d] ?? d}
                    {d === selected && (
                      <span className="ml-1.5 text-xs text-violet-500">✓</span>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </div>

          {/* Clear override */}
          {hasOverride && (
            <div className="border-t border-zinc-800 p-1">
              <button
                type="button"
                className="w-full px-3 py-1.5 text-left text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                onClick={() => handleSelect(null)}
              >
                Clear override (revert to parser value)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
