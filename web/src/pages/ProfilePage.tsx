import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import FileUpload from '../components/FileUpload';
import ProfileEditor from '../components/ProfileEditor';

interface Profile {
  name: string;
  email: string | null;
  languages: string[];
  home_locations: string[];
  current_level: string;
  track: string;
  target_level: string;
  domains: Record<string, number>;
  skills: string[];
  exclude_companies: string[];
  salary_min?: number;
  location_preference?: string;
}

type Step = 'loading' | 'view' | 'upload' | 'generating' | 'review';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('loading');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cvMarkdown, setCvMarkdown] = useState('');
  const [pendingMarkdown, setPendingMarkdown] = useState<string | null>(null);
  const [newProfile, setNewProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadProfile = () => {
    fetch('/api/onboard/profile')
      .then((r) => {
        if (!r.ok) throw new Error('no profile');
        return r.json();
      })
      .then((data) => {
        setProfile(data.profile);
        setCvMarkdown(data.cv_markdown);
        setStep('view');
      })
      .catch(() => navigate('/onboard'));
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleFile = async (file: File) => {
    setError(null);
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('Only .docx files are supported.');
      return;
    }
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch('/api/onboard/upload-cv', { method: 'POST', body: form });
    setUploading(false);
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      setError(data.detail || 'Upload failed. Please try again.');
      return;
    }
    const data = await resp.json();
    setPendingMarkdown(data.markdown);
  };

  const handleGenerate = async () => {
    if (!pendingMarkdown) return;
    setStep('generating');
    setError(null);
    const resp = await fetch('/api/onboard/generate-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_markdown: pendingMarkdown }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      setError(data.detail || 'Profile generation failed. Please try again.');
      setStep('upload');
      return;
    }
    const profileData = await resp.json();
    setNewProfile(profileData);
    setStep('review');
  };

  const handleSaved = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    loadProfile();
    setStep('view');
    setPendingMarkdown(null);
    setNewProfile(null);
  };

  if (step === 'loading') return <div className="min-h-screen bg-zinc-950" />;

  // ── Review new profile after CV replacement ──────────────────────────────
  if (step === 'review' && newProfile && pendingMarkdown) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <button
          onClick={() => { setStep('upload'); setNewProfile(null); }}
          className="mb-6 flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
        >
          <span>←</span>
          <span>Back</span>
        </button>
        <h1 className="text-xl font-bold text-white">Review new profile</h1>
        <p className="mt-1 mb-8 text-sm text-zinc-500">Confirm the extracted data before saving.</p>
        <ProfileEditor profile={newProfile} cvMarkdown={pendingMarkdown} onSaved={handleSaved} isNew />
      </div>
    );
  }

  // ── Upload / generating state ─────────────────────────────────────────────
  if (step === 'upload' || step === 'generating') {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <button
          onClick={() => { setStep('view'); setPendingMarkdown(null); setError(null); }}
          className="mb-6 flex items-center gap-1.5 text-xs font-medium text-zinc-600 transition-colors hover:text-zinc-200"
        >
          <span>←</span>
          <span>Back to profile</span>
        </button>
        <h1 className="text-xl font-bold text-white">Update your CV</h1>
        <p className="mt-1 mb-8 text-sm text-zinc-500">Upload a new .docx to re-generate your profile.</p>

        {!pendingMarkdown && <FileUpload onFile={handleFile} />}
        {uploading && <p className="mt-4 text-center text-sm text-zinc-500">Extracting CV…</p>}
        {step === 'generating' && <p className="mt-4 text-center text-sm text-zinc-500">Generating your profile…</p>}
        {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

        {pendingMarkdown && step === 'upload' && (
          <div className="mt-6">
            <h2 className="mb-2 text-sm font-semibold text-white">CV Preview</h2>
            <pre className="max-h-72 overflow-auto rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-xs leading-relaxed text-zinc-400 whitespace-pre-wrap">
              {pendingMarkdown}
            </pre>
            <button
              className="mt-4 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white transition-all hover:bg-violet-500"
              onClick={handleGenerate}
            >
              Continue
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── View / edit current profile ───────────────────────────────────────────
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">My Profile</h1>
          <p className="mt-0.5 text-xs text-zinc-500">Your job-matching preferences</p>
        </div>
        {saved && (
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
            ✓ Saved
          </span>
        )}
      </div>

      {profile ? (
        <>
          <ProfileEditor profile={profile} cvMarkdown={cvMarkdown} onSaved={handleSaved} />
          <div className="mt-8 border-t border-zinc-800 pt-6">
            <button
              onClick={() => setStep('upload')}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200"
            >
              <span className="text-xs">📄</span>
              Replace CV
            </button>
          </div>
        </>
      ) : (
        <p className="text-sm text-zinc-500">No profile found.</p>
      )}
    </div>
  );
}
