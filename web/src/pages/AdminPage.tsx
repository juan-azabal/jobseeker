import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { useAuth } from '../context/AuthContext';

interface AdminUser {
  id: number;
  email: string;
  name: string;
  profile_id: string | null;
  is_admin: number;
  has_cv: number;
  has_yaml: number;
  created_at: string;
  last_login: string;
}

export default function AdminPage() {
  const { user, isLoading, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState(false);
  const [resetting, setResetting] = useState<number | null>(null);
  const [clearingSeen, setClearingSeen] = useState<number | null>(null);
  const [impersonating, setImpersonating] = useState<number | null>(null);
  const [profile, setProfile] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillResult, setBackfillResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [reparseScoring, setReparseScoring] = useState(false);
  const [reparseScoringResult, setReparseScoringResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Domain reparse state
  const [reparsePreviewing, setReparsePreviewing] = useState(false);
  const [reparsePreviewResult, setReparsePreviewResult] = useState<{
    domain_other_count: number;
    sample: { job_id: string; company: string; title: string; inferred: string }[];
  } | null>(null);
  const [reparseRunning, setReparseRunning] = useState(false);
  const [reparseResult, setReparseResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Domain corrections state
  const [corrections, setCorrections] = useState<{ from: string; to: string; count: number }[] | null>(null);
  const [correctionsError, setCorrectionsError] = useState(false);

  // Waitlist state
  const [waitlist, setWaitlist] = useState<{ id: number; email: string; created_at: string }[] | null>(null);
  const [waitlistError, setWaitlistError] = useState(false);

  // Inline profile-id edit state
  const [editingProfileId, setEditingProfileId] = useState<{ userId: number; value: string } | null>(null);
  const [savingProfileId, setSavingProfileId] = useState(false);

  const loadUsers = () => {
    setUsersLoading(true);
    fetch('/api/admin/users')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: AdminUser[]) => {
        setUsers(data);
        setUsersError(false);
      })
      .catch(() => setUsersError(true))
      .finally(() => setUsersLoading(false));
  };

  const loadWaitlist = () => {
    fetch('/api/admin/waitlist')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setWaitlist(data.entries);
        setWaitlistError(false);
      })
      .catch(() => setWaitlistError(true));
  };

  const loadCorrections = () => {
    fetch('/api/admin/domain-corrections')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setCorrections(data.corrections);
        setCorrectionsError(false);
      })
      .catch(() => setCorrectionsError(true));
  };

  // Fetch users, corrections, and waitlist — must be before early returns to satisfy Rules of Hooks
  useEffect(() => {
    loadUsers();
    loadCorrections();
    loadWaitlist();
  }, []);

  // Redirect non-admins (after hooks)
  if (!isLoading && (!user || !user.is_admin)) {
    return <Navigate to="/jobs" replace />;
  }

  async function handleTrigger() {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const body = profile.trim() ? { profile: profile.trim() } : {};
      const r = await fetch('/api/admin/trigger-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (r.ok) {
        const label = data.profile ? `profile "${data.profile}"` : 'all active profiles';
        setTriggerResult({ ok: true, message: `Pipeline triggered for ${label}` });
      } else {
        setTriggerResult({ ok: false, message: data.detail || 'Trigger failed' });
      }
    } catch {
      setTriggerResult({ ok: false, message: 'Network error' });
    } finally {
      setTriggering(false);
    }
  }

  async function handleReparseRescore() {
    setReparseScoring(true);
    setReparseScoringResult(null);
    try {
      const body: Record<string, string> = { mode: 'reparse_rescore' };
      if (profile.trim()) body.profile = profile.trim();
      const r = await fetch('/api/admin/trigger-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (r.ok) {
        const label = data.profile ? `profile "${data.profile}"` : 'all active profiles';
        setReparseScoringResult({ ok: true, message: `Reparse+rescore triggered for ${label}` });
      } else {
        setReparseScoringResult({ ok: false, message: data.detail || 'Trigger failed' });
      }
    } catch {
      setReparseScoringResult({ ok: false, message: 'Network error' });
    } finally {
      setReparseScoring(false);
    }
  }

  async function handleBackfill() {
    setBackfilling(true);
    setBackfillResult(null);
    try {
      const r = await fetch('/api/admin/backfill-embeddings', { method: 'POST' });
      const data = await r.json();
      if (r.status === 202) {
        setBackfillResult({ ok: true, message: 'Backfill started — running in background. Check server logs for progress.' });
      } else if (r.ok) {
        setBackfillResult({ ok: true, message: `Cached ${data.cached ?? '?'}/${data.total ?? '?'} skills` });
      } else {
        setBackfillResult({ ok: false, message: data.detail || 'Backfill failed' });
      }
    } catch {
      setBackfillResult({ ok: false, message: 'Network error' });
    } finally {
      setBackfilling(false);
    }
  }

  async function handleDbImport() {
    setImporting(true);
    setImportResult(null);
    try {
      const r = await fetch('/api/admin/db-import', { method: 'POST' });
      const data = await r.json();
      if (r.ok) {
        setImportResult({ ok: true, message: data.message || 'Database imported from production.' });
      } else {
        setImportResult({ ok: false, message: data.detail || 'Import failed' });
      }
    } catch {
      setImportResult({ ok: false, message: 'Network error' });
    } finally {
      setImporting(false);
    }
  }

  async function handleReparsePreview() {
    setReparsePreviewing(true);
    setReparsePreviewResult(null);
    setReparseResult(null);
    try {
      const r = await fetch('/api/admin/reparse-domains/preview');
      if (r.ok) {
        setReparsePreviewResult(await r.json());
      } else {
        const data = await r.json();
        setReparseResult({ ok: false, message: data.detail || 'Preview failed' });
      }
    } catch {
      setReparseResult({ ok: false, message: 'Network error' });
    } finally {
      setReparsePreviewing(false);
    }
  }

  async function handleReparse() {
    setReparseRunning(true);
    setReparseResult(null);
    setReparsePreviewResult(null);
    try {
      const r = await fetch('/api/admin/reparse-domains', { method: 'POST' });
      const data = await r.json();
      if (r.ok) {
        setReparseResult({ ok: true, message: `Reclassified ${data.reclassified}/${data.total_other} jobs` });
      } else {
        setReparseResult({ ok: false, message: data.detail || 'Reparse failed' });
      }
    } catch {
      setReparseResult({ ok: false, message: 'Network error' });
    } finally {
      setReparseRunning(false);
    }
  }

  async function handleResetOnboarding(userId: number, userName: string) {
    if (!confirm(`Reset onboarding for "${userName}"? They will be sent back to the onboarding flow. Job history is preserved.`)) return;
    setResetting(userId);
    try {
      const r = await fetch(`/api/admin/users/${userId}/reset-onboarding`, { method: 'POST' });
      if (r.ok) loadUsers();
      else alert('Reset failed');
    } catch {
      alert('Network error');
    } finally {
      setResetting(null);
    }
  }

  async function handleClearSeen(userId: number, profileId: string) {
    if (!confirm(`Clear seen job IDs for "${profileId}"? Jobs will be re-scraped on next run.`)) return;
    setClearingSeen(userId);
    try {
      const r = await fetch('/api/admin/reset-seen-ids', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      });
      if (r.ok) alert(`Seen IDs cleared for ${profileId}`);
      else alert('Clear failed');
    } catch {
      alert('Network error');
    } finally {
      setClearingSeen(null);
    }
  }

  async function handleImpersonate(userId: number) {
    setImpersonating(userId);
    try {
      const r = await fetch(`/api/admin/impersonate/${userId}`, { method: 'POST' });
      if (r.ok) {
        await refreshUser();
        navigate('/jobs');
      } else {
        alert('Impersonation failed');
      }
    } catch {
      alert('Network error');
    } finally {
      setImpersonating(null);
    }
  }

  async function handleSaveProfileId(userId: number) {
    if (!editingProfileId) return;
    setSavingProfileId(true);
    try {
      const r = await fetch(`/api/admin/users/${userId}/profile-id`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: editingProfileId.value.trim() || null }),
      });
      if (r.ok) {
        setEditingProfileId(null);
        loadUsers();
      } else {
        const data = await r.json();
        alert(data.detail || 'Failed to update profile ID');
      }
    } catch {
      alert('Network error');
    } finally {
      setSavingProfileId(false);
    }
  }

  if (isLoading) return <div className="min-h-screen bg-zinc-950" />;

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="mb-8 text-xl font-bold text-white">Admin</h1>

      {/* Staging: DB refresh from production */}
      {import.meta.env.VITE_ENVIRONMENT === 'staging' && (
        <section className="mb-10 rounded-xl border border-amber-500/30 bg-amber-500/5 p-6">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-amber-400">
            Staging — Data Refresh
          </h2>
          <p className="mb-4 text-sm text-zinc-500">
            Replace the staging database with a fresh snapshot from production.
            This will restart the server.
          </p>
          <button
            onClick={handleDbImport}
            disabled={importing}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-500 disabled:opacity-50"
          >
            {importing ? 'Importing…' : 'Refresh from production'}
          </button>
          {importResult && (
            <p className={`mt-3 text-sm ${importResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
              {importResult.message}
            </p>
          )}
        </section>
      )}

      {/* Pipeline trigger */}
      <section className="mb-10 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Pipeline
        </h2>
        <p className="mb-4 text-sm text-zinc-500">
          Dispatch the GHA scraping workflow. Leave profile blank to run all active profiles.
        </p>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Profile ID (e.g. juan)"
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !triggering && handleTrigger()}
            className="w-52 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-violet-500 focus:outline-none"
          />
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:opacity-50"
          >
            {triggering ? 'Triggering…' : 'Run pipeline'}
          </button>
          <button
            onClick={handleBackfill}
            disabled={backfilling}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-50"
          >
            {backfilling ? 'Computing embeddings…' : 'Backfill embeddings'}
          </button>
          <button
            onClick={handleReparseRescore}
            disabled={reparseScoring}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-50"
          >
            {reparseScoring ? 'Triggering…' : 'Reparse & Rescore'}
          </button>
        </div>
        {triggerResult && (
          <p className={`mt-3 text-sm ${triggerResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {triggerResult.message}
          </p>
        )}
        {backfillResult && (
          <p className={`mt-3 text-sm ${backfillResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {backfillResult.message}
          </p>
        )}
        {reparseScoringResult && (
          <p className={`mt-3 text-sm ${reparseScoringResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {reparseScoringResult.message}
          </p>
        )}
      </section>

      {/* Domain Classification */}
      <section className="mb-10 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Domain Classification
        </h2>
        <p className="mb-4 text-sm text-zinc-500">
          Re-classify jobs where domain is &quot;other&quot; using expanded keyword rules.
          Does not touch parsed data or RAG scores.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={handleReparsePreview}
            disabled={reparsePreviewing || reparseRunning}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-50"
          >
            {reparsePreviewing ? 'Loading…' : 'Preview'}
          </button>
          <button
            onClick={handleReparse}
            disabled={reparseRunning || reparsePreviewing}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-50"
          >
            {reparseRunning ? 'Reclassifying…' : "Reparse 'other' domains"}
          </button>
        </div>
        {reparsePreviewResult && (
          <div className="mt-3 text-sm text-zinc-300">
            <p className="mb-1">
              <span className="text-zinc-400">{reparsePreviewResult.domain_other_count}</span> jobs with domain=&quot;other&quot;.
              {reparsePreviewResult.sample.length > 0
                ? ` ${reparsePreviewResult.sample.length} would be reclassified:`
                : ' None would be reclassified.'}
            </p>
            {reparsePreviewResult.sample.length > 0 && (
              <ul className="ml-4 list-disc space-y-0.5 text-zinc-400">
                {reparsePreviewResult.sample.map((s) => (
                  <li key={s.job_id}>
                    <span className="text-zinc-300">{s.title}</span>
                    {' '}at {s.company}{' '}
                    <span className="text-violet-400">→ {s.inferred}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {reparseResult && (
          <p className={`mt-3 text-sm ${reparseResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {reparseResult.message}
          </p>
        )}

        {/* Domain Corrections */}
        <div className="mt-6 border-t border-zinc-800 pt-5">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            User Domain Corrections
          </h3>
          {correctionsError ? (
            <p className="text-sm text-red-400">Failed to load corrections.</p>
          ) : corrections === null ? (
            <p className="text-sm text-zinc-500">Loading…</p>
          ) : corrections.length === 0 ? (
            <p className="text-sm text-zinc-500">No corrections recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                    <th className="pb-2 pr-6">From</th>
                    <th className="pb-2 pr-6">To</th>
                    <th className="pb-2">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {corrections.map((c, i) => (
                    <tr key={i} className="border-b border-zinc-800/50 last:border-0">
                      <td className="py-2 pr-6 font-mono text-zinc-400">{c.from}</td>
                      <td className="py-2 pr-6 font-mono text-violet-400">{c.to}</td>
                      <td className="py-2 text-zinc-300">{c.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* Waitlist */}
      <section className="mb-10 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Waitlist
          {waitlist !== null && (
            <span className="ml-2 rounded-full bg-violet-900/60 px-2 py-0.5 text-xs font-medium text-violet-300 normal-case">
              {waitlist.length}
            </span>
          )}
        </h2>
        {waitlistError ? (
          <p className="text-sm text-red-400">Failed to load waitlist.</p>
        ) : waitlist === null ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : waitlist.length === 0 ? (
          <p className="text-sm text-zinc-500">No entries yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                  <th className="pb-2 pr-6">Email</th>
                  <th className="pb-2 pr-6">Date</th>
                  <th className="pb-2">Time ago</th>
                </tr>
              </thead>
              <tbody>
                {waitlist.map((entry) => {
                  const date = new Date(entry.created_at + 'Z');
                  const diffMs = Math.max(0, Date.now() - date.getTime());
                  const diffDays = Math.floor(diffMs / 86400000);
                  const diffHours = Math.floor(diffMs / 3600000);
                  const diffMins = Math.floor(diffMs / 60000);
                  const timeAgo =
                    diffDays > 0
                      ? `${diffDays}d ago`
                      : diffHours > 0
                      ? `${diffHours}h ago`
                      : diffMins > 0
                      ? `${diffMins}m ago`
                      : 'just now';
                  return (
                    <tr key={entry.id} className="border-b border-zinc-800/50 last:border-0">
                      <td className="py-2 pr-6 text-zinc-200">{entry.email}</td>
                      <td className="py-2 pr-6 text-zinc-400">{date.toLocaleDateString()}</td>
                      <td className="py-2 text-zinc-500">{timeAgo}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Users table */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Users
        </h2>
        {usersLoading ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : usersError ? (
          <p className="text-sm text-red-400">Failed to load users.</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-zinc-500">No users found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                  <th className="pb-2 pr-4">Name</th>
                  <th className="pb-2 pr-4">Email</th>
                  <th className="pb-2 pr-4">Profile ID</th>
                  <th className="pb-2 pr-4">Data</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2 pr-4">Last login</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-800/50 last:border-0">
                    <td className="py-2.5 pr-4 text-zinc-200">{u.name}</td>
                    <td className="py-2.5 pr-4 text-zinc-400">{u.email}</td>

                    {/* Profile ID — inline editable */}
                    <td className="py-2.5 pr-4">
                      {editingProfileId?.userId === u.id ? (
                        <span className="flex items-center gap-1.5">
                          <input
                            autoFocus
                            value={editingProfileId.value}
                            onChange={(e) => setEditingProfileId({ userId: u.id, value: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveProfileId(u.id);
                              if (e.key === 'Escape') setEditingProfileId(null);
                            }}
                            className="w-24 rounded border border-zinc-600 bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-white focus:border-violet-500 focus:outline-none"
                          />
                          <button
                            onClick={() => handleSaveProfileId(u.id)}
                            disabled={savingProfileId}
                            className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-40"
                          >
                            {savingProfileId ? '…' : '✓'}
                          </button>
                          <button
                            onClick={() => setEditingProfileId(null)}
                            className="text-xs text-zinc-500 hover:text-zinc-300"
                          >
                            ✕
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => setEditingProfileId({ userId: u.id, value: u.profile_id ?? '' })}
                          className="group flex items-center gap-1 font-mono text-xs text-zinc-500 hover:text-zinc-300"
                          title="Click to edit profile ID"
                        >
                          {u.profile_id ?? '—'}
                          <span className="opacity-0 group-hover:opacity-60 text-zinc-500">✎</span>
                        </button>
                      )}
                    </td>

                    <td className="py-2.5 pr-4">
                      <span className={`mr-1 text-xs ${u.has_cv ? 'text-emerald-400' : 'text-red-500'}`} title="CV">
                        {u.has_cv ? '✓CV' : '✗CV'}
                      </span>
                      <span className={`text-xs ${u.has_yaml ? 'text-emerald-400' : 'text-red-500'}`} title="YAML">
                        {u.has_yaml ? '✓YAML' : '✗YAML'}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4">
                      {u.is_admin ? (
                        <span className="rounded-full bg-violet-900/60 px-2 py-0.5 text-xs font-medium text-violet-300">
                          admin
                        </span>
                      ) : (
                        <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-500">
                          user
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-xs text-zinc-500">
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        {/* View as — don't impersonate self */}
                        {u.id !== user?.id && (
                          <button
                            onClick={() => handleImpersonate(u.id)}
                            disabled={impersonating === u.id}
                            className="rounded px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-violet-400 disabled:opacity-40"
                            title="View the app as this user"
                          >
                            {impersonating === u.id ? '…' : 'View as'}
                          </button>
                        )}
                        <button
                          onClick={() => handleResetOnboarding(u.id, u.name)}
                          disabled={resetting === u.id}
                          className="rounded px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-amber-400 disabled:opacity-40"
                          title="Reset onboarding (clears profile + CV, keeps job history)"
                        >
                          {resetting === u.id ? '…' : 'Reset'}
                        </button>
                        {u.profile_id && (
                          <button
                            onClick={() => handleClearSeen(u.id, u.profile_id!)}
                            disabled={clearingSeen === u.id}
                            className="rounded px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-amber-400 disabled:opacity-40"
                            title="Clear seen job IDs (forces re-scrape on next run)"
                          >
                            {clearingSeen === u.id ? '…' : 'Clear seen'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
