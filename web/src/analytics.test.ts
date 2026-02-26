/**
 * Tests for Phase 14.5 — frontend PostHog analytics module.
 *
 * VERIFY-DOCS findings (posthog-js v1.354.3):
 *   posthog.init(token, config)
 *   posthog.identify(distinct_id, properties)
 *   posthog.reset()
 *   config.capture_pageview = 'history_change'  (SPA mode)
 *   config.disable_session_recording = false     (enable recording)
 *   config.session_recording.recordCrossOriginIframes = false
 */
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock posthog-js — must be declared before module imports (Vitest hoists vi.mock calls)
vi.mock('posthog-js', () => ({
  default: {
    init: vi.fn(),
    identify: vi.fn(),
    reset: vi.fn(),
  },
}));

import posthog from 'posthog-js';
import { initPostHog, identifyUser, resetPostHog } from './analytics';

describe('analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset module-level _initialized flag between tests
    // by re-importing after clearing; in practice the flag stays false
    // in test env because VITE_POSTHOG_KEY is never set.
  });

  it('initPostHog is a no-op when VITE_POSTHOG_KEY is not set', () => {
    // In the test environment, import.meta.env.VITE_POSTHOG_KEY is undefined
    initPostHog();
    expect(posthog.init).not.toHaveBeenCalled();
  });

  it('identifyUser is a no-op when posthog is not initialized', () => {
    // Since initPostHog never ran (no key), identify must not be forwarded
    expect(() => identifyUser(42, 'u@t.com', 'Test User')).not.toThrow();
    expect(posthog.identify).not.toHaveBeenCalled();
  });

  it('resetPostHog is a no-op when posthog is not initialized', () => {
    expect(() => resetPostHog()).not.toThrow();
    expect(posthog.reset).not.toHaveBeenCalled();
  });
});
