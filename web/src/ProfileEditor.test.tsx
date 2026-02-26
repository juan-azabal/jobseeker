import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import ProfileEditor from './components/ProfileEditor';

const MOCK_PROFILE = {
  name: 'Alice Martin',
  email: 'alice@example.com',
  languages: ['en', 'fr'],
  home_locations: ['paris', 'france'],
  current_level: 'senior',
  track: 'ic',
  target_level: 'principal',
  domains: { data: 15, ml: 10 },
  skills: ['python', 'sql'],
  exclude_companies: ['OldCorp'],
};

afterEach(() => vi.restoreAllMocks());

test('renders profile editor with extracted data', () => {
  render(
    <MemoryRouter>
      <ProfileEditor
        profile={MOCK_PROFILE}
        cvMarkdown="# Alice"
        onSaved={() => {}}
      />
    </MemoryRouter>
  );
  expect(screen.getByDisplayValue('Alice Martin')).toBeInTheDocument();
  expect(screen.getByText('python')).toBeInTheDocument();
  expect(screen.getByText('Data')).toBeInTheDocument();
});

test('calls save API and triggers onSaved', async () => {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: MOCK_PROFILE }) } as Response)
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile_id: 'alice' }) } as Response);

  const onSaved = vi.fn();
  render(
    <MemoryRouter>
      <ProfileEditor
        profile={MOCK_PROFILE}
        cvMarkdown="# Alice"
        onSaved={onSaved}
        isNew={true}
      />
    </MemoryRouter>
  );

  await userEvent.click(screen.getByRole('button', { name: /activate/i }));
  await waitFor(() => expect(onSaved).toHaveBeenCalled());
});

test('renders role_function dropdown and role_type input', () => {
  const profileWithRoles = {
    ...MOCK_PROFILE,
    role_type: 'Product Manager',
    role_function: 'product',
  };
  render(
    <MemoryRouter>
      <ProfileEditor
        profile={profileWithRoles}
        cvMarkdown="# Alice"
        onSaved={() => {}}
      />
    </MemoryRouter>
  );
  // role_type text input should exist
  expect(screen.getByDisplayValue('Product Manager')).toBeInTheDocument();
  // role_function dropdown should render (combobox)
  const dropdown = screen.getByRole('combobox', { name: /role function/i });
  expect(dropdown).toBeInTheDocument();
  expect((dropdown as HTMLSelectElement).value).toBe('product');
});

test('shows error when save fails', async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: false,
    json: async () => ({ detail: 'Save failed' }),
  } as Response);

  render(
    <MemoryRouter>
      <ProfileEditor
        profile={MOCK_PROFILE}
        cvMarkdown="# Alice"
        onSaved={() => {}}
        isNew={true}
      />
    </MemoryRouter>
  );

  await userEvent.click(screen.getByRole('button', { name: /activate/i }));
  await waitFor(() => expect(screen.getByText(/save failed/i)).toBeInTheDocument());
});
