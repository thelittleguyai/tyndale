'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  adminReviewQueue,
  type ConfidenceBand,
  type ReviewHealth,
  type ReviewQueueItem,
  type ReviewState,
} from '@/lib/api-client';
import { PENDING_STATES, QUEUE_PILLS, pillCount, pillLabel } from '@/lib/review-queue-filters';
import {
  BandPill,
  Card,
  DocumentSetChip,
  FlagChips,
  IntakeModeChip,
  StatePill,
  age,
  caseTitle,
  humanize,
  money,
  pct,
  serviceDate,
  shortId,
} from './review-ui';
import { SamplingDial } from './sampling-dial';

// The reviewer queue (doc 39 §1 + mockup human_review_queue.svg). Default view: pending
// runs, oldest first. User ids are masked server-side (`u·8c41`) — no email on this page.

const BANDS: ConfidenceBand[] = ['high', 'medium', 'low', 'unknown'];
const LOAD_TIMEOUT_MS = 30_000;

// Approval rate = approved / (approved + disapproved). A can't-verify is neither, in BOTH
// windows — say so under both, or the 7d number reads as a different statistic from the 30d.
const RATE_CAVEAT = "can't-verify excluded";

function HealthStrip({ h }: { h: ReviewHealth }) {
  const cell = (label: string, value: string, sub?: string) => (
    <Card key={label} className="min-w-[150px] flex-1">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-white/40">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white">{value}</p>
      {sub ? <p className="text-[11px] text-white/40">{sub}</p> : null}
    </Card>
  );
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      {/* the server's `unreviewed` is every run still waiting for a decision-maker: unreviewed +
          re-review. Labelled as that — beside an "Unreviewed · N" pill, the old label read as a
          contradiction. */}
      {cell('Awaiting review', String(h.unreviewed), `unreviewed + re-review · ${h.in_review} more in review`)}
      {cell('Median age', age(h.median_age_hours), 'pending runs')}
      {cell('Approval rate · 7d', pct(h.approval_rate_7d), `${h.approved_7d} approved · ${h.disapproved_7d} disapproved · ${RATE_CAVEAT}`)}
      {cell('Approval rate · 30d', pct(h.approval_rate_30d), `${h.approved_30d} approved · ${h.disapproved_30d} disapproved · ${RATE_CAVEAT}`)}
    </div>
  );
}

