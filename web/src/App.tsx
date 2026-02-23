import { Routes, Route, Navigate, useNavigate, useParams } from 'react-router';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';

function JobDetailRoute() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  return <JobDetailPage jobId={jobId!} onBack={() => navigate(-1)} />;
}

export default function App() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 px-4 py-3">
        <span className="text-lg font-bold text-white">JobSeeker</span>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/jobs" replace />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailRoute />} />
      </Routes>
    </div>
  );
}
