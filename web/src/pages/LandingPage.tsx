import { useEffect, useRef } from 'react';
import WaitlistForm from '../components/WaitlistForm';
import MockDashboard from '../components/MockDashboard';
import MockJobDetail from '../components/MockJobDetail';
import MockCVButton from '../components/MockCVButton';

// ---- Scroll reveal hook ----
function useScrollReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      el.classList.add('revealed');
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add('revealed'); observer.disconnect(); } },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
}

// ---- Section wrapper ----
function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useScrollReveal();
  return (
    <div ref={ref} className={`reveal-section ${className}`}>
      {children}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* ---- Hero ---- */}
      <section className="relative flex flex-col items-center justify-center px-6 py-24 text-center md:py-40">
        {/* Violet glow */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(139,92,246,0.08) 0%, transparent 70%)' }}
          aria-hidden="true"
        />
        <RevealSection className="relative z-10 flex flex-col items-center gap-6 max-w-2xl mx-auto">
          {/* Beta badge */}
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium text-violet-300">
            Now in private beta
          </span>
          {/* Product name */}
          <p className="flex items-center gap-2 text-sm font-semibold text-zinc-400 uppercase tracking-widest">
            <span className="inline-block h-2 w-2 rounded-full bg-violet-500" />
            JobSeeker
          </p>
          {/* Headline */}
          <h1
            className="text-4xl font-normal leading-[1.1] text-zinc-100 md:text-6xl"
            style={{ fontFamily: "'Instrument Serif', serif" }}
          >
            Know your fit before you apply
          </h1>
          {/* Subheadline */}
          <p className="max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg">
            Every job scored 0–100 against your CV. Stop guessing which roles are worth your time.
          </p>
          {/* CTA */}
          <div className="w-full max-w-md">
            <WaitlistForm source="hero" />
          </div>
          {/* Sign in link */}
          <a
            href="/api/auth/login"
            className="text-sm text-zinc-500 underline-offset-4 hover:text-zinc-300 hover:underline transition-colors"
          >
            Already have access? Sign in
          </a>
        </RevealSection>
      </section>

      {/* ---- MockDashboard section ---- */}
      <section className="px-6 pb-24 md:pb-40">
        <RevealSection className="mx-auto max-w-[900px]">
          <div className="mb-10 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-violet-400">Your daily feed</p>
            <h2
              className="text-3xl font-normal text-zinc-100 md:text-4xl"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              Every job, scored and ranked
            </h2>
          </div>
          <MockDashboard />
        </RevealSection>
      </section>

      {/* ---- MockJobDetail section ---- */}
      <section className="px-6 pb-24 md:pb-40">
        <RevealSection className="mx-auto max-w-[900px]">
          <div className="mb-10 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-violet-400">Behind the score</p>
            <h2
              className="text-3xl font-normal text-zinc-100 md:text-4xl"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              See exactly why each job fits — or doesn't
            </h2>
          </div>
          <MockJobDetail />
        </RevealSection>
      </section>

      {/* ---- CV callout ---- */}
      <div className="px-6" style={{ marginTop: '80px', marginBottom: '80px' }}>
        <RevealSection className="mx-auto max-w-3xl">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 md:p-10">
            <div className="flex flex-col gap-8 md:flex-row md:items-center md:gap-10">
              <div className="flex-1">
                <h3
                  className="mb-3 text-2xl font-normal text-zinc-100 md:text-3xl"
                  style={{ fontFamily: "'Instrument Serif', serif" }}
                >
                  A CV that speaks to the job description
                </h3>
                <p className="text-sm leading-relaxed text-zinc-400 md:text-base">
                  For each job, generate a CV that highlights the experience that matters for that role. Strengths emphasized, gaps addressed, jargon matched. ATS-ready, one click.
                </p>
              </div>
              <div className="flex shrink-0 items-center justify-center md:justify-end">
                <MockCVButton />
              </div>
            </div>
          </div>
        </RevealSection>
      </div>

      {/* ---- How it works ---- */}
      <section className="px-6 py-24 md:py-40">
        <RevealSection className="mx-auto max-w-4xl">
          <h2
            className="mb-16 text-center text-3xl font-normal text-zinc-100 md:text-4xl"
            style={{ fontFamily: "'Instrument Serif', serif" }}
          >
            How it works
          </h2>
          <div className="grid gap-10 md:grid-cols-4">
            {[
              {
                num: '01',
                title: 'Upload your CV',
                body: 'Your profile, skills, and preferences are extracted automatically. No forms to fill.',
              },
              {
                num: '02',
                title: 'Get scored matches',
                body: 'New jobs scraped daily, scored against your exact background. Tier A means apply, Tier C means skip.',
              },
              {
                num: '03',
                title: 'Understand the match',
                body: 'For each job, see your score breakdown by dimension, skill-by-skill matching, strengths to leverage, and gaps to address.',
              },
              {
                num: '04',
                title: 'Apply with a tailored CV',
                body: 'Generate a CV customized to each role in one click. Your best experience highlighted, ATS-optimized, ready to send.',
              },
            ].map(({ num, title, body }) => (
              <div key={num} className="flex flex-col gap-4">
                <span
                  className="text-5xl font-normal text-violet-500 leading-none"
                  style={{ fontFamily: "'Instrument Serif', serif" }}
                >
                  {num}
                </span>
                <h3
                  className="text-xl font-normal text-zinc-100"
                  style={{ fontFamily: "'Instrument Serif', serif" }}
                >
                  {title}
                </h3>
                <p className="text-base leading-relaxed text-zinc-400">{body}</p>
              </div>
            ))}
          </div>
        </RevealSection>
      </section>

      {/* ---- Bottom CTA ---- */}
      <section className="relative px-6 py-24 md:py-40">
        {/* Violet glow */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(ellipse 80% 60% at 50% 100%, rgba(139,92,246,0.08) 0%, transparent 70%)' }}
          aria-hidden="true"
        />
        <RevealSection className="relative z-10 mx-auto flex max-w-xl flex-col items-center gap-6 text-center">
          <h2
            className="text-3xl font-normal text-zinc-100 md:text-4xl"
            style={{ fontFamily: "'Instrument Serif', serif" }}
          >
            Stop applying blind
          </h2>
          <p className="text-base leading-relaxed text-zinc-400">
            Join the waitlist. We'll let you know when a spot opens.
          </p>
          <div className="w-full max-w-md">
            <WaitlistForm source="bottom" />
          </div>
        </RevealSection>
      </section>

      {/* ---- Footer ---- */}
      <footer className="border-t border-zinc-800 px-6 py-6">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <a
            href="https://linkedin.com/in/juan-azabal"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-zinc-500 underline-offset-4 hover:text-zinc-300 hover:underline transition-colors"
          >
            Built by Juan Azabal
          </a>
          <span className="text-sm text-zinc-600">Barcelona, 2025</span>
        </div>
      </footer>
    </div>
  );
}
