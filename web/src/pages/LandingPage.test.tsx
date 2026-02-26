import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import LandingPage from './LandingPage';

vi.mock('posthog-js', () => ({
  default: { capture: vi.fn() },
}));

afterEach(() => vi.restoreAllMocks());

test('renders hero headline', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('Know your fit before you apply')).toBeInTheDocument();
});

test('renders two WaitlistForm instances (hero + bottom)', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getAllByRole('button', { name: /get early access/i }).length).toBe(2);
});

test('renders MockDashboard with job cards', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('Head of Product')).toBeInTheDocument();
});

test('renders footer with Built by Juan Azabal', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('Built by Juan Azabal')).toBeInTheDocument();
});

test('renders Sign in link pointing to /api/auth/login', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  const link = screen.getByRole('link', { name: /sign in/i });
  expect(link).toHaveAttribute('href', '/api/auth/login');
});
