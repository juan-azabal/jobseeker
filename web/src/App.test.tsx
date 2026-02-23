import { render, screen } from '@testing-library/react';
import App from './App';

test('renders JobSeeker heading', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /jobseeker/i })).toBeInTheDocument();
});
