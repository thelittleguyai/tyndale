'use client';

/**
 * "Not a chatbot with opinions" — two chats answer the same question side by side, message by
 * message (Landing Motion Parity, Phase A — 2026-09-23). Ported from Brock's round-2
 * `chat-compare.tsx`: the alternating timeline, the typing beat sized to the message, the
 * `rise` entrances and the spotlight that pins a flag to a message for a few seconds. On OUR
 * tokens — the prototype's glass tiles are the held N7 decision and are not here.
 *
 * The words are NOT the prototype's. The Tyndale pane is registry copy
 * (`content/landing-compare.json` mirrors `orchestration_script.md` verbatim; a runtime guard
 * test fails on drift): it reads the documents, shows a RANGE where an input is missing, cites
 * the plan clause it stands on, and never states a statistic. The other pane is the foil.
 *
 * Playback starts when the band enters view, runs ONCE, then offers Replay. Reduced motion
 * renders the whole transcript statically.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, Check, RotateCcw, Sparkles, X } from 'lucide-react';

import compare from '../content/landing-compare.json';
import { useInView, useReducedMotion } from '../lib/motion';
import { Logo } from './logo';

type Pane = 'generic' | 'tyndale';
type Msg = {
  from: 'user' | 'bot';
  text: string;
  key?: string;
  spot?: string;
  chip?: { key?: string; text: string };
  flag?: string;
};
type PaneData = {
  name: string;
  subtitle: string;
  pill: string;
  aria: string;
  caption: string;
  messages: Msg[];
};

const PANES = compare.panes as Record<Pane, PaneData>;
const MESSAGES: Record<Pane, Msg[]> = {
  generic: PANES.generic.messages,
  tyndale: PANES.tyndale.messages,
};

/* The "typing" beat before a message lands, by who is talking. The foil types longest — it
   has the most to say and the least to show for it. */
const TYPING_MS: Record<'user' | Pane, number> = { user: 1400, tyndale: 2800, generic: 4000 };
/* How long a flag stays pinned to its message before it fades. */
const SPOTLIGHT_MS = 5800;

type Step = { panes: Pane[]; index: number; typing: number };

/** The shared timeline: the one question lands in both panes at once, then the panes
 *  alternate so both conversations feel like they are happening at the same time. */
function buildTimeline(): Step[] {
  const steps: Step[] = [{ panes: ['tyndale', 'generic'], index: 0, typing: TYPING_MS.user }];
  const max = Math.max(MESSAGES.tyndale.length, MESSAGES.generic.length);
  for (let i = 1; i < max; i++) {
    for (const pane of ['tyndale', 'generic'] as const) {
      const msg = MESSAGES[pane][i];
      if (msg) steps.push({ panes: [pane], index: i, typing: msg.from === 'user' ? TYPING_MS.user : TYPING_MS[pane] });
    }
  }
  return steps;
}
const TIMELINE = buildTimeline();
const FULL = { generic: MESSAGES.generic.length, tyndale: MESSAGES.tyndale.length };

/* ── text: `**bold**`, line breaks, and the spotlight phrase ─────────────────────────── */

function Spot({ lit, pane, children }: { lit: boolean; pane: Pane; children: ReactNode }) {
  return (
    <span
      className={
        'rounded-sm transition-colors duration-500 ' +
        (lit
          ? pane === 'tyndale'
            ? 'bg-sage-soft underline decoration-sage decoration-2 underline-offset-4'
            : 'bg-rose-soft underline decoration-rose decoration-2 underline-offset-4'
          : '')
      }
    >
      {children}
    </span>
  );
}

