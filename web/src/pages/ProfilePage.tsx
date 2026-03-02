import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import FileUpload from '../components/FileUpload';
import ProfileEditor from '../components/ProfileEditor';
import CVReplaceSummary from '../components/CVReplaceSummary';
import AddSourceModal from '../components/AddSourceModal';
import AddEntryModal from '../components/AddEntryModal';
import type { MasterCv } from '../types/masterCv';

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
  const [masterCv, setMasterCv] = useState<MasterCv | null>(null);
  const [showAddSource, setShowAddSource] = useState(false);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const loadMasterCv = () => {
    fetch('/api/onboard/master-cv')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setMasterCv(data))
      .catch(() => null);
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

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
        loadMasterCv();
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
      body: JSON.stringify({ cv_markdown: pendingMarkdown, extracted_profile: extracted.profile, master_cv_json: extracted.master_cv_json }),
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
      {/* Toast */}
      {(toast || saved) && (
        <div className="fixed top-4 right-4 z-50 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-medium text-emerald-400 shadow-lg">
          ✓ {toast || 'Saved'}
        </div>
      )}

      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">My Profile</h1>
          <p className="mt-0.5 text-xs text-zinc-500">Your job-matching preferences</p>
        </div>
      </div>

      {profile ? (
        <>
          <ProfileEditor key={profileVersion} profile={profile} cvMarkdown={cvMarkdown} onSaved={handleSaved} />

          {/* ── Master CV section ──────────────────────────────────────── */}
          <div className="mt-8 border-t border-zinc-800 pt-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Career history</h2>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowAddEntry(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200"
                >
                  + Add experience
                </button>
                <button
                  onClick={() => setShowAddSource(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-400 transition-all hover:border-zinc-500 hover:text-zinc-200"
                >
                  📄 Add source
                </button>
              </div>
            </div>

            {masterCv && masterCv.work.length > 0 ? (
              <div className="space-y-3">
                {masterCv.work.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-white">{entry.position}</p>
                        <p className="text-xs text-zinc-400">{entry.company}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-zinc-600">
                          {entry.start_date} – {entry.end_date ?? 'present'}
                        </span>
                        <SourceBadge source={entry.source} />
                      </div>
                    </div>
                    {entry.highlights.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {entry.highlights.slice(0, 2).map((h, i) => (
                          <li key={i} className="text-xs text-zinc-500 before:content-['•'] before:mr-1.5">
                            {h}
                          </li>
                        ))}
                        {entry.highlights.length > 2 && (
                          <li className="text-xs text-zinc-600">+{entry.highlights.length - 2} more</li>
                        )}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-600">
                No career history yet. Add your experience above.
              </p>
            )}
          </div>

          {/* ── CV actions ─────────────────────────────────────────────── */}
          <div className="mt-6">
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

      {/* Modals */}
      {showAddSource && (
        <AddSourceModal
          onAdded={() => {
            setShowAddSource(false);
            showToast('Source added');
            loadProfile();
          }}
          onClose={() => setShowAddSource(false)}
        />
      )}
      {showAddEntry && (
        <AddEntryModal
          existingSkills={profile?.skills ?? []}
          onAdded={(entryId) => {
            setShowAddEntry(false);
            showToast(`Entry ${entryId} added`);
            loadProfile();
          }}
          onClose={() => setShowAddEntry(false)}
        />
      )}
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  const label: Record<string, string> = {
    cv_upload: 'CV',
    linkedin_pdf: 'LinkedIn',
    manual: 'Manual',
    merged: 'Merged',
  };
  const colors: Record<string, string> = {
    cv_upload: 'bg-blue-900/30 text-blue-400 border-blue-800/30',
    linkedin_pdf: 'bg-sky-900/30 text-sky-400 border-sky-800/30',
    manual: 'bg-violet-900/30 text-violet-400 border-violet-800/30',
    merged: 'bg-zinc-800 text-zinc-400 border-zinc-700',
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium ${colors[source] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
    >
      {label[source] ?? source}
    </span>
  );
}
