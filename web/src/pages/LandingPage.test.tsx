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
  expect(screen.getAllByText('Head of Product').length).toBeGreaterThanOrEqual(1);
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

test('renders MockDashboard section heading', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('Every job, scored and ranked')).toBeInTheDocument();
});

test('renders MockJobDetail section heading', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText(/See exactly why each job fits/)).toBeInTheDocument();
});

test('renders CV callout title', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('A CV that speaks to the job description')).toBeInTheDocument();
});

test('renders How it works step 3 and step 4', () => {
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  expect(screen.getByText('Understand the match')).toBeInTheDocument();
  expect(screen.getByText('Apply with a tailored CV')).toBeInTheDocument();
});
