export default function MockCVButton() {
  return (
    <div className="relative" style={{ height: '42px' }}>
      <style>{`
        /* 6s total cycle: Generate(1.5s) → Generating(1.5s) → Downloaded(3s) */
        @keyframes cv-frame-1 {
          0%, 100% { opacity: 0; }
          3.3%  { opacity: 1; }
          21.7% { opacity: 1; }
          25%   { opacity: 0; }
        }
        @keyframes cv-frame-2 {
          0%, 25%  { opacity: 0; }
          28.3% { opacity: 1; }
          46.7% { opacity: 1; }
          50%   { opacity: 0; }
          100%  { opacity: 0; }
        }
        @keyframes cv-frame-3 {
          0%, 50%  { opacity: 0; }
          53.3% { opacity: 1; }
          96.7% { opacity: 1; }
          100%  { opacity: 0; }
        }
      `}</style>

      {/* Frame 1: Generate CV */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ animation: 'cv-frame-1 6s ease infinite', animationDelay: '0s', opacity: 0 }}
      >
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white"
          tabIndex={-1}
        >
          <span>📄</span>Generate CV
        </button>
      </div>

      {/* Frame 2: Generating CV... */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ animation: 'cv-frame-2 6s ease infinite', animationDelay: '0s', opacity: 0 }}
      >
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white"
          tabIndex={-1}
        >
          <svg className="h-4 w-4 animate-spin text-violet-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Generating CV...
        </button>
      </div>

      {/* Frame 3: CV downloaded */}
      <div
        className="absolute inset-0 flex items-center justify-center"
        style={{ animation: 'cv-frame-3 6s ease infinite', animationDelay: '0s', opacity: 0 }}
      >
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white"
          tabIndex={-1}
        >
          <span className="text-violet-200">✓</span>CV downloaded
        </button>
      </div>
    </div>
  );
}
