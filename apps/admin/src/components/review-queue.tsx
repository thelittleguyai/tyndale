'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import {
  adminReviewQueue,
  adminReviewSettings,
  adminSetReviewSampling,
  type ConfidenceBand,
  type ReviewHealth,
  type ReviewQueueItem,
  type ReviewSettings,
  type ReviewState,
} from '@/lib/api-client';
import {
  BandPill,
  Card,
  FlagChips,
  STATE_LABEL,
  StatePill,
  age,
  humanize,
  money,
  pct,
  shortId,
} from './review-ui';

// The reviewer queue (doc 39 §1 + mockup human_review_queue.svg). Default view: pending
// runs, oldest first. User ids are masked server-side (`u·8c41`) — no email on this page.

const PENDING = 'unreviewed,in_review,re_review';
const STATES: ReviewState[] = ['unreviewed', 'in_review', 're_review', 'approved', 'disapproved', 'cant_verify'];
const BANDS: ConfidenceBand[] = ['high', 'medium', 'low', 'unknown'];

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
      {cell('Unreviewed', String(h.unreviewed), `${h.in_review} in review`)}
      {cell('Median age', age(h.median_age_hours), 'pending runs')}
      {cell('Approval rate · 7d', pct(h.approval_rate_7d), `${h.approved_7d} approved · ${h.disapproved_7d} disapproved`)}
      {cell('Approval rate · 30d', pct(h.approval_rate_30d), `${h.approved_30d} approved · ${h.disapproved_30d} disapproved · can't-verify excluded`)}
    </div>
  );
}

function SamplingDial() {
  const [settings, setSettings] = useState<ReviewSettings | null>(null);
  const [draft, setDraft] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    adminReviewSettings()
      .then((s) => {
        setSettings(s);
        setDraft(String(s.review_sample_pct));
      })
      .catch(() => setSettings(null));
  }, []);

  const save = async () => {
    const n = Number(draft);
    if (!Number.isInteger(n) || n < 0 || n > 100) {
      setMsg('0–100 only');
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const r = await adminSetReviewSampling(n);
      setSettings((s) => (s ? { ...s, review_sample_pct: r.review_sample_pct } : s));
      setMsg('Saved');
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!settings) return null;
  const on = Object.entries(settings.triggers)
    .filter(([, v]) => v)
    .map(([k]) => humanize(k));
  return (
    <Card className="mb-4 flex flex-wrap items-center gap-3 text-xs text-white/60">
      <span className="font-semibold uppercase tracking-widest text-white/40">Sampling</span>
      <label className="flex items-center gap-2">
        review
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          inputMode="numeric"
          className="w-14 rounded border border-white/15 bg-transparent px-2 py-1 text-right text-white"
        />
        % of completed runs
      </label>
      <button
        onClick={save}
        disabled={busy || draft === String(settings.review_sample_pct)}
        className="rounded-lg border border-white/15 px-2 py-1 text-white/70 hover:bg-white/5 disabled:opacity-40"
      >
        Save
      </button>
      {msg ? <span className="text-white/50">{msg}</span> : null}
      <span className="ml-auto text-white/40">
        always enqueued: {on.length ? on.join(' · ') : 'none'} · env default {settings.env_default_pct}%
      </span>
    </Card>
  );
}

export function ReviewQueue() {
  const [state, setState] = useState<string>(PENDING);
  const [band, setBand] = useState<string>('');
  const [systemError, setSystemError] = useState(false);
  const [canary, setCanary] = useState(false);
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [health, setHealth] = useState<ReviewHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number | boolean> = { limit: 200 };
    if (state) params.state = state;
    if (band) params.confidence = band;
    if (systemError) params.has_system_error = true;
    if (canary) params.canary = true;
    adminReviewQueue(params)
      .then((r) => {
        setItems(r.items);
        setHealth(r.health);
        setError(null);
      })
      .catch((e) => setError(e?.message ?? String(e)))
      .finally(() => setLoading(false));
  }, [state, band, systemError, canary]);

  useEffect(() => {
    load();
  }, [load]);

  const select = 'rounded-lg border border-white/15 bg-navy-soft px-2 py-1 text-xs text-white/80';

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-white/40">Human review</p>
          <h1 className="text-xl font-bold">Review queue</h1>
        </div>
        <button onClick={load} className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white/70 hover:bg-white/5">
          Refresh
        </button>
      </div>

      {health ? <HealthStrip h={health} /> : null}
      <SamplingDial />

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <select value={state} onChange={(e) => setState(e.target.value)} className={select}>
          <option value={PENDING}>Pending (unreviewed · in review · re-review)</option>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {STATE_LABEL[s]}
            </option>
          ))}
          <option value="">All states</option>
        </select>
        <select value={band} onChange={(e) => setBand(e.target.value)} className={select}>
          <option value="">Any confidence</option>
          {BANDS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-white/60">
          <input type="checkbox" checked={systemError} onChange={(e) => setSystemError(e.target.checked)} />
          system error
        </label>
        <label className="flex items-center gap-1 text-white/60">
          <input type="checkbox" checked={canary} onChange={(e) => setCanary(e.target.checked)} />
          canary
        </label>
        <span className="ml-auto text-white/40">{loading ? 'Loading…' : `${items.length} runs`}</span>
      </div>

      {error ? <p className="text-sm text-rose-soft">{error}</p> : null}

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
              <th className="px-3 py-2">Assignee</th>
              <th className="px-3 py-2">Flags</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.review_id} className="border-t border-white/10 hover:bg-white/5">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link href={`/review/${it.case_file_id}`} className="text-citation-soft hover:underline">
                    {shortId(it.case_file_id)}
                  </Link>
                  <span className="ml-1 text-white/40">#{it.run_seq}</span>
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
                </td>
                <td className="px-3 py-2 font-mono text-xs text-white/70">{it.reviewer_masked ?? '—'}</td>
                <td className="px-3 py-2">
                  <FlagChips flags={it.flags} sampled={it.sampled} />
                </td>
              </tr>
            ))}
            {!loading && !items.length ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-sm text-white/40">
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
