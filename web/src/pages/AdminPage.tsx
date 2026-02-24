import { useEffect, useState } from 'react';
import { Navigate } from 'react-router';
import { useAuth } from '../context/AuthContext';

interface AdminUser {
  id: number;
  email: string;
  name: string;
  profile_id: string | null;
  is_admin: number;
  created_at: string;
  last_login: string;
}

export default function AdminPage() {
  const { user, isLoading } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState(false);
  const [profile, setProfile] = useState('');
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Fetch users — must be before early returns to satisfy Rules of Hooks
  useEffect(() => {
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

  if (isLoading) return <div className="min-h-screen bg-zinc-950" />;

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="mb-8 text-xl font-bold text-white">Admin</h1>

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
        </div>
        {triggerResult && (
          <p className={`mt-3 text-sm ${triggerResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {triggerResult.message}
          </p>
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
                  <th className="pb-2 pr-4">Profile</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2">Last login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-800/50 last:border-0">
                    <td className="py-2.5 pr-4 text-zinc-200">{u.name}</td>
                    <td className="py-2.5 pr-4 text-zinc-400">{u.email}</td>
                    <td className="py-2.5 pr-4 font-mono text-xs text-zinc-500">
                      {u.profile_id ?? '—'}
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
                    <td className="py-2.5 text-xs text-zinc-500">
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
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
