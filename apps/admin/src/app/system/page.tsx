'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import {
  adminListCrons,
  adminSystemHealth,
  adminTriggerCron,
  type AdminCronSummary,
  type AdminSystemHealth,
} from '@/lib/api-client';

function Tile({ label, value, ok }: { label: string; value: string; ok: boolean | null }) {
  const c =
    ok === null
      ? 'bg-white/10 text-white/50'
      : ok
        ? 'bg-sage/20 text-sage'
        : 'bg-rose/20 text-rose';
  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <p className="text-xs uppercase tracking-wide text-white/40">{label}</p>
      <span className={`mt-2 inline-block rounded-md px-2 py-0.5 text-sm ${c}`}>{value}</span>
    </div>
  );
}

export default function SystemPage() {
  const [health, setHealth] = useState<AdminSystemHealth | null>(null);
  const [crons, setCrons] = useState<AdminCronSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(() => {
    adminSystemHealth()
      .then(setHealth)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    adminListCrons()
      .then((r) => setCrons(r.crons))
      .catch(() => {});
  }, []);

  useEffect(() => load(), [load]);

  const trigger = async (name: string) => {
    setMsg(null);
    try {
      const r = await adminTriggerCron(name);
      setMsg(`Triggered ${name} → ${r.run_id.slice(0, 8)} (${r.status})`);
      setTimeout(load, 800);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">System</h1>
      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
      {!health ? (
        <p className="text-sm text-white/40">Loading…</p>
      ) : (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tile label="Runtime" value={health.runtime_version} ok />
            <Tile
              label="Database"
              value={health.db_pool.size !== null ? `pool ${health.db_pool.size}` : 'ok'}
              ok
            />
            <Tile label="Qdrant" value={health.qdrant_status} ok={health.qdrant_status === 'healthy'} />
            <Tile
              label="Claude"
              value={health.anthropic_status}
              // "foundry" (managed identity) and "anthropic-direct" are live paths;
              // "stub" (fixture fallback) is neutral, not a failure.
              ok={
                health.anthropic_status === 'foundry' ||
                health.anthropic_status === 'anthropic-direct'
                  ? true
                  : null
              }
            />
          </div>
          <div className="mb-5 rounded-2xl border border-white/10 bg-navy-soft p-4 text-sm text-white/60">
            <span className="text-white/40">Deploy:</span> {health.deploy_sha ?? '—'} ·{' '}
            <span className="text-white/40">env:</span> {health.node_env}
            {health.last_claude_call ? (
              <>
                {' · '}
                <span className="text-white/40">Last Claude call:</span>{' '}
                <span
                  className={
                    health.last_claude_call.status === 'error'
                      ? 'text-rose'
                      : health.last_claude_call.status === 'ok'
                        ? 'text-sage'
                        : 'text-white/50'
                  }
                >
                  {health.last_claude_call.status}
                  {health.last_claude_call.path ? ` (${health.last_claude_call.path})` : ''}
                  {health.last_claude_call.detail ? ` — ${health.last_claude_call.detail}` : ''}
                </span>
                {health.last_claude_call.at ? (
                  <span className="text-white/30"> · {new Date(health.last_claude_call.at).toLocaleString()}</span>
                ) : null}
              </>
            ) : null}
          </div>

          <h2 className="mb-2 text-sm font-semibold text-white/80">Crons</h2>
          {msg ? <p className="mb-2 text-xs text-sage">{msg}</p> : null}
          <div className="mb-6 overflow-hidden rounded-xl border border-white/10">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
                <tr>
                  <th className="px-4 py-2">Cron</th>
                  <th className="px-4 py-2">Schedule</th>
                  <th className="px-4 py-2">Last run</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {crons.map((c) => (
                  <tr key={c.cron_name} className="border-t border-white/5 hover:bg-white/5">
                    <td className="px-4 py-2">
                      <Link href={`/system/crons/${c.cron_name}`} className="text-sage hover:underline">
                        {c.cron_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-white/50">{c.schedule}</td>
                    <td className="px-4 py-2 text-white/40">
                      {c.last_run_at ? new Date(c.last_run_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2 text-white/60">{c.last_status ?? '—'}</td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => trigger(c.cron_name)}
                        className="rounded-md border border-white/15 px-2 py-1 text-xs text-white/70 hover:bg-white/5"
                      >
                        Trigger
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="mb-2 text-sm font-semibold text-white/80">Recent errors</h2>
          <div className="rounded-xl border border-white/10 bg-navy-soft p-4 text-sm">
            {health.recent_errors.length ? (
              health.recent_errors.map((e) => (
                <div key={e.event_id} className="border-b border-white/5 py-1 text-xs last:border-0">
                  <span className="text-rose">{e.outcome}</span>{' '}
                  <span className="text-white/60">{e.event_type}</span>{' '}
                  <span className="text-white/40">{e.error ?? ''}</span>
                </div>
              ))
            ) : (
              <p className="text-white/30">No recent errors</p>
            )}
          </div>
        </>
      )}
    </AdminShell>
  );
}
