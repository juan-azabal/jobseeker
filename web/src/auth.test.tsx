import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import App from './App';

afterEach(() => vi.restoreAllMocks());

test('shows login page when unauthenticated', async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: 'Not authenticated' }),
  } as Response);

  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  await waitFor(() =>
    expect(screen.getByRole('link', { name: /sign in with google/i })).toBeInTheDocument()
  );
});

test('shows jobs page when authenticated', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, email: 'u@e.com', name: 'User', avatar_url: null, profile_id: 'user' }),
    } as Response)
    .mockResolvedValue({
      ok: true,
      json: async () => ({ jobs: [], total: 0, filters: { tier: [], period: 'all' } }),
    } as Response);

  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  await waitFor(() =>
    expect(screen.getByRole('heading', { name: /^jobs$/i })).toBeInTheDocument()
  );
});

test('shows user name in header when authenticated', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, email: 'u@e.com', name: 'Alice', avatar_url: null, profile_id: 'alice' }),
    } as Response)
    .mockResolvedValue({
      ok: true,
      json: async () => ({ jobs: [], total: 0, filters: { tier: [], period: 'all' } }),
    } as Response);

  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument());
});
