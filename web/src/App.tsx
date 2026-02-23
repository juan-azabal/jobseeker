import { Routes, Route, Navigate, useNavigate, useParams } from 'react-router';
import { AuthProvider, useAuth } from './context/AuthContext';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import LoginPage from './pages/LoginPage';
import OnboardPage from './pages/OnboardPage';
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
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <span className="text-lg font-bold text-white">JobSeeker</span>
        <UserMenu />
      </header>
      <Routes>
        <Route path="/onboard" element={<OnboardPage onComplete={() => window.location.replace('/jobs')} />} />
        <Route path="/" element={<Navigate to={user?.profile_id ? '/jobs' : '/onboard'} replace />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailRoute />} />
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
