import { render, screen } from '@testing-library/react';
import MockJobDetail from './MockJobDetail';

test('renders job title', () => {
  render(<MockJobDetail />);
  expect(screen.getByText('Head of Product')).toBeInTheDocument();
});

test('renders score', () => {
  render(<MockJobDetail />);
  expect(screen.getByText('91')).toBeInTheDocument();
});

test('renders all 5 breakdown labels', () => {
  render(<MockJobDetail />);
  expect(screen.getByText('Domain Fit')).toBeInTheDocument();
  expect(screen.getByText('Seniority Fit')).toBeInTheDocument();
  expect(screen.getByText('Technical Depth')).toBeInTheDocument();
  expect(screen.getByText('Profile Evidence')).toBeInTheDocument();
  expect(screen.getByText('Strategic Impact')).toBeInTheDocument();
});

test('renders skill chips', () => {
  render(<MockJobDetail />);
  expect(screen.getByText('Product Strategy')).toBeInTheDocument();
  expect(screen.getByText('Enterprise Sales Cycles')).toBeInTheDocument();
});

test('renders strength claim', () => {
  render(<MockJobDetail />);
  expect(screen.getByText('Deep B2B platform experience')).toBeInTheDocument();
});

test('renders verdict text', () => {
  render(<MockJobDetail />);
  expect(screen.getByText(/Strong product leader/)).toBeInTheDocument();
});
