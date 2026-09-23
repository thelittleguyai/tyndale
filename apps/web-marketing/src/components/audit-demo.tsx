'use client';

/**
 * How it works — the three-act product demo (Landing Motion Parity, Phase A — 2026-09-23),
 * ported from Brock's round-2 `audit-demo.tsx` on our tokens, no glass:
 *
 *   Act 1 · Add your documents — the bill, the EOB, the Summary of Benefits and the card
 *           funnel (`tyn-funnel`) into the pulsing intake ring (`tyn-intake`, opaque teal).
 *   Act 2 · Tyndale audits — the phase rail's bar runs the act's length; four worklines fill.
 *   Act 3 · Every finding, sorted — pay / overcharged / your script rise in (`tyn-rise`).
 *
 * The fixture is the HERO's numbers (content/landing-demo.json) — nothing invented — and the
 * two product-voice strings in Act 3 are registry copy, guard-tested against the registry.
 * Loops only while on screen (IntersectionObserver); reduced motion shows the final act, still.
 */
import { useEffect, useRef, useState } from 'react';
import { Check, Handshake, Phone, Quote, ScanLine, ShieldAlert } from 'lucide-react';

import demo from '../content/landing-demo.json';
import { useInView, useReducedMotion } from '../lib/motion';
import { Logo } from './logo';

type Phase = 'add' | 'audit' | 'sort';
const PHASES = demo.phases as { id: Phase; label: string; caption: string }[];
const PHASE_MS: Record<Phase, number> = { add: 6600, audit: 5600, sort: 9500 };

/* ── Act 1 · mini documents, drawn with tokens (illustrations — hidden from the tree) ── */

type Doc = (typeof demo.documents)[number];

