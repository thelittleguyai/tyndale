'use client';

/**
 * Internal analytics dashboard (Internal Analytics P0). Renders the aggregated rollups per panel.
 * The design rules are enforced in the rendering, not left to convention:
 *   - Rule 1: every ratio shows its raw n/d and its pinned definition beside the percentage.
 *   - Rule 4: counts render before ratios within every panel.
 *   - Win rate and its report-rate denominator are ONE component (WinRateWithReportRate) — the
 *     number can't be shown without the basis it's reported on.
 */

import { useCallback, useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import {
  adminGetAnalytics,
  type AdminAnalytics,
  type AdminAnalyticsPanel,
  type AdminMetric,
} from '@/lib/api-client';

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`;
}

function nd(m: AdminMetric): string {
  const d = m.denominator === null ? '—' : Math.round(m.denominator);
  return `${Math.round(m.numerator)} / ${d}`;
}

/** One metric card. A count shows the integer; a ratio shows the % with its raw n/d beside it.
 * The pinned definition always rides along (Rule 1). */
function MetricStat({ m }: { m: AdminMetric }) {
  const isRatio = m.kind === 'ratio';
  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs uppercase tracking-wide text-white/40">{m.key}</p>
        {m.backfilled ? (
          <span className="rounded bg-amber/20 px-1.5 py-0.5 text-[10px] text-amber">backfilled</span>
        ) : null}
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">
          {isRatio ? pct(m.value) : Math.round(m.numerator)}
        </span>
        {isRatio ? <span className="text-sm text-white/50">{nd(m)}</span> : null}
      </div>
      <p className="mt-2 text-xs leading-5 text-white/50">{m.definition}</p>
    </div>
  );
}

/** Win rate and its report-rate denominator, hard-paired — you cannot render win rate alone. */
function WinRateWithReportRate({ win, report }: { win: AdminMetric; report: AdminMetric }) {
  return (
    <div className="rounded-2xl border border-sage/30 bg-sage/10 p-4 sm:col-span-2">
      <p className="text-xs uppercase tracking-wide text-sage">Win rate — reported beside its basis</p>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <span className="text-3xl font-bold text-sage">{pct(win.value)}</span>
        <span className="text-sm text-white/60">{nd(win)} resolved/reported</span>
        <span className="text-white/30">·</span>
        <span className="text-sm text-white/80">
          {pct(report.value)} of completed audits reported an outcome ({nd(report)})
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-white/50">{win.definition}</p>
    </div>
  );
}

/** Counts before ratios (Rule 4). The Outcomes panel replaces the win/report pair with the hard-
 * paired component so they can never be shown apart. */
function Panel({ panel }: { panel: AdminAnalyticsPanel }) {
  const byKey = Object.fromEntries(panel.metrics.map((m) => [m.key, m]));
  const win = byKey['win_rate'];
  const report = byKey['outcome_report_rate'];
  const paired = Boolean(win && report);
  const rest = panel.metrics.filter((m) => !(paired && (m.key === 'win_rate' || m.key === 'outcome_report_rate')));
  const counts = rest.filter((m) => m.kind === 'count');
  const ratios = rest.filter((m) => m.kind === 'ratio');

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-white/45">{panel.title}</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {paired ? <WinRateWithReportRate win={win} report={report} /> : null}
        {counts.map((m) => (
          <MetricStat key={m.key} m={m} />
        ))}
        {ratios.map((m) => (
          <MetricStat key={m.key} m={m} />
        ))}
      </div>
    </section>
  );
}

function StatusBoard({ status }: { status: AdminAnalytics['status'] }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-white/45">Ops · status board</h2>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-white/40">Feature flags</p>
          {Object.entries(status.flags).map(([k, on]) => (
            <div key={k} className="flex items-center justify-between py-0.5 text-sm">
              <span className="text-white/70">{k}</span>
              <span className={on ? 'text-sage' : 'text-white/30'}>{on ? 'on' : 'off'}</span>
            </div>
          ))}
        </div>
        <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-white/40">Dropped events (since boot)</p>
          {Object.keys(status.drop_counts).length === 0 ? (
            <p className="text-sm text-white/40">none</p>
          ) : (
            Object.entries(status.drop_counts).map(([k, n]) => (
              <div key={k} className="flex items-center justify-between py-0.5 text-sm">
                <span className="text-white/70">{k}</span>
                <span className="text-rose">{n}</span>
              </div>
            ))
          )}
        </div>
        <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-white/40">
            Registered but not yet live
          </p>
          {status.not_yet_live_events.map((e) => (
            <div key={e} className="py-0.5 text-sm text-white/60">
              {e}
            </div>
          ))}
          <p className="mt-2 text-xs text-white/30">{status.crons.length} crons registered</p>
        </div>
      </div>
    </section>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await adminGetAnalytics(days));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AdminShell>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Analytics</h1>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1 text-sm ${
                days === d ? 'bg-teal-deep text-white' : 'border border-white/15 text-white/60'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="text-sm text-rose">Failed to load: {error}</p> : null}
      {!data && !error ? <p className="text-sm text-white/50">Loading…</p> : null}

      {data ? (
        <>
          {data.panels.map((p) => (
            <Panel key={p.key} panel={p} />
          ))}
          <StatusBoard status={data.status} />
          <p className="mt-4 text-xs text-white/30">
            Every rate shows its raw n/d and definition (Rule 1); counts precede ratios (Rule 4).
            Window: last {data.window_days} days.
          </p>
        </>
      ) : null}
    </AdminShell>
  );
}
