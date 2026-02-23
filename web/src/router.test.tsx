import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import App from './App';

const MOCK_USER = { id: 1, email: 'u@e.com', name: 'User', avatar_url: null, profile_id: 'user' };
const MOCK_JOBS = { jobs: [], total: 0, filters: { tier: [], period: 'all' } };

beforeEach(() => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => MOCK_USER } as Response)
    .mockResolvedValue({ ok: true, json: async () => MOCK_JOBS } as Response);
});

afterEach(() => vi.restoreAllMocks());

test('/ redirects to /jobs', async () => {
  render(
    <MemoryRouter initialEntries={['/']}>
      <App />
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByRole('heading', { name: /jobs/i })).toBeInTheDocument());
});

test('/jobs renders jobs page', async () => {
  render(
    <MemoryRouter initialEntries={['/jobs']}>
      <App />
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByRole('heading', { name: /jobs/i })).toBeInTheDocument());
});
