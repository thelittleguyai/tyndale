'use client';

/**
 * The hero's example audit — a looping resolution that is NEVER blank (Landing Motion Parity,
 * Phase A — 2026-09-23). The previous loop began every cycle with an empty white card for
 * seconds while its rows waited on their delays; a visitor's first beat was nothing. Now the
 * three rows are on the card from the first frame in their "before" state — the billed line
 * plain, the insurer's line present, the answer line dimmed with a placeholder — and the loop
 * animates the RESOLUTION: the strike draws through the billed figure, the insurer's figure
 * settles, the answer turns green and rises in, the note fades up. It holds, then crossfades
 * back to "before" (never a wipe to white) and goes again.
 *
 * Same fixture numbers as the static mock; the resolved frame IS the old static layout, and
 * every step is opacity/transform/colour so band height never shifts. Reduced motion renders
 * the resolved frame, still. Keyframes live in app/globals.css as `tyn-mock-*` (keyframe names
 * are global). No glass: current tokens only.
 */
import { useEffect, useRef, useState } from 'react';

import { useInView, useReducedMotion } from '../lib/motion';

/* The resolution, in beats after the loop starts (ms). */
const BEATS = { strike: 1200, insurer: 2000, answer: 2900, cross: 8000 } as const;
const CROSS_MS = 900; // the crossfade back to "before" — reset happens at its midpoint

export function AuditMock() {
  const ref = useRef<HTMLDivElement | null>(null);
  const inView = useInView(ref, { threshold: 0.4 });
  const reduced = useReducedMotion();
  const [beat, setBeat] = useState(0); // 0 before · 1 strike · 2 insurer · 3 answer + note
  const [cross, setCross] = useState(false);
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    if (reduced || !inView) return;
    const timers = [
      setTimeout(() => setBeat(1), BEATS.strike),
      setTimeout(() => setBeat(2), BEATS.insurer),
      setTimeout(() => setBeat(3), BEATS.answer),
      setTimeout(() => setCross(true), BEATS.cross),
      setTimeout(() => setBeat(0), BEATS.cross + CROSS_MS / 2),
      setTimeout(() => {
        setCross(false);
        setCycle((c) => c + 1);
      }, BEATS.cross + CROSS_MS),
    ];
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced, cycle]);

  const resolved = reduced ? 3 : beat; // reduced motion: the resolved frame, no loop
  const anim = (name: string, ms: number, delay = 0) =>
    reduced ? undefined : { animation: `${name} ${ms}ms ease-out ${delay}ms both` };

  return (
    <div
      ref={ref}
      className="relative w-full max-w-md rounded-lg bg-surface p-6 shadow-elev ring-1 ring-black/5 sm:p-7"
      data-beat={resolved}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/50">
          Your audit
        </p>
        <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
          Example
        </span>
      </div>

      {/* The crossfade wraps the rows only, so the header never blinks. */}
      <div style={cross ? anim('tyn-mock-cross', CROSS_MS) : undefined}>
        <dl className="mt-5 space-y-3">
          <div className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3">
            <dt className="text-sm text-ink/55">What you were billed</dt>
            <dd
              className={
                'relative text-lg font-semibold transition-colors duration-500 ' +
                (resolved >= 1 ? 'text-ink/35' : 'text-ink/80')
              }
            >
              $2,347.18
              {/* the strikethrough draws itself when the row resolves */}
              <span
                aria-hidden
                className="absolute left-0 top-1/2 h-[1.5px] bg-ink/30"
                style={
                  resolved >= 1
                    ? (anim('tyn-mock-strike', 400) ?? { width: '100%' })
                    : { width: 0 }
                }
              />
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3">
            <dt className="text-sm text-ink/55">What your insurer says you owe</dt>
            <dd
              className={
                'text-lg font-semibold transition-colors duration-500 ' +
                (resolved >= 2 ? 'text-ink/70' : 'text-ink/40')
              }
            >
              $1,184.60
            </dd>
          </div>
          <div
            className={
              'flex items-baseline justify-between gap-4 rounded-md border px-4 py-3.5 transition-colors duration-500 ' +
              (resolved >= 3 ? 'border-sage/25 bg-sage-soft' : 'border-dashed border-line-soft')
            }
          >
            <dt
              className={
                'text-sm font-medium transition-colors duration-500 ' +
                (resolved >= 3 ? 'text-teal-deep' : 'text-ink/45')
              }
            >
              What you should actually owe
            </dt>
            <dd className="text-2xl font-bold tabular-nums">
              {resolved >= 3 ? (
                <span key={cycle} className="block text-sage-deep" style={anim('tyn-mock-row', 550)}>
                  $612.40
                </span>
              ) : (
                <span className="block text-ink/25" aria-label="not yet computed">
                  —
                </span>
              )}
            </dd>
          </div>
        </dl>

        <p
          className={'mt-4 text-xs leading-relaxed text-ink/45 ' + (resolved >= 3 ? '' : 'opacity-0')}
          style={resolved >= 3 ? anim('tyn-mock-fade', 600, 500) : undefined}
        >
          Every difference is a finding, cited to your plan documents and published rates.
        </p>
      </div>
    </div>
  );
}
