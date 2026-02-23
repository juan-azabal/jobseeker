import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import OnboardPage from './pages/OnboardPage';

afterEach(() => vi.restoreAllMocks());

test('renders upload prompt', () => {
  render(<MemoryRouter><OnboardPage onComplete={() => {}} /></MemoryRouter>);
  expect(screen.getByRole('heading', { name: /set up your profile/i })).toBeInTheDocument();
});

test('shows error for non-docx file', async () => {
  render(<MemoryRouter><OnboardPage onComplete={() => {}} /></MemoryRouter>);
  const input = screen.getByTestId('cv-file-input');
  const file = new File(['content'], 'cv.pdf', { type: 'application/pdf' });
  await userEvent.upload(input, file, { applyAccept: false });
  expect(screen.getByText(/only .docx files/i)).toBeInTheDocument();
});

test('shows markdown preview after successful upload', async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ markdown: '# Alice Martin\n\nSenior PM' }),
  } as Response);

  render(<MemoryRouter><OnboardPage onComplete={() => {}} /></MemoryRouter>);
  const input = screen.getByTestId('cv-file-input');
  const file = new File(['PK\x03\x04'], 'cv.docx', {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
  await userEvent.upload(input, file);

  await waitFor(() =>
    expect(screen.getByText(/alice martin/i)).toBeInTheDocument()
  );
  expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
});

test('shows error when upload fails', async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: false,
    json: async () => ({ detail: 'Server error' }),
  } as Response);

  render(<MemoryRouter><OnboardPage onComplete={() => {}} /></MemoryRouter>);
  const input = screen.getByTestId('cv-file-input');
  const file = new File(['PK'], 'cv.docx', {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
  await userEvent.upload(input, file);

  await waitFor(() =>
    expect(screen.getByText(/server error/i)).toBeInTheDocument()
  );
});
