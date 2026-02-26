/**
 * Frontend PostHog analytics module.
 *
 * Initialises posthog-js from VITE_POSTHOG_KEY + VITE_POSTHOG_HOST.
 * All exported functions are no-ops when the key is absent (dev / test).
 *
 * Usage:
 *   main.tsx   → initPostHog()
 *   AuthContext → identifyUser(id, email, name) on user load
 *               → resetPostHog() on logout
 */
import posthog from 'posthog-js';

/** True once posthog.init() has been called successfully. */
let _initialized = false;

/**
 * Initialise PostHog. No-op when VITE_POSTHOG_KEY is absent.
 * Call once at application start, before the first render.
 */
export function initPostHog(): void {
  const key = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
  if (!key) return;

  const host =
    (import.meta.env.VITE_POSTHOG_HOST as string | undefined) ??
    'https://us.i.posthog.com';

  posthog.init(key, {
    api_host: host,
    // Track route changes in the React SPA (not just the initial page load)
    capture_pageview: 'history_change',
    // Session recording ON — no cross-origin iframes
    disable_session_recording: false,
    session_recording: {
      recordCrossOriginIframes: false,
    },
  });

  _initialized = true;
}

/**
 * Associate the current anonymous session with an authenticated user.
 * No-op when PostHog was not initialised.
 */
export function identifyUser(
  userId: number | string,
  email: string,
  name: string,
): void {
  if (!_initialized) return;
  posthog.identify(String(userId), { email, name });
}

/**
 * Reset the PostHog session (call on logout so the next visitor
 * gets a fresh anonymous identity).
 * No-op when PostHog was not initialised.
 */
export function resetPostHog(): void {
  if (!_initialized) return;
  posthog.reset();
}
