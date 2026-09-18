'use client';

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
