import { useState } from 'react';
import posthog from 'posthog-js';

interface Props {
  source: 'hero' | 'bottom';
}

type State = 'idle' | 'submitting' | 'success' | 'error';

const _EMAIL_RE = /^[^@]+@[^@]+\.[^@]+$/;

export default function WaitlistForm({ source }: Props) {
  const [email, setEmail] = useState('');
  const [state, setState] = useState<State>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || !_EMAIL_RE.test(trimmed)) {
      setErrorMsg('Enter a valid email');
      setState('error');
      return;
    }
    setState('submitting');
    setErrorMsg('');
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.status === 201) {
        posthog.capture('waitlist_success', { source });
        setState('success');
      } else if (res.status === 409) {
        posthog.capture('waitlist_duplicate', { source });
        setErrorMsg('Already on the list');
        setState('error');
      } else if (res.status === 422) {
        posthog.capture('waitlist_error', { source, reason: 'invalid_email' });
        setErrorMsg('Enter a valid email');
        setState('error');
      } else {
        posthog.capture('waitlist_error', { source, reason: 'server_error' });
        setErrorMsg('Something went wrong. Try again.');
        setState('error');
      }
    } catch {
      clearTimeout(timeoutId);
      setErrorMsg('Something went wrong. Try again.');
      setState('error');
    }
  };

  if (state === 'success') {
    return (
      <div className="flex items-center justify-center rounded-lg bg-violet-500/10 px-6 py-4 text-sm font-medium text-violet-300 border border-violet-500/30 transition-all duration-300">
        You're on the list ✓
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row sm:gap-3">
      <div className="flex flex-col gap-1.5 flex-1">
        <label
          htmlFor="waitlist-email"
          className="absolute w-px h-px p-0 -m-px overflow-hidden whitespace-nowrap border-0"
          style={{ clip: 'rect(0,0,0,0)' }}
        >
          Email address
        </label>
        <input
          id="waitlist-email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (state === 'error') { setState('idle'); setErrorMsg(''); }
          }}
          placeholder="you@example.com"
          disabled={state === 'submitting'}
          className={`w-full rounded-lg border bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 outline-none transition-all duration-150
            ${state === 'error'
              ? 'border-red-500 ring-1 ring-red-500/50 focus:ring-red-500'
              : 'border-zinc-700 focus:border-violet-500 focus:ring-1 focus:ring-violet-500/50'
            }
            disabled:opacity-50`}
        />
        {errorMsg && (
          <p role="alert" className="text-xs text-red-400">{errorMsg}</p>
        )}
      </div>
      <button
        type="submit"
        disabled={state === 'submitting'}
        className="flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-violet-500 px-6 py-3 text-sm font-bold text-white transition-all duration-150 hover:bg-violet-600 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {state === 'submitting' ? (
          <>
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Sending…
          </>
        ) : (
          'Get early access'
        )}
      </button>
    </form>
  );
}
