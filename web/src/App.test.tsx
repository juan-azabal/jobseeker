import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import App from './App';

const MOCK_USER = { id: 1, email: 'u@e.com', name: 'User', avatar_url: null, profile_id: 'user', onboarded: true };
const MOCK_JOBS = { jobs: [], total: 0, filters: { tier: [], period: 'all' } };

afterEach(() => vi.restoreAllMocks());

test('renders JobSeeker header when authenticated', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => MOCK_USER } as Response)
    .mockResolvedValue({ ok: true, json: async () => MOCK_JOBS } as Response);
  render(<MemoryRouter><App /></MemoryRouter>);
  await waitFor(() => expect(screen.getByText('JobSeeker')).toBeInTheDocument());
});

test('/ redirects to /jobs page when authenticated', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => MOCK_USER } as Response)
    .mockResolvedValue({ ok: true, json: async () => MOCK_JOBS } as Response);
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('heading', { name: /^jobs$/i })).toBeInTheDocument());
});
