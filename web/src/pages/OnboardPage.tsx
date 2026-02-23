import { useState } from 'react';
import FileUpload from '../components/FileUpload';

interface Props {
  onComplete: (markdown: string) => void;
}

export default function OnboardPage({ onComplete }: Props) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('Only .docx files are supported. Please export your CV from Word or Google Docs.');
      return;
    }

    setLoading(true);
    const form = new FormData();
    form.append('file', file);

    const resp = await fetch('/api/onboard/upload-cv', { method: 'POST', body: form });
    setLoading(false);

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      setError(data.detail || 'Upload failed. Please try again.');
      return;
    }

    const data = await resp.json();
    setMarkdown(data.markdown);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-white mb-2">Set up your profile</h1>
      <p className="text-zinc-400 mb-8">Upload your CV to generate a personalised job-matching profile.</p>

      {!markdown && <FileUpload onFile={handleFile} />}

      {loading && <p className="text-zinc-400 mt-4 text-center">Extracting CV…</p>}

      {error && (
        <p className="mt-4 text-red-400 text-sm">{error}</p>
      )}

      {markdown && (
        <div className="mt-6">
          <h2 className="text-white font-semibold mb-2">CV Preview</h2>
          <pre className="bg-zinc-800 rounded-lg p-4 text-zinc-300 text-sm overflow-auto max-h-80 whitespace-pre-wrap">
            {markdown}
          </pre>
          <button
            className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2 rounded-lg"
            onClick={() => onComplete(markdown)}
          >
            Continue
          </button>
        </div>
      )}
    </div>
  );
}
