import { useState } from 'react';
import FileUpload from '../components/FileUpload';
import ProfileEditor from '../components/ProfileEditor';

function LinkedInGuidance() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <button
        className="flex w-full items-center justify-between text-left text-sm font-medium text-zinc-300 hover:text-white"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>💼 Add your LinkedIn PDF</span>
        <span className="text-zinc-500 text-xs">{open ? '▲ Hide' : '▼ Show steps'}</span>
      </button>
      {open && (
        <ol className="mt-3 space-y-1.5 text-xs text-zinc-400 list-decimal list-inside">
          <li>Go to your LinkedIn profile page</li>
          <li>
            Click <strong className="text-zinc-200">More</strong> →{' '}
            <strong className="text-zinc-200">Save to PDF</strong>
          </li>
          <li>Upload the downloaded PDF here alongside your CV</li>
        </ol>
      )}
    </div>
  );
}

interface Props {
  onComplete: () => void;
}

type Step = 'upload' | 'generating' | 'review';

export default function OnboardPage({ onComplete }: Props) {
  const [step, setStep] = useState<Step>('upload');
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [profile, setProfile] = useState<Parameters<typeof ProfileEditor>[0]['profile'] | null>(null);
  const [masterCvJson, setMasterCvJson] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFile = async (file: File) => {
    setError(null);
    const name = file.name.toLowerCase();
    if (!name.endsWith('.docx') && !name.endsWith('.pdf')) {
      setError('Only .docx and .pdf files are supported.');
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

  const handleContinue = async () => {
    if (!markdown) return;
    setStep('generating');
    setError(null);

    const resp = await fetch('/api/onboard/generate-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_markdown: markdown }),
    });

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      setError(data.detail || 'Profile generation failed. Please try again.');
      setStep('upload');
      return;
    }

    const data = await resp.json();
    setProfile(data.profile);
    setMasterCvJson(data.master_cv_json ?? null);
    setStep('review');
  };

  if (step === 'review' && profile && markdown) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12">
        <h1 className="text-2xl font-bold text-white mb-2">Review your profile</h1>
        <p className="text-zinc-400 mb-8">
          Adjust your preferences before activating your account.
        </p>
        <ProfileEditor
          profile={profile}
          cvMarkdown={markdown}
          masterCvJson={masterCvJson}
          onSaved={onComplete}
          isNew
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-white mb-2">Set up your profile</h1>
      <p className="text-zinc-400 mb-8">Upload your CV to generate a personalised job-matching profile.</p>

      {!markdown && step !== 'generating' && <FileUpload onFile={handleFile} />}
      {!markdown && step !== 'generating' && <LinkedInGuidance />}

      {loading && <p className="text-zinc-400 mt-4 text-center">Extracting CV…</p>}

      {step === 'generating' && (
        <p className="text-zinc-400 mt-4 text-center">Generating your profile…</p>
      )}

      {error && (
        <p className="mt-4 text-red-400 text-sm">{error}</p>
      )}

      {markdown && step === 'upload' && (
        <div className="mt-6">
          <h2 className="text-white font-semibold mb-2">CV Preview</h2>
          <pre className="bg-zinc-800 rounded-lg p-4 text-zinc-300 text-sm overflow-auto max-h-80 whitespace-pre-wrap">
            {markdown}
          </pre>
          <button
            className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2 rounded-lg"
            onClick={handleContinue}
          >
            Continue
          </button>
        </div>
      )}
    </div>
  );
}
