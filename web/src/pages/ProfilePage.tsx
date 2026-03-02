import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
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

interface CvDiff {
  skills_added: string[];
  skills_kept: string[];
  domains_added: Record<string, number>;
  domains_kept: Record<string, number>;
  fields_updated: string[];
  fields_preserved: string[];
}

interface CvProcessing {
  status: 'processing' | 'done' | 'failed';
  started_at?: string;
  result?: { type?: string; diff?: CvDiff; error?: string };
}

type Step = 'loading' | 'view';

export default function ProfilePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('loading');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [cvMarkdown, setCvMarkdown] = useState('');

  const [saved, setSaved] = useState(false);
  const [profileVersion, setProfileVersion] = useState(0);
  const [masterCv, setMasterCv] = useState<MasterCv | null>(null);
  const [showAddSource, setShowAddSource] = useState(false);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [cvProcessing, setCvProcessing] = useState<CvProcessing | null>(null);

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
        setCvProcessing(data.cv_processing ?? null);
        setProfileVersion((v) => v + 1);
        setStep('view');
        loadMasterCv();
      })
      .catch(() => navigate('/onboard'));
  };

  useEffect(() => {
    loadProfile();
  }, []);

  // Poll every 5 s while background CV processing is running
  useEffect(() => {
    if (cvProcessing?.status !== 'processing') return;
    const id = setInterval(() => {
      fetch('/api/onboard/profile')
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (!data) return;
          setCvProcessing(data.cv_processing ?? null);
          if (data.cv_processing?.status !== 'processing') {
            setProfile(data.profile);
            loadMasterCv();
          }
        })
        .catch(() => null);
    }, 5000);
    return () => clearInterval(id);
  }, [cvProcessing?.status]);

  const handleAcceptMerge = async () => {
    await fetch('/api/onboard/accept-merge', { method: 'POST' }).catch(() => null);
    setCvProcessing(null);
    loadProfile();
  };

  const handleSaved = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
    loadProfile();
    setCvProcessing(null);
  };

  if (step === 'loading') return <div className="min-h-screen bg-zinc-950" />;

  // ── Show CV merge diff from async background task ─────────────────────────
  if (cvProcessing?.status === 'done' && cvProcessing.result?.diff) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <CVReplaceSummary diff={cvProcessing.result.diff} onDone={handleAcceptMerge} />
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

      {/* CV processing banner */}
      {cvProcessing?.status === 'processing' && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs font-medium text-amber-400">
          <span className="inline-block animate-spin">⟳</span>
          Processing your CV... This takes about a minute.
        </div>
      )}
      {cvProcessing?.status === 'failed' && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs font-medium text-red-400">
          <span>CV processing failed. Try again.</span>
          <button
            onClick={() => fetch('/api/onboard/accept-merge', { method: 'POST' }).then(() => setCvProcessing(null))}
            className="ml-2 text-red-400 hover:text-red-200"
            aria-label="Dismiss"
          >✕</button>
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
        </>
      ) : (
        <p className="text-sm text-zinc-500">No profile found.</p>
      )}

      {/* Modals */}
      {showAddSource && (
        <AddSourceModal
          onAdded={() => {
            setShowAddSource(false);
            showToast('Source added — processing in background');
            setCvProcessing({ status: 'processing' });
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
