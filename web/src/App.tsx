import { useState, useRef, useEffect } from 'react';
import { Routes, Route, Navigate, Link, useNavigate, useParams, useLocation } from 'react-router';
import { AuthProvider, useAuth } from './context/AuthContext';

import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import LandingPage from './pages/LandingPage';
import OnboardPage from './pages/OnboardPage';
import ProfilePage from './pages/ProfilePage';
import AdminPage from './pages/AdminPage';

function JobDetailRoute() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const jobIds: string[] = (location.state as { jobIds?: string[] } | null)?.jobIds ?? [];

  const idx = jobIds.indexOf(jobId!);
  const prevId = idx > 0 ? jobIds[idx - 1] : undefined;
  const nextId = idx >= 0 && idx < jobIds.length - 1 ? jobIds[idx + 1] : undefined;

  return (
    <JobDetailPage
      jobId={jobId!}
      onBack={() => navigate(-1)}
      prevId={prevId}
      nextId={nextId}
      onNavigate={(id) => navigate(`/jobs/${id}`, { state: { jobIds }, replace: true })}
    />
  );
}

function HamburgerMenu() {
  const { user, logout } = useAuth();
  const isAdmin = !!user?.is_admin;
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative flex items-center gap-3">
      <span className="hidden text-sm text-zinc-400 sm:block">{user?.name}</span>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-8 w-8 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
        aria-label="Menu"
      >
        {open ? (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 min-w-44 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 py-1 shadow-xl">
          <Link
            to="/jobs"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="8" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="1" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="8" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            Jobs
          </Link>
          <Link
            to="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="4.5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
              <path d="M1.5 12.5c0-2.485 2.462-4.5 5.5-4.5s5.5 2.015 5.5 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
            My Profile
          </Link>
          {isAdmin && (
            <Link
              to="/admin"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1.5a2 2 0 100 4 2 2 0 000-4zM3 10.5c0-2.21 1.79-4 4-4s4 1.79 4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                <path d="M10.5 8.5l1 1 2-2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Admin
            </Link>
          )}
          <div className="mx-3 my-1 h-px bg-zinc-800" />
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M5 2H2.5A1.5 1.5 0 001 3.5v7A1.5 1.5 0 002.5 12H5M9 10l3-3-3-3M12 7H5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function StagingBanner() {
  if (import.meta.env.VITE_ENVIRONMENT !== 'staging') return null;
  return (
    <div className="flex items-center justify-center gap-2 border-b border-amber-500/30 bg-amber-500/15 px-4 py-2">
      <span className="text-xs font-medium text-amber-400">⚠ Staging environment — data from production</span>
    </div>
  );
}

function ImpersonationBanner() {
  const { user, stopImpersonating } = useAuth();
  const navigate = useNavigate();

  if (!user?.is_impersonating) return null;

  const handleStop = async () => {
    await stopImpersonating();
    navigate('/admin');
  };

  return (
    <div className="flex items-center justify-center gap-3 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2">
      <span className="text-xs text-amber-400">
        Viewing as <span className="font-semibold">{user.name}</span>
        {user.real_user_name && (
          <span className="text-amber-500/60"> · logged in as {user.real_user_name}</span>
        )}
      </span>
      <button
        onClick={handleStop}
        className="rounded bg-amber-500/20 px-2.5 py-0.5 text-xs font-medium text-amber-300 transition-colors hover:bg-amber-500/30"
      >
        Stop
      </button>
    </div>
  );
}

function AppRoutes() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) return <div className="min-h-screen bg-zinc-950" />;
  if (!isAuthenticated) return <LandingPage />;

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-zinc-800/60 bg-zinc-950/90 px-6 py-3 backdrop-blur-sm">
        <Link to="/jobs" className="flex items-center gap-2 transition-opacity hover:opacity-70">
          <span className="h-2 w-2 rounded-full bg-violet-500" />
          <span className="text-sm font-bold tracking-tight text-white">JobSeeker</span>
        </Link>
        <HamburgerMenu />
      </header>
      <StagingBanner />
      <ImpersonationBanner />
      <Routes>
        <Route path="/onboard" element={<OnboardPage onComplete={() => window.location.replace('/jobs?welcome=1')} />} />
        <Route path="/" element={<Navigate to={user?.onboarded ? '/jobs' : '/onboard'} replace />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailRoute />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
