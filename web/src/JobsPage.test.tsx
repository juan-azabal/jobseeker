import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import JobsPage from './pages/JobsPage';

const MOCK_JOBS = [
  { job_id: 'a1', title: 'Senior PM', company: 'Acme', location: 'Paris', score: 72, tier: 'A', first_seen: '2026-02-23', url: 'https://ex.com/1', location_type: 'hybrid', domain: 'data' },
  { job_id: 'b1', title: 'ML PM', company: 'Beta', location: 'Remote', score: 35, tier: 'B', first_seen: '2026-02-20', url: 'https://ex.com/2', location_type: 'remote', domain: 'ml' },
  { job_id: 'c1', title: 'Growth PM', company: 'Gamma', location: 'Amsterdam', score: 20, tier: 'C', first_seen: '2026-02-01', url: 'https://ex.com/3', location_type: 'onsite', domain: 'growth' },
];

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ jobs: MOCK_JOBS, total: 3, filters: { tier: [], period: 'all' } }),
  } as Response);
});

afterEach(() => vi.restoreAllMocks());

test('renders job cards for all tiers', async () => {
  render(<MemoryRouter><JobsPage /></MemoryRouter>);
  await waitFor(() => expect(screen.getByText('Senior PM')).toBeInTheDocument());
  expect(screen.getByText('ML PM')).toBeInTheDocument();
  expect(screen.getByText('Growth PM')).toBeInTheDocument();
});

test('shows tier badges', async () => {
  render(<MemoryRouter><JobsPage /></MemoryRouter>);
  await waitFor(() => screen.getByText('Senior PM'));
  expect(screen.getAllByText('A').length).toBeGreaterThan(0);
  expect(screen.getAllByText('B').length).toBeGreaterThan(0);
  expect(screen.getAllByText('C').length).toBeGreaterThan(0);
});

test('shows company names', async () => {
  render(<MemoryRouter><JobsPage /></MemoryRouter>);
  await waitFor(() => expect(screen.getByText(/Acme/)).toBeInTheDocument());
  expect(screen.getByText(/Beta/)).toBeInTheDocument();
});
