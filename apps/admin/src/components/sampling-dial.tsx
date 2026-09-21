'use client';

import { useCallback, useEffect, useState } from 'react';

import { adminReviewSettings, adminSetReviewSampling, type ReviewSettings } from '@/lib/api-client';
import { Card, humanize } from './review-ui';

// The sampling dial (doc 39 §7-2a). It used to `return null` when its settings call failed —
// the control that decides how much gets reviewed vanished without a word. The view below has
// no empty branch: loading, the error with a Retry, or the dial.

export type DialLoad =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; settings: ReviewSettings };

export interface DialMessage {
  text: string;
  bad: boolean;
}

/** Returns the whole-number percent, or null when the draft isn't one (so '' is not 0). */
export function parseSamplePct(draft: string): number | null {
  const n = Number(draft);
  return draft.trim() !== '' && Number.isInteger(n) && n >= 0 && n <= 100 ? n : null;
}

export function SamplingDialView({
  load,
  draft,
  busy,
  msg,
  onDraft,
  onSave,
  onRetry,
}: {
  load: DialLoad;
  draft: string;
  busy: boolean;
  msg: DialMessage | null;
  onDraft: (value: string) => void;
  onSave: () => void;
  onRetry: () => void;
}) {
  const label = <span className="font-semibold uppercase tracking-widest text-white/40">Sampling</span>;
  const shell = 'mb-4 flex flex-wrap items-center gap-3 text-xs text-white/60';

  if (load.status === 'loading') {
    return (
      <Card className={shell}>
        {label}
        <span role="status">Loading the sampling dial…</span>
      </Card>
    );
  }
  if (load.status === 'error') {
    return (
      <Card className={shell}>
        {label}
        <span role="alert" className="text-rose-soft">
          Couldn’t load the sampling settings: {load.message}. The dial itself is unchanged.
        </span>
        <button
          type="button"
          onClick={onRetry}
          className="min-h-[36px] rounded-lg border border-white/15 px-3 text-white/80 hover:bg-white/5"
        >
          Retry
        </button>
      </Card>
    );
  }

  const { settings } = load;
  const on = Object.entries(settings.triggers)
    .filter(([, v]) => v)
    .map(([k]) => humanize(k));
  return (
    <Card className={shell}>
      {label}
      <label className="flex items-center gap-2">
        review
        <input
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          inputMode="numeric"
          aria-label="Percent of completed runs to review"
          className="w-14 rounded border border-white/15 bg-transparent px-2 py-1 text-right text-white"
        />
        % of completed runs
      </label>
      <button
        type="button"
        onClick={onSave}
        disabled={busy || draft === String(settings.review_sample_pct)}
        className="min-h-[36px] rounded-lg border border-white/15 px-3 text-white/70 hover:bg-white/5 disabled:opacity-40"
      >
        {busy ? 'Saving…' : 'Save'}
      </button>
      {msg ? (
        <span role={msg.bad ? 'alert' : 'status'} className={msg.bad ? 'text-rose-soft' : 'text-white/60'}>
          {msg.text}
        </span>
      ) : null}
      <span className="ml-auto text-white/40">
        always enqueued: {on.length ? on.join(' · ') : 'none'} · env default {settings.env_default_pct}%
      </span>
    </Card>
  );
}

export function SamplingDial() {
  const [load, setLoad] = useState<DialLoad>({ status: 'loading' });
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<DialMessage | null>(null);

  const fetchSettings = useCallback(() => {
    setLoad({ status: 'loading' });
    adminReviewSettings()
      .then((s) => {
        setLoad({ status: 'ready', settings: s });
        setDraft(String(s.review_sample_pct));
      })
      .catch((e: unknown) => setLoad({ status: 'error', message: e instanceof Error ? e.message : String(e) }));
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const save = async () => {
    if (load.status !== 'ready') return;
    const n = parseSamplePct(draft);
    if (n === null) {
      setMsg({ text: 'Whole number, 0–100', bad: true });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const r = await adminSetReviewSampling(n);
      setLoad({ status: 'ready', settings: { ...load.settings, review_sample_pct: r.review_sample_pct } });
      setDraft(String(r.review_sample_pct));
      setMsg({ text: 'Saved', bad: false });
    } catch (e: unknown) {
      setMsg({ text: `Not saved: ${e instanceof Error ? e.message : String(e)}`, bad: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SamplingDialView
      load={load}
      draft={draft}
      busy={busy}
      msg={msg}
      onDraft={setDraft}
      onSave={save}
      onRetry={fetchSettings}
    />
  );
}
