/** Modal for manually adding a work experience or project entry.
 *  Calls POST /api/onboard/add-entry. On success, calls onAdded().
 */

import { useState } from 'react';
import type { AddEntryPayload } from '../types/masterCv';

interface Props {
  existingSkills?: string[];
  onAdded: (entryId: string) => void;
  onClose: () => void;
}

type EntryType = 'work' | 'project';

const MAX_HIGHLIGHTS = 8;

export default function AddEntryModal({ existingSkills = [], onAdded, onClose }: Props) {
  const [entryType, setEntryType] = useState<EntryType>('work');
  const [company, setCompany] = useState('');
  const [position, setPosition] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [location, setLocation] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [isCurrent, setIsCurrent] = useState(false);
  const [summary, setSummary] = useState('');
  const [highlights, setHighlights] = useState<string[]>(['']);
  const [skillInput, setSkillInput] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addHighlight = () => {
    if (highlights.length < MAX_HIGHLIGHTS) setHighlights([...highlights, '']);
  };
  const removeHighlight = (i: number) => setHighlights(highlights.filter((_, idx) => idx !== i));
  const updateHighlight = (i: number, val: string) =>
    setHighlights(highlights.map((h, idx) => (idx === i ? val : h)));

  const addSkill = (skill: string) => {
    const s = skill.trim();
    if (s && !skills.includes(s)) setSkills([...skills, s]);
    setSkillInput('');
  };
  const removeSkill = (skill: string) => setSkills(skills.filter((s) => s !== skill));

  const filledHighlights = highlights.filter((h) => h.trim());

  const canSubmit =
    filledHighlights.length >= 1 &&
    (entryType === 'work' ? company.trim() && position.trim() : name.trim());

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);

    const payload: AddEntryPayload = {
      type: entryType,
      highlights: filledHighlights,
      start_date: startDate || undefined,
      end_date: isCurrent ? null : endDate || undefined,
      summary: summary || undefined,
    };

    if (entryType === 'work') {
      payload.company = company.trim();
      payload.position = position.trim();
      payload.location = location || undefined;
      payload.skills_used = skills;
    } else {
      payload.name = name.trim();
      payload.url = url || undefined;
      payload.description = summary || undefined;
      payload.keywords = skills;
    }

    try {
      const resp = await fetch('/api/onboard/add-entry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || 'Failed to add entry. Please try again.');
        setSubmitting(false);
        return;
      }
      const data = await resp.json();
      onAdded(data.entry_id);
    } catch {
      setError('Network error. Please try again.');
      setSubmitting(false);
    }
  };

  const suggestedSkills = existingSkills.filter(
    (s) => !skills.includes(s) && s.toLowerCase().includes(skillInput.toLowerCase()),
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-950 p-6 shadow-xl mx-4">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Add experience</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-white text-lg leading-none">×</button>
        </div>

        {/* Type toggle */}
        <div className="mb-5 flex rounded-lg border border-zinc-800 p-1 gap-1">
          {(['work', 'project'] as EntryType[]).map((t) => (
            <button
              key={t}
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition ${
                entryType === t
                  ? 'bg-zinc-700 text-white'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
              onClick={() => setEntryType(t)}
            >
              {t === 'work' ? 'Work experience' : 'Project'}
            </button>
          ))}
        </div>

        <div className="space-y-4">
          {/* Work-specific fields */}
          {entryType === 'work' && (
            <>
              <Field label="Company *">
                <input
                  className={inputCls}
                  placeholder="e.g. Acme Corp"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </Field>
              <Field label="Position *">
                <input
                  className={inputCls}
                  placeholder="e.g. Senior Product Manager"
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                />
              </Field>
              <Field label="Location">
                <input
                  className={inputCls}
                  placeholder="e.g. Barcelona, Spain"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </Field>
            </>
          )}

          {/* Project-specific fields */}
          {entryType === 'project' && (
            <>
              <Field label="Project name *">
                <input
                  className={inputCls}
                  placeholder="e.g. Open Source Dashboard"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
              <Field label="URL">
                <input
                  className={inputCls}
                  placeholder="https://..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </Field>
            </>
          )}

          {/* Dates */}
          <div className="flex gap-3">
            <Field label="Start date" className="flex-1">
              <input
                className={inputCls}
                placeholder="YYYY-MM"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </Field>
            <Field label="End date" className="flex-1">
              <input
                className={inputCls}
                placeholder="YYYY-MM"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={isCurrent}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
            <input
              type="checkbox"
              checked={isCurrent}
              onChange={(e) => setIsCurrent(e.target.checked)}
              className="accent-violet-500"
            />
            Current role
          </label>

          {/* Summary / description */}
          <Field label={entryType === 'work' ? 'Summary' : 'Description'}>
            <textarea
              className={`${inputCls} h-20 resize-none`}
              placeholder="Brief overview…"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </Field>

          {/* Highlights */}
          <Field label="Highlights * (at least 1)">
            <div className="space-y-2">
              {highlights.map((h, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    className={`${inputCls} flex-1`}
                    placeholder={`Achievement ${i + 1}…`}
                    value={h}
                    onChange={(e) => updateHighlight(i, e.target.value)}
                  />
                  {highlights.length > 1 && (
                    <button
                      onClick={() => removeHighlight(i)}
                      className="text-zinc-600 hover:text-red-400 text-sm px-1"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              {highlights.length < MAX_HIGHLIGHTS && (
                <button
                  onClick={addHighlight}
                  className="text-xs text-violet-400 hover:text-violet-300"
                >
                  + Add highlight
                </button>
              )}
            </div>
          </Field>

          {/* Skills */}
          <Field label={entryType === 'work' ? 'Skills used' : 'Keywords'}>
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="flex items-center gap-1 rounded-full bg-violet-900/40 border border-violet-700/30 px-2.5 py-0.5 text-xs text-violet-300"
                  >
                    {s}
                    <button onClick={() => removeSkill(s)} className="text-violet-500 hover:text-violet-200 leading-none">×</button>
                  </span>
                ))}
              </div>
              <input
                className={inputCls}
                placeholder="Type skill and press Enter…"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') { e.preventDefault(); addSkill(skillInput); }
                }}
              />
              {skillInput && suggestedSkills.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {suggestedSkills.slice(0, 5).map((s) => (
                    <button
                      key={s}
                      onClick={() => addSkill(s)}
                      className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-xs text-zinc-300 hover:border-zinc-500"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Field>
        </div>

        {error && <p className="mt-4 text-xs text-red-400">{error}</p>}

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          <button
            className="flex-1 rounded-lg bg-violet-600 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:opacity-40"
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
          >
            {submitting ? 'Saving…' : 'Add'}
          </button>
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-800 px-4 text-sm text-zinc-400 hover:text-zinc-200"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

const inputCls =
  'w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-violet-500 disabled:opacity-40';

function Field({
  label,
  children,
  className = '',
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-xs font-medium text-zinc-400">{label}</label>
      {children}
    </div>
  );
}
