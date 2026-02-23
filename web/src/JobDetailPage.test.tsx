import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import JobDetailPage from './pages/JobDetailPage';

const MOCK_JOB = {
  job_id: 'a1',
  title: 'Senior PM',
  company: 'Acme',
  location: 'Paris',
  score: 72,
  tier: 'A',
  first_seen: '2026-02-23',
  last_seen: '2026-02-23',
  ingested_at: '2026-02-23T10:00:00',
  url: 'https://ex.com/1',
  location_type: 'hybrid',
  domain: 'data',
  parsed: { domain: 'data', must_have_skills: ['SQL', 'Python'] },
  scored: {
    score: 72,
    score_breakdown: {
      domain_fit: 20,
      seniority_fit: 15,
      technical_depth: 18,
      profile_evidence: 15,
      strategic_impact: 4,
    },
    strengths: [{ claim: 'Strong data background', evidence: '5 years' }],
    gaps: [{ gap: 'Rust', severity: 'low', mitigation: 'nice to have' }],
  },
};

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => MOCK_JOB,
  } as Response);
});

afterEach(() => vi.restoreAllMocks());

test('renders job title and company', async () => {
  render(<JobDetailPage jobId="a1" />);
  await waitFor(() => expect(screen.getByText('Senior PM')).toBeInTheDocument());
  expect(screen.getByText(/Acme/)).toBeInTheDocument();
});

test('renders score', async () => {
  render(<JobDetailPage jobId="a1" />);
  await waitFor(() => screen.getByText('Senior PM'));
  expect(screen.getByText('72')).toBeInTheDocument();
});

test('renders score breakdown with 5 dimensions', async () => {
  render(<JobDetailPage jobId="a1" />);
  await waitFor(() => screen.getByText('Senior PM'));
  expect(screen.getByText(/domain fit/i)).toBeInTheDocument();
  expect(screen.getByText(/seniority/i)).toBeInTheDocument();
  expect(screen.getByText(/technical/i)).toBeInTheDocument();
  expect(screen.getByText(/profile/i)).toBeInTheDocument();
  expect(screen.getByText(/strategic/i)).toBeInTheDocument();
});

test('renders strengths and gaps', async () => {
  render(<JobDetailPage jobId="a1" />);
  await waitFor(() => screen.getByText('Senior PM'));
  expect(screen.getByText(/strong data background/i)).toBeInTheDocument();
  expect(screen.getByText(/Rust/)).toBeInTheDocument();
});

test('renders view posting link', async () => {
  render(<JobDetailPage jobId="a1" />);
  await waitFor(() => screen.getByText('Senior PM'));
  const link = screen.getByRole('link', { name: /view posting/i });
  expect(link).toHaveAttribute('href', 'https://ex.com/1');
});
