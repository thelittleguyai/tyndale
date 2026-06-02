'use client';

import { Fragment, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import {
  adminExportAuditLog,
  adminGetAuditLog,
  type AdminAuditEntry,
} from '@/lib/api-client';

const FIELDS: { key: string; placeholder: string }[] = [
  { key: 'user_id', placeholder: 'Target user id' },
  { key: 'admin_id', placeholder: 'Acting admin id' },
  { key: 'action_type', placeholder: 'Action (e.g. block)' },
  { key: 'tool_name', placeholder: 'Tool name' },
  { key: 'date_from', placeholder: 'From (ISO date)' },
  { key: 'date_to', placeholder: 'To (ISO date)' },
];

export default function AuditPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [entries, setEntries] = useState<AdminAuditEntry[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const params = (): Record<string, string> =>
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v.trim()));

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await adminGetAuditLog(params());
      setEntries(r.entries);
      setTotal(r.total_matched);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const exportJson = async () => {
    try {
      const data = await adminExportAuditLog(params());
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit-export.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AdminShell>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Audit log</h1>
        <button
          onClick={exportJson}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white/70 hover:bg-white/5"
        >
          Export JSON
        </button>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {FIELDS.map((f) => (
          <input
            key={f.key}
            value={filters[f.key] ?? ''}
            onChange={(e) => setFilters((prev) => ({ ...prev, [f.key]: e.target.value }))}
            placeholder={f.placeholder}
            className="rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
          />
        ))}
      </div>
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg bg-sage px-4 py-2 text-sm font-bold text-ink disabled:opacity-40"
        >
          {busy ? '…' : 'Search'}
        </button>
        <span className="text-xs text-white/40">{total} matched</span>
      </div>

      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
            <tr>
              <th className="px-4 py-2">Time</th>
              <th className="px-4 py-2">Actor</th>
              <th className="px-4 py-2">Action</th>
              <th className="px-4 py-2">Target</th>
              <th className="px-4 py-2">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <Fragment key={e.event_id}>
                <tr
                  onClick={() => setExpanded(expanded === e.event_id ? null : e.event_id)}
                  className="cursor-pointer border-t border-white/5 hover:bg-white/5"
                >
                  <td className="px-4 py-2 text-white/50">
                    {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-2 text-white/70">{e.actor}</td>
                  <td className="px-4 py-2 text-white/80">{e.action ?? e.event_type}</td>
                  <td className="px-4 py-2 text-white/50">
                    {e.target_user_id ? `${e.target_user_id.slice(0, 8)}…` : '—'}
                  </td>
                  <td className="px-4 py-2 text-white/50">{e.outcome}</td>
                </tr>
                {expanded === e.event_id ? (
                  <tr className="bg-black/20">
                    <td colSpan={5} className="px-4 py-2">
                      <pre className="overflow-auto text-[11px] text-white/60">
                        {JSON.stringify(e.payload, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
            {!entries.length ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-white/30">
                  No results
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
