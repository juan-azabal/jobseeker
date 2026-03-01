import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import FileUpload from '../components/FileUpload';
import ProfileEditor from '../components/ProfileEditor';
import CVReplaceSummary from '../components/CVReplaceSummary';

interface Profile {
  name: string;
  email: string | null;
  languages: string[];
  home_locations: string[];
  current_level: string;
  track: string;
  target_level: string;
  role_type?: string;
  role_function?: string;
  domains: Record<string, number>;
  seniority_weights?: Record<string, number>;
  country_weights?: Record<string, number>;
  company_type_weights?: Record<string, number>;
  skills: string[];
  search_titles: string[];
  exclude_companies: string[];
  salary_min?: number;
  location_preference?: string;
}

interface MergedResult {
  merged_profile: Profile;
  diff: {
    skills_added: string[];
    skills_kept: string[];
    domains_added: Record<string, number>;
    domains_kept: Record<string, number>;
    fields_updated: string[];
    fields_preserved: string[];
  };
}

type Step = 'loading' | 'view' | 'upload' | 'generating' | 'review' | 'merged';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('loading');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cvMarkdown, setCvMarkdown] = useState('');
  const [pendingMarkdown, setPendingMarkdown] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [mergedResult, setMergedResult] = useState<MergedResult | null>(null);
  const [profileVersion, setProfileVersion] = useState(0);

  const loadProfile = () => {
    fetch('/api/onboard/profile')
      .then((r) => {
        if (!r.ok) throw new Error('no profile');
        return r.json();
      })
      .then((data) => {
        setProfile(data.profile);
        setCvMarkdown(data.cv_markdown);
        setProfileVersion((v) => v + 1);
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

    // Step 1: Extract profile data from new CV
    const extractResp = await fetch('/api/onboard/generate-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_markdown: pendingMarkdown }),
    });
    if (!extractResp.ok) {
      const data = await extractResp.json().catch(() => ({}));
      setError(data.detail || 'Profile generation failed. Please try again.');
      setStep('upload');
      return;
    }
    const extracted = await extractResp.json();

    // Step 2: Server-side additive merge
    const mergeResp = await fetch('/api/onboard/replace-cv', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_markdown: pendingMarkdown, extracted_profile: extracted }),
    });
    if (!mergeResp.ok) {
      const data = await mergeResp.json().catch(() => ({}));
      setError(data.detail || 'Profile merge failed. Please try again.');
      setStep('upload');
      return;
    }
    const result: MergedResult = await mergeResp.json();
    setMergedResult(result);
    setStep('merged');
  };

  const handleSaved = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    loadProfile();
    setStep('view');
    setPendingMarkdown(null);

    setMergedResult(null);
  };

  if (step === 'loading') return <div className="min-h-screen bg-zinc-950" />;

  // ── Show CV merge diff after CV replacement ───────────────────────────────
  if (step === 'merged' && mergedResult) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <CVReplaceSummary diff={mergedResult.diff} onDone={handleSaved} />
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
          <ProfileEditor key={profileVersion} profile={profile} cvMarkdown={cvMarkdown} onSaved={handleSaved} />
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