export function ReviewQueue() {
  const [state, setState] = useState<string>(PENDING_STATES.join(','));
  const [band, setBand] = useState<string>('');
  const [systemError, setSystemError] = useState(false);
  const [canary, setCanary] = useState(false);
  const [guardDrop, setGuardDrop] = useState(false);
  const [route, setRoute] = useState<string>('');
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [counts, setCounts] = useState<Record<ReviewState, number> | null>(null);
  const [health, setHealth] = useState<ReviewHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const inFlight = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    inFlight.current?.abort(); // a newer filter wins; a stale response never overwrites it
    const ctl = new AbortController();
    inFlight.current = ctl;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      ctl.abort();
    }, LOAD_TIMEOUT_MS);
    setLoading(true);
    const params: Record<string, string | number | boolean> = { limit: 200 };
    if (state) params.state = state;
    if (band) params.confidence = band;
    if (systemError) params.has_system_error = true;
    if (canary) params.canary = true;
    if (guardDrop) params.guard_drop = true;
    if (route) params.intake_mode = route;
    adminReviewQueue(params, ctl.signal)
      .then((r) => {
        setItems(r.items);
        setCounts(r.state_counts ?? null);
        setHealth(r.health);
        setError(null);
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted && !timedOut) return; // superseded, not failed
        setError(timedOut ? `No response after ${LOAD_TIMEOUT_MS / 1000}s` : e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        clearTimeout(timer);
        if (inFlight.current === ctl) setLoading(false);
      });
  }, [state, band, systemError, canary, guardDrop, route]);

  useEffect(() => {
    load();
    return () => inFlight.current?.abort();
  }, [load]);

  const select = 'rounded-lg border border-white/15 bg-navy-soft px-2 py-1 text-xs text-white/80';

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-white/40">Human review</p>
          <h1 className="text-xl font-bold">Review queue</h1>
        </div>
        <button
          type="button"
          onClick={load}
          className="min-h-[36px] rounded-lg border border-white/15 px-3 text-xs text-white/70 hover:bg-white/5"
        >
          Refresh
        </button>
      </div>

      {health ? <HealthStrip h={health} /> : null}
      <SamplingDial />

      {/* State filter — count pills (mockup), with a compact select where they would wrap badly.
          Both drive the same `state`; a pill's N obeys every OTHER filter on this row. */}
      <div role="group" aria-label="Filter by review state" className="mb-2 hidden flex-wrap gap-2 md:flex">
        {QUEUE_PILLS.map((p) => {
          const active = state === p.value;
          return (
            <button
              key={p.key}
              type="button"
              aria-pressed={active}
              onClick={() => setState(p.value)}
              className={`min-h-[36px] rounded-full px-3 text-xs font-semibold ${
                active ? 'bg-teal text-white' : 'border border-white/15 text-white/70 hover:bg-white/5'
              }`}
            >
              {pillLabel(p, counts)}
            </button>
          );
        })}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          aria-label="Filter by review state"
          className={`${select} md:hidden`}
        >
          {QUEUE_PILLS.map((p) => (
            <option key={p.key} value={p.value}>
              {pillLabel(p, counts)}
            </option>
          ))}
        </select>
        <select value={band} onChange={(e) => setBand(e.target.value)} aria-label="Filter by confidence" className={select}>
          <option value="">Any confidence</option>
          {BANDS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        {/* doc 40 §D: both front doors land in this one queue — filter to compare them */}
        <select value={route} onChange={(e) => setRoute(e.target.value)} aria-label="Filter by intake route" className={select}>
          <option value="">Any intake route</option>
          <option value="guided">Guided intake</option>
          <option value="chat_first">Chat-first</option>
        </select>
        <label className="flex items-center gap-1 text-white/60">
          <input type="checkbox" checked={systemError} onChange={(e) => setSystemError(e.target.checked)} />
          system error
        </label>
        <label className="flex items-center gap-1 text-white/60" title="a planted fixture marker (02417 / 05821 / Z4411) leaked into a tripwire">
          <input type="checkbox" checked={canary} onChange={(e) => setCanary(e.target.checked)} />
          canary marker hit
        </label>
        <label className="flex items-center gap-1 text-white/60" title="a fabrication guard removed or downgraded something on this run">
          <input type="checkbox" checked={guardDrop} onChange={(e) => setGuardDrop(e.target.checked)} />
          guard drop
        </label>
        <span role="status" className="ml-auto text-white/40">
          {loading ? 'Loading…' : listedLabel(items.length, state, counts)}
        </span>
      </div>

      {error ? (
        <div role="alert" className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-rose-soft">
            Couldn’t load the queue: {error}
            {items.length ? ' — showing the last loaded rows.' : ''}
          </span>
          <button
            type="button"
            onClick={load}
            className="min-h-[36px] rounded-lg border border-white/15 px-3 text-xs text-white/80 hover:bg-white/5"
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-[11px] uppercase tracking-wider text-white/40">
            <tr>
              <th className="px-3 py-2">Case</th>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Run</th>
              <th className="px-3 py-2">Audit result</th>
              <th className="px-3 py-2">Confidence</th>
              <th className="px-3 py-2">State</th>
              <th className="px-3 py-2">Flags</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.review_id} className="border-t border-white/10 align-top hover:bg-white/5">
                <td className="px-3 py-2">
                  <Link href={`/review/${it.case_file_id}`} className="font-semibold text-white hover:underline">
                    {caseTitle(it.provider)}
                  </Link>
                  <span className="block text-[11px] text-white/60">
                    {serviceDate(it.service_date) ?? 'service date not extracted'}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-2">
                    <DocumentSetChip set={it.document_set} />
                    <IntakeModeChip mode={it.intake_mode} />
                    <span className="whitespace-nowrap font-mono text-[11px] text-white/40">
                      {shortId(it.case_file_id)} #{it.run_seq}
                    </span>
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-xs text-white/70">{it.user_masked ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-white/70">
                  {humanize(it.terminal_status)}
                  {it.incomplete_reason ? <span className="text-white/40"> · {humanize(it.incomplete_reason)}</span> : null}
                  <span className="block text-[11px] text-white/40">{age(it.age_hours)} ago</span>
                </td>
                <td className="px-3 py-2 text-xs text-white/70">
                  {it.findings_count} finding{it.findings_count === 1 ? '' : 's'}
                  <span className="block text-[11px] text-white/40">{money(it.net_finding_usd)} identified</span>
                </td>
                <td className="px-3 py-2">
                  <BandPill band={it.confidence_band} />
                </td>
                <td className="px-3 py-2">
                  <StatePill state={it.state} />
                  {it.verdict ? (
                    <span className="block text-[11px] text-white/40">
                      {humanize(it.verdict.verdict)}
                      {it.verdict.cause ? ` · ${humanize(it.verdict.cause)}` : ''}
                    </span>
                  ) : null}
                  {/* who claimed or decided it. Not an assignment — doc 39 §7-2e: no assignment
                      machinery in Phase 1 — so it is a line under the state, not a column. */}
                  {it.reviewer_masked ? (
                    <span className="block font-mono text-[11px] text-white/40">{it.reviewer_masked}</span>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <FlagChips flags={it.flags} sampled={it.sampled} />
                </td>
              </tr>
            ))}
            {!loading && !items.length ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-sm text-white/40">
                  Nothing in this view.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** "200 of 347 runs" when the page is a truncated slice of what the pill counted — the list is
 *  capped at 200 and must not read as the whole view. */
function listedLabel(listed: number, state: string, counts: Record<ReviewState, number> | null): string {
  const pill = QUEUE_PILLS.find((p) => p.value === state);
  const total = pill ? pillCount(pill, counts) : null;
  const noun = `run${(total ?? listed) === 1 ? '' : 's'}`;
  return total !== null && total > listed ? `${listed} of ${total} ${noun}` : `${listed} ${noun}`;
}
