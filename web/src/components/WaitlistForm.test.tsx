import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import WaitlistForm from './WaitlistForm';

vi.mock('posthog-js', () => ({
  default: { capture: vi.fn() },
}));

import posthog from 'posthog-js';

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test('renders email input and submit button', () => {
  render(<WaitlistForm source="hero" />);
  expect(screen.getByRole('textbox')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /get early access/i })).toBeInTheDocument();
});

test('submits with valid email and calls fetch with POST /api/waitlist', async () => {
  global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ status: 'ok' }) } as Response);
  render(<WaitlistForm source="hero" />);
  await userEvent.type(screen.getByRole('textbox'), 'user@example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  expect(global.fetch).toHaveBeenCalledWith('/api/waitlist', expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ email: 'user@example.com' }),
  }));
});

test('on 201 shows success message', async () => {
  global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ status: 'ok' }) } as Response);
  render(<WaitlistForm source="hero" />);
  await userEvent.type(screen.getByRole('textbox'), 'user@example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  await waitFor(() => expect(screen.getByText(/you're on the list/i)).toBeInTheDocument());
});

test('on 409 shows "Already on the list"', async () => {
  global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail: 'already_registered' }) } as Response);
  render(<WaitlistForm source="bottom" />);
  await userEvent.type(screen.getByRole('textbox'), 'dup@example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  await waitFor(() => expect(screen.getByText(/already on the list/i)).toBeInTheDocument());
});

test('on empty input shows validation error and does NOT call fetch', async () => {
  global.fetch = vi.fn();
  render(<WaitlistForm source="hero" />);
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('email with subdomain (user@sub.example.com) passes validation', async () => {
  global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ status: 'ok' }) } as Response);
  render(<WaitlistForm source="hero" />);
  await userEvent.type(screen.getByRole('textbox'), 'user@sub.example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  expect(global.fetch).toHaveBeenCalled();
  expect(screen.queryByText(/enter a valid email/i)).not.toBeInTheDocument();
});

test('fetch abort (timeout) shows generic error', async () => {
  global.fetch = vi.fn().mockRejectedValueOnce(
    Object.assign(new Error('Aborted'), { name: 'AbortError' }),
  );
  render(<WaitlistForm source="hero" />);
  await userEvent.type(screen.getByRole('textbox'), 'user@example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  await waitFor(() => expect(screen.getByText(/something went wrong/i)).toBeInTheDocument());
});

test('source prop is passed to posthog.capture on submit', async () => {
  global.fetch = vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ status: 'ok' }) } as Response);
  render(<WaitlistForm source="bottom" />);
  await userEvent.type(screen.getByRole('textbox'), 'user@example.com');
  await userEvent.click(screen.getByRole('button', { name: /get early access/i }));
  expect(posthog.capture).toHaveBeenCalledWith('waitlist_submitted', { source: 'bottom' });
});
