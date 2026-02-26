import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import './index.css';
import App from './App.tsx';
import { initPostHog } from './analytics';

// Initialise PostHog before the first render so the initial pageview is captured.
// No-op when VITE_POSTHOG_KEY is absent (dev / test).
initPostHog();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
