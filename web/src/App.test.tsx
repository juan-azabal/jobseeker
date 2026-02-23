import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import App from './App';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ jobs: [], total: 0, filters: { tier: [], period: 'all' } }),
  } as Response);
});

afterEach(() => vi.restoreAllMocks());

test('renders JobSeeker header', async () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(screen.getByText('JobSeeker')).toBeInTheDocument();
});

test('/ redirects to /jobs page', async () => {
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
  await waitFor(() => expect(screen.getByRole('heading', { name: /^jobs$/i })).toBeInTheDocument());
});