function renderText(text: string, pane: Pane, spot: string | undefined, lit: boolean): ReactNode {
  const withSpot = (s: string, k: string): ReactNode => {
    if (!spot) return s;
    const at = s.indexOf(spot);
    if (at < 0) return s;
    return (
      <span key={k}>
        {s.slice(0, at)}
        <Spot lit={lit} pane={pane}>
          {spot}
        </Spot>
        {s.slice(at + spot.length)}
      </span>
    );
  };
  return text.split('\n').map((line, li) => (
    <span key={li} className="block">
      {line.split('**').map((seg, si) =>
        si % 2 === 1 ? <strong key={si}>{withSpot(seg, `${li}-${si}`)}</strong> : withSpot(seg, `${li}-${si}`),
      )}
    </span>
  ));
}

/* ── pieces ─────────────────────────────────────────────────────────────────────────── */

function TypingDots() {
  return (
    <div
      className="flex w-fit items-center gap-1 rounded-2xl rounded-bl-md bg-cream px-3.5 py-3 ring-1 ring-line"
      aria-hidden="true"
    >
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="tyn-typing h-1.5 w-1.5 rounded-full bg-ink/40"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </div>
  );
}

function Bubble({ msg, pane, lit }: { msg: Msg; pane: Pane; lit: boolean }) {
  const isUser = msg.from === 'user';
  const win = pane === 'tyndale';
  return (
    <div className={'tyn-rise flex flex-col gap-1.5 ' + (isUser ? 'items-end' : 'items-start')}>
      <div
        className={
          'max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed ' +
          (isUser
            ? 'rounded-br-md bg-navy text-white'
            : win
              ? 'rounded-bl-md bg-teal-tint text-ink ring-1 ring-teal/20'
              : 'rounded-bl-md bg-cream text-ink/75 ring-1 ring-line')
        }
      >
        {renderText(msg.text, pane, msg.spot, lit)}
        {msg.chip ? (
          <span className="mt-2 inline-flex max-w-full items-center rounded-full bg-citation-soft px-2.5 py-0.5 text-[11.5px] font-medium text-citation-deep">
            {msg.chip.text}
          </span>
        ) : null}
      </div>
      {/* The flag pins to its message with the spotlight, then goes away entirely. */}
      {msg.flag && lit ? (
        <span
          className={
            'tyn-rise inline-flex max-w-[92%] items-start gap-1.5 rounded-lg px-3 py-2 text-[12.5px] font-medium leading-snug ring-1 ' +
            (win ? 'bg-sage-soft text-sage-deep ring-sage/30' : 'bg-rose-soft text-rose-deep ring-rose/30')
          }
        >
          {win ? (
            <Check size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
          ) : (
            <X size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
          )}
          {msg.flag}
        </span>
      ) : null}
    </div>
  );
}

