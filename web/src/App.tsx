import { Routes, Route, Navigate, Link, useNavigate, useParams } from 'react-router';
import { AuthProvider, useAuth } from './context/AuthContext';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import LoginPage from './pages/LoginPage';
import OnboardPage from './pages/OnboardPage';
import ProfilePage from './pages/ProfilePage';
import UserMenu from './components/UserMenu';

function JobDetailRoute() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  return <JobDetailPage jobId={jobId!} onBack={() => navigate(-1)} />;
}

function AppRoutes() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) return <div className="min-h-screen bg-zinc-950" />;
  if (!isAuthenticated) return <LoginPage />;

  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-zinc-800/60 bg-zinc-950/90 px-6 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-violet-500" />
          <span className="text-sm font-bold tracking-tight text-white">JobSeeker</span>
        </div>
        <div className="flex items-center gap-5">
          <Link
            to="/profile"
            className="text-xs font-medium text-zinc-400 transition-colors hover:text-zinc-200"
          >
            My CV
          </Link>
          <UserMenu />
        </div>
      </header>
      <Routes>
        <Route path="/onboard" element={<OnboardPage onComplete={() => window.location.replace('/jobs')} />} />
        <Route path="/" element={<Navigate to={user?.profile_id ? '/jobs' : '/onboard'} replace />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailRoute />} />
        <Route path="/profile" element={<ProfilePage />} />
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
