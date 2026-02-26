import { render, screen } from '@testing-library/react';
import MockCVButton from './MockCVButton';

test('renders Generate CV text', () => {
  render(<MockCVButton />);
  expect(screen.getByText('Generate CV')).toBeInTheDocument();
});

test('renders Generating CV text', () => {
  render(<MockCVButton />);
  expect(screen.getByText('Generating CV...')).toBeInTheDocument();
});

test('renders CV downloaded text', () => {
  render(<MockCVButton />);
  expect(screen.getByText('CV downloaded')).toBeInTheDocument();
});
