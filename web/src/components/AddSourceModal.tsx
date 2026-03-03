/** Modal for adding a new CV source (file upload or paste text).
 *  .docx uploads → replace-cv flow (profile update + diff).
 *  .pdf uploads and paste text → add-source flow (career history only).
 */

import { useState, useRef } from 'react';

interface Props {
  onAdded: () => void;
  onClose: () => void;
}

type Mode = 'choose' | 'file' | 'text' | 'loading' | 'error';

export default function AddSourceModal({ onAdded, onClose }: Props) {
  const [mode, setMode] = useState<Mode>('choose');
  const [loadingLabel, setLoadingLabel] = useState('Processing…');
  const [pasteText, setPasteText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  /** .docx → full CV replace flow (3 steps). Returns true on success. */
  const handleDocxReplace = async (file: File): Promise<boolean> => {
    setLoadingLabel('Parsing CV…');
    const form = new FormData();
    form.append('file', file);
    const uploadResp = await fetch('/api/onboard/upload-cv', { method: 'POST', body: form });
    if (!uploadResp.ok) {
      const d = await uploadResp.json().catch(() => ({}));
      setError(d.detail || 'Upload failed. Please try again.');
      return false;
    }
    const { markdown } = await uploadResp.json();

    setLoadingLabel('Extracting profile…');
    const extractResp = await fetch('/api/onboard/generate-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_markdown: markdown }),
    });
    if (!extractResp.ok) {
      const d = await extractResp.json().catch(() => ({}));
      setError(d.detail || 'Profile generation failed. Please try again.');
      return false;
    }
    const extracted = await extractResp.json();

    setLoadingLabel('Merging…');
    const mergeResp = await fetch('/api/onboard/replace-cv', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cv_markdown: markdown,
        extracted_profile: extracted.profile,
        master_cv_json: extracted.master_cv_json,
      }),
    });
    if (!mergeResp.ok) {
      const d = await mergeResp.json().catch(() => ({}));
      setError(d.detail || 'Merge failed. Please try again.');
      return false;
    }
    return true;
  };

  const handleFile = async (file: File) => {
    setMode('loading');
    setError(null);
    try {
      if (file.name.toLowerCase().endsWith('.docx')) {
        const ok = await handleDocxReplace(file);
        if (!ok) { setMode('file'); return; }
      } else {
        setLoadingLabel('Processing…');
        const form = new FormData();
        form.append('file', file);
        const resp = await fetch('/api/onboard/add-source', { method: 'POST', body: form });
        if (!resp.ok) {
          const d = await resp.json().catch(() => ({}));
          setError(d.detail || 'Upload failed. Please try again.');
          setMode('file');
          return;
        }
      }
      onAdded();
    } catch {
      setError('Network error. Please try again.');
      setMode('file');
    }
  };

  const handlePaste = async () => {
    if (!pasteText.trim()) return;
    setMode('loading');
    setLoadingLabel('Processing…');
    setError(null);
    try {
      const resp = await fetch('/api/onboard/add-source', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: pasteText }),
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        setError(d.detail || 'Failed. Please try again.');
        setMode('text');
        return;
      }
      onAdded();
    } catch {
      setError('Network error. Please try again.');
      setMode('text');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Add a source</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-white text-lg leading-none">×</button>
        </div>

        {mode === 'choose' && (
          <div className="space-y-3">
            <button
              className="flex w-full items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-left text-sm font-medium text-zinc-200 transition hover:border-zinc-600"
              onClick={() => setMode('file')}
            >
              <span className="text-base">📄</span>
              <div>
                <div>Upload file</div>
                <div className="text-xs font-normal text-zinc-500">.docx CV or LinkedIn PDF</div>
              </div>
            </button>
            <button
              className="flex w-full items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-left text-sm font-medium text-zinc-200 transition hover:border-zinc-600"
              onClick={() => setMode('text')}
            >
              <span className="text-base">📋</span>
              <div>
                <div>Paste text</div>
                <div className="text-xs font-normal text-zinc-500">LinkedIn summary, bio, or resume text</div>
              </div>
            </button>
          </div>
        )}

        {mode === 'file' && (
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            <button
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-zinc-700 bg-zinc-900 py-8 text-sm text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200"
              onClick={() => fileRef.current?.click()}
            >
              Click to choose .docx or .pdf
            </button>
            {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
            <button onClick={() => setMode('choose')} className="mt-4 text-xs text-zinc-500 hover:text-zinc-300">← Back</button>
          </div>
        )}

        {mode === 'text' && (
          <div>
            <textarea
              className="w-full h-40 rounded-xl border border-zinc-800 bg-zinc-900 p-3 text-sm text-zinc-200 resize-none focus:outline-none focus:border-violet-500"
              placeholder="Paste your LinkedIn summary, bio, or resume text…"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
            <div className="mt-4 flex gap-3">
              <button
                className="flex-1 rounded-lg bg-violet-600 py-2 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:opacity-40"
                onClick={handlePaste}
                disabled={!pasteText.trim()}
              >
                Add
              </button>
              <button onClick={() => setMode('choose')} className="text-sm text-zinc-500 hover:text-zinc-300 px-3">Cancel</button>
            </div>
          </div>
        )}

        {mode === 'loading' && (
          <div className="py-6 text-center">
            <p className="text-sm text-zinc-400">{loadingLabel}</p>
            {loadingLabel !== 'Processing…' && (
              <p className="mt-1 text-xs text-zinc-600">This may take a moment…</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
