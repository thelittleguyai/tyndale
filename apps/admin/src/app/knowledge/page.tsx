'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import type { PayerCorpusView, QdrantCollectionInfo } from '@tyndale/shared';

import { AdminShell } from '@/components/admin-shell';
import { adminListCollections, adminPayerInstructions } from '@/lib/api-client';
import { entryStatus, reverifyReminder, type ReverifyTone } from '@/lib/reverify';

const TONE: Record<ReverifyTone, string> = {
  overdue: 'bg-rose-soft text-rose-deep',
  soon: 'bg-amber-soft text-amber-deep',
  ok: 'bg-white/5 text-white/60',
};

/** "Where to find it" — the portal guide's corpus and its quarterly re-verify clock (item G). */
function PayerCorpus({ view }: { view: PayerCorpusView }) {
  const reminder = reverifyReminder(view);
  return (
    <section className="mt-10">
      <h2 className="mb-1 text-lg font-semibold">Payer instructions — “Where to find it”</h2>
      <p className="mb-3 text-sm text-white/50">
        From {view.source}. A payer’s path reaches members only when verified ({view.verified}); the{' '}
        {view.unverified} unverified items wait for the hands-on pass and are never shown.
      </p>
      {reminder ? (
        <p className={`mb-4 rounded-xl px-4 py-3 text-sm ${TONE[reminder.tone]}`} data-testid="reverify-reminder">
          {reminder.text}
        </p>
      ) : null}
      <div className="grid gap-3">
        {view.payers.map((p) => (
          <details key={p.payer_id} className="rounded-2xl border border-white/10 bg-navy-soft p-4">
            <summary className="cursor-pointer font-semibold">
              {p.name}{' '}
              <span className="text-xs font-normal text-white/40">
                {p.entries.filter((e) => e.verified).length} verified ·{' '}
                {p.entries.filter((e) => !e.verified).length} unverified
              </span>
            </summary>
            <ul className="mt-3 grid gap-3">
              {p.entries.map((e, i) => (
                <li key={i} className="rounded-xl border border-white/5 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-white/70">{e.document_type}</span>
                    <span className={e.verified ? (e.overdue ? 'text-rose-soft' : 'text-sage') : 'text-amber'}>
                      {entryStatus(e)}
                    </span>
                  </div>
                  {e.claim ? <p className="mt-1 text-xs text-white/40">{e.claim}</p> : null}
                  {e.steps.length ? (
                    <ol className="mt-2 list-decimal pl-5 text-white/70">
                      {e.steps.map((s, n) => (
                        <li key={n}>{s}</li>
                      ))}
                    </ol>
                  ) : null}
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </section>
  );
}

export default function KnowledgePage() {
  const [cols, setCols] = useState<QdrantCollectionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [corpus, setCorpus] = useState<PayerCorpusView | null>(null);

  useEffect(() => {
    // an older runtime without the corpus route simply shows no section — never an error banner
    adminPayerInstructions()
      .then(setCorpus)
      .catch(() => setCorpus(null));
    adminListCollections()
      .then((r) => setCols(r.collections))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Knowledge base</h1>
      {error ? <p className="mb-3 text-sm text-rose-soft">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-white/40">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {cols.map((c) => (
            <Link
              key={c.name}
              href={`/knowledge/${c.name}`}
              className="rounded-2xl border border-white/10 bg-navy-soft p-4 hover:border-white/25"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="font-semibold">{c.name}</span>
                <span
                  className={`rounded-md px-2 py-0.5 text-xs ${
                    c.exists ? 'bg-sage/20 text-sage' : 'bg-white/10 text-white/40'
                  }`}
                >
                  {c.exists ? 'live' : 'missing'}
                </span>
              </div>
              <div className="flex gap-4 text-sm text-white/60">
                <span>{c.total} chunks</span>
                <span className="text-sage">{c.live} live</span>
                <span className="text-amber">{c.staging} staging</span>
              </div>
              {c.sources.length ? (
                <p className="mt-2 truncate text-xs text-white/40">
                  Sources: {c.sources.map((s) => s.source).join(', ')}
                </p>
              ) : null}
            </Link>
          ))}
        </div>
      )}
      {corpus ? <PayerCorpus view={corpus} /> : null}
    </AdminShell>
  );
}
