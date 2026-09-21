'use client';

import { useEffect, useRef, useState } from 'react';

import type { ConfidenceBand, ReviewState } from '@/lib/api-client';

// Shared bits for the Human Review pages (doc 39 §7, 2026-09-18). Palette classes only —
// the design-token guard scans this app for raw hex.

export const STATE_LABEL: Record<ReviewState, string> = {
  unreviewed: 'Unreviewed',
  in_review: 'In review',
  re_review: 'Re-review',
  approved: 'Approved',
  disapproved: 'Disapproved',
  cant_verify: "Can't verify",
};

const STATE_CLASS: Record<ReviewState, string> = {
  unreviewed: 'bg-amber-soft text-amber-deep',
  in_review: 'bg-citation-soft text-citation-deep',
  re_review: 'bg-amber-soft text-amber-deep',
  approved: 'bg-sage-soft text-sage-deep',
  disapproved: 'bg-rose-soft text-rose',
  cant_verify: 'bg-white/10 text-white/60',
};

const BAND_CLASS: Record<ConfidenceBand, string> = {
  high: 'bg-sage-soft text-sage-deep',
  medium: 'bg-amber-soft text-amber-deep',
  low: 'bg-rose-soft text-rose',
  unknown: 'bg-white/10 text-white/60',
};

export function StatePill({ state }: { state: ReviewState }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATE_CLASS[state]}`}>
      {STATE_LABEL[state]}
    </span>
  );
}

export function BandPill({ band }: { band: ConfidenceBand }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ${BAND_CLASS[band]}`}>
      {band}
    </span>
  );
}

export function FlagChips({
  flags,
  sampled,
}: {
  flags: { first_case: boolean; system_error: boolean; canary: boolean; material_disagreement: boolean };
  sampled: boolean;
}) {
  const chips: { label: string; cls: string }[] = [];
  if (flags.canary) chips.push({ label: 'canary', cls: 'bg-rose-soft text-rose' });
  if (flags.system_error) chips.push({ label: 'system error', cls: 'bg-rose-soft text-rose' });
  if (flags.material_disagreement) chips.push({ label: 'EOB ≠ Tyndale', cls: 'bg-amber-soft text-amber-deep' });
  if (flags.first_case) chips.push({ label: 'first case', cls: 'bg-citation-soft text-citation-deep' });
  if (!chips.length && sampled) chips.push({ label: 'sampled', cls: 'bg-white/10 text-white/50' });
  return (
    <span className="flex flex-wrap gap-1">
      {chips.map((c) => (
        <span key={c.label} className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${c.cls}`}>
          {c.label}
        </span>
      ))}
    </span>
  );
}

export function shortId(id: string | null | undefined): string {
  return id ? `c·${id.slice(-4)}` : '—';
}

export function money(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

export function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? '—' : `${Math.round(x * 100)}%`;
}

export function age(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '—';
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  const d = Math.floor(hours / 24);
  return `${d}d ${Math.round(hours - d * 24)}h`;
}

export function when(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function humanize(s: string | null | undefined): string {
  return (s ?? '—').replace(/_/g, ' ');
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-white/40">{children}</p>;
}

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-white/10 bg-navy-soft p-3 ${className}`}>{children}</div>;
}

/** The honest empty — Phase 2 data that is not collected yet is labeled, never faked. */
export function Phase2Placeholder({ title, label }: { title: string; label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-white/15 p-3">
      <p className="text-xs font-semibold text-white/60">{title}</p>
      <p className="mt-1 text-[11px] text-white/40">{label} · not collected yet</p>
    </div>
  );
}

export function NotRecorded() {
  return <span className="italic text-white/30">not recorded</span>;
}

/** Engineers sometimes need the raw object; a PHI console must not print it by default.
 *  Collapsed, keyboard-reachable, and never the primary rendering of anything. */
export function RawToggle({ value, label = 'show raw' }: { value: unknown; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="text-[10px] uppercase tracking-widest text-white/30 hover:text-white/60"
      >
        {open ? 'hide raw' : label}
      </button>
      {open ? (
        <pre className="mt-1 max-h-64 overflow-auto rounded bg-white/5 p-2 text-[11px] leading-4 text-white/60">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

/** A compact label/value list — the typed replacement for a JSON dump. Scalars only; nested
 *  values are summarized (count / keys) and stay behind the raw toggle. */
export function KeyValues({ data, skip = [] }: { data: Record<string, unknown>; skip?: string[] }) {
  const rows = Object.entries(data).filter(([k, v]) => !skip.includes(k) && v !== null && v !== undefined && v !== '');
  if (!rows.length) return <NotRecorded />;
  const show = (v: unknown): string =>
    Array.isArray(v)
      ? v.every((x) => typeof x === 'string' || typeof x === 'number')
        ? v.join(', ')
        : `${v.length} item${v.length === 1 ? '' : 's'}`
      : typeof v === 'object'
        ? `{${Object.keys(v as object).join(', ')}}`
        : String(v);
  return (
    <dl className="grid grid-cols-[minmax(90px,140px)_1fr] gap-x-2 gap-y-0.5 text-[11px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-white/40">{humanize(k)}</dt>
          <dd className="break-words text-white/75">{show(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A right-hand side sheet (citation sources, the document viewer). Esc and the backdrop close
 *  it, focus moves in on open and back to the opener on close, the page behind is inert. */
export function Sheet({
  title,
  subtitle,
  onClose,
  wide = false,
  children,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      opener?.focus?.();
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close" onClick={onClose} className="absolute inset-0 bg-navy-deep/70" />
      <div
        className={`relative flex h-full w-full flex-col border-l border-white/10 bg-navy-soft shadow-xl ${
          wide ? 'max-w-4xl' : 'max-w-xl'
        }`}
      >
        <div className="flex items-start justify-between gap-3 border-b border-white/10 p-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">{title}</p>
            {subtitle ? <p className="truncate text-[11px] text-white/50">{subtitle}</p> : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] rounded-lg border border-white/15 px-3 text-xs text-white/70 hover:bg-white/5"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}
