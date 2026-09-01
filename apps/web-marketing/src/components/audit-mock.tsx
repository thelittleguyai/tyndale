'use client';

/**
 * The hero's example audit — ANIMATED (Brock round-2 gap, 2026-08-28): documents stack in,
 * the three numbers resolve in sequence, the finding line settles. Motion only — the same
 * fixture numbers as the static mock, and the FINAL frame is exactly the old static layout
 * (elements animate opacity/transform, so band height never shifts).
 *
 * `prefers-reduced-motion` renders the static presentation unchanged. No animation library:
 * CSS keyframes + one IntersectionObserver to start when the card is actually on screen.
 * Deliberately NOT the prototype's looping stateful demo — and no glass: current tokens only.
 */
import { useEffect, useRef, useState } from 'react';

const DOC_CHIPS = ['Bill.pdf', 'EOB.pdf', 'Insurance card'];

export function AuditMock() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [play, setPlay] = useState(false);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setPlay(true);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const row = (i: number) =>
    play ? { animation: `mock-row 0.55s ease-out ${900 + i * 550}ms both` } : undefined;

  return (
    <div
      ref={ref}
      className="relative w-full max-w-md rounded-lg bg-surface p-6 shadow-elev ring-1 ring-black/5 sm:p-7"
      data-animated={play || undefined}
    >
      <style>{`
        @keyframes mock-doc {
          0% { opacity: 0; transform: translateY(-14px) scale(0.96); }
          22% { opacity: 1; transform: translateY(0) scale(1); }
          78% { opacity: 1; }
          100% { opacity: 0; transform: translateY(4px); visibility: hidden; }
        }
        @keyframes mock-row {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes mock-strike { from { width: 0; } to { width: 100%; } }
        @keyframes mock-fade { from { opacity: 0; } to { opacity: 1; } }
      `}</style>

      {/* Documents stacking in — an overlay that plays once and vanishes; absolutely
          positioned so it can never move the layout beneath it. */}
      {play ? (
        <div aria-hidden className="pointer-events-none absolute inset-x-6 top-16 z-10 flex justify-center gap-2">
          {DOC_CHIPS.map((label, i) => (
            <span
              key={label}
              className="rounded-md border border-line-soft bg-white px-2.5 py-1.5 text-[11px] font-medium text-ink/60 shadow-sm"
              style={{ animation: `mock-doc 1.5s ease-in-out ${i * 180}ms both` }}
            >
              {label}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/50">
          Your audit
        </p>
        <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
          Example
        </span>
      </div>

      <dl className="mt-5 space-y-3">
        <div
          className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3"
          style={row(0)}
        >
          <dt className="text-sm text-ink/55">What you were billed</dt>
          <dd className="relative text-lg font-semibold text-ink/35">
            $2,347.18
            {/* the strikethrough draws itself once the row lands */}
            <span
              aria-hidden
              className="absolute left-0 top-1/2 h-[1.5px] bg-ink/30"
              style={
                play
                  ? { animation: 'mock-strike 0.4s ease-out 1550ms both' }
                  : { width: '100%' }
              }
            />
          </dd>
        </div>
        <div
          className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3"
          style={row(1)}
        >
          <dt className="text-sm text-ink/55">What your insurer says you owe</dt>
          <dd className="text-lg font-semibold text-ink/70">$1,184.60</dd>
        </div>
        <div
          className="flex items-baseline justify-between gap-4 rounded-md bg-sage-soft px-4 py-3.5 ring-1 ring-sage/25"
          style={row(2)}
        >
          <dt className="text-sm font-medium text-teal-deep">What you should actually owe</dt>
          <dd className="text-2xl font-bold text-sage-deep">$612.40</dd>
        </div>
      </dl>

      <p
        className="mt-4 text-xs leading-relaxed text-ink/45"
        style={play ? { animation: 'mock-fade 0.6s ease-out 2600ms both' } : undefined}
      >
        Every difference is a finding, cited to your plan documents and published rates.
      </p>
    </div>
  );
}
