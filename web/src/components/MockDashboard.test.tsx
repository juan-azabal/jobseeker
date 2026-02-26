import { render, screen } from '@testing-library/react';
import MockDashboard from './MockDashboard';

test('renders all 4 job card titles', () => {
  render(<MockDashboard />);
  expect(screen.getByText('Head of Product')).toBeInTheDocument();
  expect(screen.getByText('Product Lead, Payments')).toBeInTheDocument();
  expect(screen.getByText('Senior PM, Marketplace')).toBeInTheDocument();
  expect(screen.getByText('Group PM, Infrastructure')).toBeInTheDocument();
});

test('renders tier badges Apply, Review, Skip', () => {
  render(<MockDashboard />);
  // Two Tier A cards → two "Apply" badges
  expect(screen.getAllByText('Apply').length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText('Review')).toBeInTheDocument();
  expect(screen.getByText('Skip')).toBeInTheDocument();
});

test('renders scores 91, 82, 68, 41', () => {
  render(<MockDashboard />);
  expect(screen.getByText('91')).toBeInTheDocument();
  expect(screen.getByText('82')).toBeInTheDocument();
  expect(screen.getByText('68')).toBeInTheDocument();
  expect(screen.getByText('41')).toBeInTheDocument();
});
