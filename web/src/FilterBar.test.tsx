import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import FilterBar from './components/FilterBar';

const DEFAULT_FILTERS = { tiers: ['A', 'B', 'C'], period: 'all' };

test('renders period and tier buttons', () => {
  render(<FilterBar filters={DEFAULT_FILTERS} onChange={vi.fn()} />);
  expect(screen.getByRole('button', { name: /today/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /this week/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /this month/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /all/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^A$/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^B$/ })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^C$/ })).toBeInTheDocument();
});

test('calls onChange when period button clicked', async () => {
  const onChange = vi.fn();
  render(<FilterBar filters={DEFAULT_FILTERS} onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: /this week/i }));
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ period: 'week' }));
});

test('calls onChange when tier toggled off', async () => {
  const onChange = vi.fn();
  render(<FilterBar filters={DEFAULT_FILTERS} onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: /^A$/ }));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ tiers: expect.not.arrayContaining(['A']) })
  );
});

test('active period button is visually distinct', () => {
  render(<FilterBar filters={{ ...DEFAULT_FILTERS, period: 'week' }} onChange={vi.fn()} />);
  const weekBtn = screen.getByRole('button', { name: /this week/i });
  expect(weekBtn.className).toMatch(/bg-/);
});