function Panel({
  pane,
  visible,
  typing,
  spotIndex,
  smooth,
}: {
  pane: Pane;
  visible: number;
  typing: boolean;
  spotIndex: number | null;
  smooth: boolean;
}) {
  const data = PANES[pane];
  const win = pane === 'tyndale';
  const scrollRef = useRef<HTMLDivElement | null>(null);

  /* Keep the newest message in view inside the panel while it plays. The static (reduced
     motion) transcript starts at the top, to be read in order. */
  useEffect(() => {
    const el = scrollRef.current;
    if (el && smooth) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [visible, typing, smooth]);

  return (
    <section
      aria-label={data.aria}
      className={
        'overflow-hidden rounded-lg bg-surface shadow-card ring-1 ' + (win ? 'ring-teal/25' : 'ring-line')
      }
    >
      <header
        className={
          'flex items-center gap-2.5 border-b px-4 py-3 ' + (win ? 'border-teal/15 bg-teal-tint' : 'border-line')
        }
      >
        {win ? (
          <Logo size={32} />
        ) : (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cream text-ink/50">
            <Sparkles size={16} aria-hidden="true" />
          </span>
        )}
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-ink">{data.name}</p>
          <p className="text-[12px] leading-snug text-ink/55">{data.subtitle}</p>
        </div>
        <span
          className={
            'ml-auto inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ' +
            (win ? 'bg-sage-soft text-sage-deep' : 'bg-rose-soft text-rose-deep')
          }
        >
          {win ? <Check size={12} aria-hidden="true" /> : <AlertTriangle size={12} aria-hidden="true" />}
          {data.pill}
        </span>
      </header>
      <div ref={scrollRef} className="flex h-[400px] flex-col gap-3 overflow-y-auto p-4 md:h-[460px]">
        {data.messages.slice(0, visible).map((m, i) => (
          <Bubble key={i} msg={m} pane={pane} lit={spotIndex === i} />
        ))}
        {typing ? <TypingDots /> : null}
      </div>
    </section>
  );
}

/* ── the playback ───────────────────────────────────────────────────────────────────── */

export function ChatCompare() {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inView = useInView(rootRef, { threshold: 0.25 });
  const reduced = useReducedMotion();
  const [stepIdx, setStepIdx] = useState(0);
  const [typing, setTyping] = useState<Pane | null>(null);
  const [count, setCount] = useState<Record<Pane, number>>({ generic: 0, tyndale: 0 });
  const [spot, setSpot] = useState<{ pane: Pane; index: number } | null>(null);
  const [run, setRun] = useState(0);

  /* Reduced motion: the whole transcript, no beats, no spotlight. */
  useEffect(() => {
    if (!reduced) return;
    setCount(FULL);
    setTyping(null);
    setSpot(null);
  }, [reduced]);

  /* Play the shared timeline: a typing beat, then the message lands. */
  useEffect(() => {
    if (reduced || !inView || stepIdx >= TIMELINE.length) {
      setTyping(null);
      return;
    }
    const step = TIMELINE[stepIdx];
    const msg = MESSAGES[step.panes[0]][step.index];
    /* The visitor's own lines get a beat but no typing bubble. */
    setTyping(msg.from === 'user' ? null : step.panes[0]);
    const t = setTimeout(() => {
      setCount((c) => {
        const next = { ...c };
        for (const p of step.panes) next[p] = step.index + 1;
        return next;
      });
      setTyping(null);
      if (msg.flag) setSpot({ pane: step.panes[0], index: step.index });
      setStepIdx((i) => i + 1);
    }, step.typing);
    return () => clearTimeout(t);
  }, [stepIdx, inView, reduced, run]);

  /* The spotlight fades on its own (unless a newer one replaced it). */
  useEffect(() => {
    if (!spot) return;
    const t = setTimeout(() => setSpot(null), SPOTLIGHT_MS);
    return () => clearTimeout(t);
  }, [spot]);

  const done = !reduced && stepIdx >= TIMELINE.length;
  const replay = () => {
    setCount({ generic: 0, tyndale: 0 });
    setSpot(null);
    setTyping(null);
    setStepIdx(0);
    setRun((r) => r + 1);
  };

  return (
    <div ref={rootRef} className="mt-10" data-playback={reduced ? 'static' : done ? 'done' : inView ? 'playing' : 'waiting'}>
      <p className="mb-4 flex flex-wrap items-center gap-2 text-[13px] text-ink/55">
        <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
          Example
        </span>
        {compare.example_note}
      </p>
      <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2">
        {(['generic', 'tyndale'] as const).map((pane) => (
          <div key={pane} className="flex flex-col gap-3">
            <Panel
              pane={pane}
              visible={count[pane]}
              typing={typing === pane}
              spotIndex={spot?.pane === pane ? spot.index : null}
              smooth={!reduced}
            />
            <p className="px-1 text-[14px] leading-relaxed text-ink/60">{PANES[pane].caption}</p>
          </div>
        ))}
      </div>
      {done ? (
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={replay}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-line bg-surface px-5 text-sm font-medium text-ink transition hover:bg-cream focus:outline-none focus-visible:ring-2 focus-visible:ring-teal/60"
          >
            <RotateCcw size={15} aria-hidden="true" />
            {compare.replay}
          </button>
        </div>
      ) : null}
    </div>
  );
}
