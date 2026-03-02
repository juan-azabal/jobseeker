/** Modal for adding a new CV source (file upload or paste text).
 *  Calls POST /api/onboard/add-source. On success, calls onAdded().
 */

import { useState, useRef } from 'react';

interface Props {
  onAdded: () => void;
  onClose: () => void;
}

type Mode = 'choose' | 'file' | 'text' | 'loading' | 'error';

export default function AddSourceModal({ onAdded, onClose }: Props) {
  const [mode, setMode] = useState<Mode>('choose');
  const [pasteText, setPasteText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setMode('loading');
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const resp = await fetch('/api/onboard/add-source', { method: 'POST', body: form });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || 'Upload failed. Please try again.');
        setMode('file');
        return;
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
    setError(null);
    try {
      const resp = await fetch('/api/onboard/add-source', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: pasteText }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data.detail || 'Failed. Please try again.');
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
                <div className="text-xs font-normal text-zinc-500">.pdf or .docx</div>
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
              Click to choose .pdf or .docx
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
          <p className="text-center text-sm text-zinc-400 py-6">Processing…</p>
        )}
      </div>
    </div>
  );
}
