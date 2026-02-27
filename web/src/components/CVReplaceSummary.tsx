interface Diff {
  skills_added: string[];
  skills_kept: string[];
  domains_added: Record<string, number>;
  domains_kept: Record<string, number>;
  fields_updated: string[];
  fields_preserved: string[];
}

interface Props {
  diff: Diff;
  onDone: () => void;
}

const FIELD_LABELS: Record<string, string> = {
  name: 'Name',
  email: 'Email',
  languages: 'Languages',
  home_locations: 'Home locations',
  current_level: 'Current level',
  target_level: 'Target level',
  seniority_weights: 'Seniority preferences',
  country_weights: 'Country preferences',
  company_type_weights: 'Company type preferences',
};

export default function CVReplaceSummary({ diff, onDone }: Props) {
  const totalSkillsAdded = diff.skills_added.length;
  const totalDomainsAdded = Object.keys(diff.domains_added).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">CV updated</h1>
        <p className="mt-1 text-sm text-zinc-400">
          {totalSkillsAdded > 0 || totalDomainsAdded > 0
            ? `${totalSkillsAdded} new skill${totalSkillsAdded !== 1 ? 's' : ''} and ${totalDomainsAdded} new domain${totalDomainsAdded !== 1 ? 's' : ''} added to your profile.`
            : 'Your profile has been updated with the latest CV data.'}
        </p>
      </div>

      {/* Skills */}
      {(diff.skills_added.length > 0 || diff.skills_kept.length > 0) && (
        <div>
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">Skills</h2>
          <div className="flex flex-wrap gap-2">
            {diff.skills_kept.map((s) => (
              <span
                key={s}
                className="rounded bg-zinc-700 px-2 py-1 text-xs text-zinc-300"
              >
                {s}
              </span>
            ))}
            {diff.skills_added.map((s) => (
              <span
                key={s}
                className="rounded border border-emerald-500/50 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300"
              >
                {s}
                <span className="ml-1.5 rounded bg-emerald-600/30 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">
                  new
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Domains */}
      {(Object.keys(diff.domains_added).length > 0 || Object.keys(diff.domains_kept).length > 0) && (
        <div>
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">Domains</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(diff.domains_kept).map(([k, w]) => (
              <span key={k} className="rounded bg-zinc-700 px-2 py-1 text-xs text-zinc-300">
                {k} <span className="text-zinc-500">{w > 0 ? `+${w}` : w}</span>
              </span>
            ))}
            {Object.entries(diff.domains_added).map(([k, w]) => (
              <span
                key={k}
                className="rounded border border-emerald-500/50 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300"
              >
                {k} <span className="text-emerald-500">{w > 0 ? `+${w}` : w}</span>
                <span className="ml-1.5 rounded bg-emerald-600/30 px-1 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">
                  new
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Updated factual fields */}
      {diff.fields_updated.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-zinc-300">Updated fields</h2>
          <ul className="space-y-1">
            {diff.fields_updated.map((f) => (
              <li key={f} className="flex items-center gap-2 text-xs text-zinc-400">
                <span className="text-emerald-400">✓</span>
                {FIELD_LABELS[f] ?? f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Preserved preferences */}
      {diff.fields_preserved.length > 0 && (
        <p className="text-xs text-zinc-500">
          Your {diff.fields_preserved.map((f) => FIELD_LABELS[f] ?? f).join(', ')} were preserved.
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          onClick={onDone}
          className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-all hover:bg-violet-500"
        >
          Looks good
        </button>
        <button
          onClick={onDone}
          className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200"
        >
          Review in profile
        </button>
      </div>
    </div>
  );
}
