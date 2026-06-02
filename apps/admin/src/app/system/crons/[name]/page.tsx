'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Fragment, useCallback, useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import { adminCronRuns, adminTriggerCron, type AdminCronRun } from '@/lib/api-client';

function statusPill(s: string): string {
  if (s === 'success') return 'bg-sage/20 text-sage';
  if (s === 'failed') return 'bg-rose/20 text-rose';
  return 'bg-amber/20 text-amber';
}

export default function CronDetailPage() {
  const params = useParams<{ name: string }>();
  const name = String(params.name);
  const [runs, setRuns] = useState<AdminCronRun[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    adminCronRuns(name)
      .then((r) => setRuns(r.runs))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [name]);

  useEffect(() => load(), [load]);

  const trigger = async () => {
    setMsg(null);
    try {
      const r = await adminTriggerCron(name);
      setMsg(`Run ${r.run_id.slice(0, 8)} (${r.status})`);
      setTimeout(load, 800);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AdminShell>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/system" className="text-sm text-white/40 hover:text-white/70">
            ← System
          </Link>
          <h1 className="text-xl font-bold">{name}</h1>
        </div>
        <button onClick={trigger} className="rounded-lg bg-sage px-3 py-1.5 text-sm font-bold text-ink">
          Trigger now
        </button>
      </div>
      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
      {msg ? <p className="mb-3 text-xs text-sage">{msg}</p> : null}

      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
            <tr>
              <th className="px-4 py-2">Started</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Finished</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <Fragment key={r.run_id}>
                <tr
                  onClick={() => setExpanded(expanded === r.run_id ? null : r.run_id)}
                  className="cursor-pointer border-t border-white/5 hover:bg-white/5"
                >
                  <td className="px-4 py-2 text-white/50">
                    {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-md px-2 py-0.5 text-xs ${statusPill(r.status)}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-white/50">{r.triggered_source}</td>
                  <td className="px-4 py-2 text-white/40">
                    {r.finished_at ? new Date(r.finished_at).toLocaleString() : '—'}
                  </td>
                </tr>
                {expanded === r.run_id ? (
                  <tr className="bg-black/20">
                    <td colSpan={4} className="px-4 py-2">
                      <pre className="overflow-auto text-[11px] text-white/60">
                        {JSON.stringify(
                          { summary: r.summary_json, error: r.error_message },
                          null,
                          2,
                        )}
                      </pre>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
            {!runs.length ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-white/30">
                  No runs yet
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