function MiniDoc({ doc, className, style }: { doc: Doc; className?: string; style?: React.CSSProperties }) {
  const rows = 'rows' in doc ? doc.rows : undefined;
  return (
    <div
      className={'w-[128px] overflow-hidden rounded-md border border-line bg-surface shadow-card ' + (className ?? '')}
      style={style}
    >
      {doc.kind === 'card' ? (
        <div className="flex items-center justify-between bg-navy px-2 py-1">
          <span className="text-[7.5px] font-bold uppercase tracking-wide text-white">{doc.title}</span>
          <span className="h-2 w-3 rounded-[2px] bg-sage-soft" />
        </div>
      ) : (
        <div className="flex items-center justify-between px-2.5 pt-2">
          <span className={'truncate text-[8px] font-bold uppercase tracking-wide ' + (doc.kind === 'sob' ? 'text-teal' : 'text-ink/80')}>
            {doc.title}
          </span>
          {doc.kind === 'bill' ? <span className="text-[7px] font-semibold text-ink/40">BILL</span> : null}
        </div>
      )}
      <div className="px-2.5 pb-2 pt-1">
        {'note' in doc && doc.note ? <p className="text-[7.5px] text-ink/50">{doc.note}</p> : null}
        {rows ? (
          <div className="mt-1 flex flex-col gap-[3px]">
            {rows.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-[7.5px] text-ink/50">{k}</span>
                <span className="text-[7.5px] font-bold text-ink/80">{v}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-1.5 flex flex-col gap-1">
            <div className="h-1 w-full rounded-full bg-line-soft" />
            <div className="h-1 w-4/5 rounded-full bg-line-soft" />
            <div className="h-1 w-3/5 rounded-full bg-line-soft" />
          </div>
        )}
        {'amount' in doc && doc.amount ? (
          <div className="mt-1.5 flex items-center justify-between border-t border-line-soft pt-1">
            <span className="text-[7px] font-semibold uppercase text-ink/40">{doc.amount_label}</span>
            <span className="text-[10px] font-bold text-ink/80">{doc.amount}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* The funnel canvas is 520 × 300; the intake ring sits at (260, 236). Each document's
   (--fx, --fy) is the vector from its own centre to the ring. */
const RING = { x: 260, y: 236 }; // on the 520 × 300 canvas
const SLOTS: Record<string, { x: number; y: number; h: number }> = {
  bill: { x: 30, y: 4, h: 84 },
  sob: { x: 196, y: 0, h: 86 },
  eob: { x: 362, y: 4, h: 84 },
  card: { x: 196, y: 108, h: 70 },
};

function FunnelStage({ cycle, reduced }: { cycle: number; reduced: boolean }) {
  return (
    <div className="relative mx-auto h-[300px] w-full max-w-[520px]" aria-hidden="true">
      <div className="absolute left-1/2 top-0 h-[300px] w-[520px] -translate-x-1/2 scale-[0.6] sm:scale-100" style={{ transformOrigin: '50% 0' }} key={cycle}>
        {demo.documents.map((d, i) => {
          const slot = SLOTS[d.id];
          const fx = RING.x - (slot.x + 64);
          const fy = RING.y - (slot.y + slot.h / 2);
          return (
            <MiniDoc
              key={d.id}
              doc={d}
              className={reduced ? '' : 'tyn-funnel'}
              style={{
                position: 'absolute',
                left: slot.x,
                top: slot.y,
                animationDelay: `${300 + i * 520}ms`,
                ['--fx' as string]: `${fx}px`,
                ['--fy' as string]: `${fy}px`,
              }}
            />
          );
        })}
        {/* The intake ring — opaque, teal, breathing as documents arrive. */}
        <div
          className={
            'absolute flex h-[72px] w-[72px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-surface ring-4 ring-teal/25 ' +
            (reduced ? '' : 'tyn-intake')
          }
          style={{ left: RING.x, top: RING.y }}
        >
          <Logo size={44} />
        </div>
        <p
          className="absolute -translate-x-1/2 text-[12px] font-semibold uppercase tracking-wide text-teal"
          style={{ left: RING.x, top: RING.y + 44 }}
        >
          Tyndale
        </p>
      </div>
    </div>
  );
}

/* ── Act 3 · the sorted result ───────────────────────────────────────────────────────── */

const TONE = {
  pay: { text: 'text-sage-deep', chip: 'bg-sage-soft text-sage-deep', Icon: Check },
  dispute: { text: 'text-rose-deep', chip: 'bg-rose-soft text-rose-deep', Icon: ShieldAlert },
  script: { text: 'text-amber-deep', chip: 'bg-amber-soft text-amber-deep', Icon: Quote },
} as const;

function SortedCard({ item, show, delay, reduced }: { item: (typeof demo.sorted)[number]; show: boolean; delay: number; reduced: boolean }) {
  const tone = TONE[item.tone as keyof typeof TONE];
  const Icon = tone.Icon;
  return (
    <div
      className={
        'flex flex-col rounded-md bg-cream p-3.5 ring-1 ring-line ' + (show ? (reduced ? '' : 'tyn-rise') : 'opacity-0')
      }
      style={show && !reduced ? { animationDelay: `${delay}ms` } : undefined}
    >
      <div className={'flex items-center gap-2 ' + tone.text}>
        <span className={'flex h-7 w-7 items-center justify-center rounded-md ' + tone.chip}>
          <Icon size={15} aria-hidden="true" />
        </span>
        <span className="text-[12px] font-bold uppercase tracking-wide">{item.label}</span>
        {'amount' in item && item.amount ? (
          <span className="ml-auto text-[15px] font-bold tabular-nums">{item.amount}</span>
        ) : null}
      </div>
      <p className="mt-2.5 text-[13px] font-semibold text-ink">{item.title}</p>
      <p className="mt-1 text-[12.5px] leading-snug text-ink/65">
        {item.tone === 'script' ? <Handshake size={12} className="mr-1 inline-block align-[-1px] text-amber-deep" aria-hidden="true" /> : null}
        {item.tone === 'script' ? <>&ldquo;{item.body}&rdquo;</> : item.body}
      </p>
      {'chip' in item && item.chip ? (
        <span className="mt-2 inline-flex w-fit max-w-full rounded-full bg-citation-soft px-2.5 py-0.5 text-[11px] font-medium text-citation-deep">
          {item.chip.text}
        </span>
      ) : null}
    </div>
  );
}

/* ── the shell ───────────────────────────────────────────────────────────────────────── */

export function AuditDemo() {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inView = useInView(rootRef, { threshold: 0.35, once: false });
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<Phase>('add');
  const [cycle, setCycle] = useState(0);

  /* Restart from the first act each time the demo comes on screen. */
  useEffect(() => {
    if (inView && !reduced) {
      setPhase('add');
      setCycle((c) => c + 1);
    }
  }, [inView, reduced]);

  useEffect(() => {
    if (reduced) {
      setPhase('sort');
      return;
    }
    if (!inView) return;
    const t = setTimeout(() => {
      setPhase((p) => {
        if (p === 'add') return 'audit';
        if (p === 'audit') return 'sort';
        setCycle((c) => c + 1);
        return 'add';
      });
    }, PHASE_MS[phase]);
    return () => clearTimeout(t);
  }, [phase, reduced, inView]);

  const phaseIndex = PHASES.findIndex((p) => p.id === phase);
  const sort = phase === 'sort';
  const still = reduced || !inView;

  return (
    <div ref={rootRef} className="overflow-hidden rounded-lg bg-surface shadow-card ring-1 ring-black/[0.04]" data-phase={phase}>
      {/* Phase rail — add → audit → sort, the active bar timed to its act. */}
      <div className="flex items-center gap-1.5 border-b border-line px-5 pb-3 pt-4">
        {PHASES.map((p, i) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              if (p.id === 'add') setCycle((c) => c + 1);
              setPhase(p.id);
            }}
            className="flex min-h-[44px] min-w-0 flex-1 flex-col justify-center gap-1.5 rounded-sm text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-teal/60"
            aria-label={`Show step: ${p.label}`}
            aria-current={p.id === phase ? 'step' : undefined}
          >
            <span className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
              <span
                className="block h-full rounded-full bg-teal"
                style={
                  i === phaseIndex
                    ? {
                        width: '100%',
                        transitionProperty: 'width',
                        transitionTimingFunction: 'linear',
                        transitionDuration: still ? '0ms' : `${PHASE_MS[phase]}ms`,
                      }
                    : { width: i < phaseIndex ? '100%' : '0%', transition: 'width 300ms ease' }
                }
              />
            </span>
            <span
              className={
                'text-[10px] font-semibold uppercase leading-tight tracking-wide transition-colors sm:text-[12px] ' +
                (i === phaseIndex ? 'text-teal' : 'text-ink/45')
              }
            >
              {p.label}
            </span>
          </button>
        ))}
      </div>

      {/* Stage — each act is absolutely positioned so the swap never moves layout. */}
      <div className="relative min-h-[470px] sm:min-h-[420px]">
        {/* Act 1 */}
        <div
          aria-hidden={phase !== 'add'}
          className={
            'absolute inset-0 flex flex-col items-center justify-center px-4 py-5 transition-opacity duration-500 ' +
            (phase === 'add' ? 'opacity-100' : 'pointer-events-none opacity-0')
          }
        >
          {phase === 'add' ? <FunnelStage cycle={cycle} reduced={reduced} /> : null}
        </div>

        {/* Act 2 */}
        <div
          aria-hidden={phase !== 'audit'}
          className={
            'absolute inset-0 flex flex-col items-center justify-center px-6 transition-opacity duration-500 ' +
            (phase === 'audit' ? 'opacity-100' : 'pointer-events-none opacity-0')
          }
        >
          <div className="w-full max-w-sm rounded-md bg-cream p-5 ring-1 ring-line">
            <div className="flex items-center gap-2 text-teal">
              <ScanLine size={18} aria-hidden="true" />
              <span className="text-[12px] font-bold uppercase tracking-wide">Auditing your bill…</span>
            </div>
            <div className="mt-4 flex flex-col gap-3.5">
              {demo.audit_lines.map((line, i) => (
                <div key={line}>
                  <p className="text-[13px] font-medium text-ink/85">{line}</p>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line-soft">
                    <div
                      className="h-full rounded-full bg-teal"
                      style={{
                        width: phase === 'audit' || reduced ? '100%' : '0%',
                        transitionProperty: 'width',
                        transitionTimingFunction: 'ease-out',
                        transitionDuration: reduced ? '0ms' : '1400ms',
                        transitionDelay: phase === 'audit' && !reduced ? `${300 + i * 700}ms` : '0ms',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-4 text-[13px] font-medium text-ink/60">
            No guessing — every number is read from your documents.
          </p>
        </div>

        {/* Act 3 */}
        <div
          aria-hidden={!sort}
          className={
            'absolute inset-0 flex flex-col justify-center gap-2.5 overflow-y-auto px-4 py-5 transition-opacity duration-500 sm:px-5 ' +
            (sort ? 'opacity-100' : 'pointer-events-none opacity-0')
          }
        >
          <div className="grid gap-2.5 md:grid-cols-3">
            {demo.sorted.map((item, i) => (
              <SortedCard key={`${item.id}-${cycle}`} item={item} show={sort} delay={200 + i * 350} reduced={reduced} />
            ))}
          </div>
          <p className="flex items-center justify-center gap-1.5 text-center text-[13px] font-medium text-ink/60">
            <Phone size={13} className="text-teal" aria-hidden="true" />
            {demo.closing}
          </p>
        </div>
      </div>

      {/* Caption for the act on stage. */}
      <div className="border-t border-line px-5 py-4">
        <p key={phase} className={'text-center text-[14px] font-medium leading-relaxed text-ink/80 ' + (reduced ? '' : 'tyn-rise')}>
          {PHASES[phaseIndex].caption}
        </p>
      </div>
    </div>
  );
}
