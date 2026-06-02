'use client';

import { useCallback, useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import {
  adminAggregateGaps,
  adminListGaps,
  adminResolveGap,
  type AdminGap,
} from '@/lib/api-client';

type Group = { key: string; count: number };
type Cluster = { cluster: string; representative_query: string; count: number };

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <p className="mb-2 text-xs uppercase tracking-wide text-white/40">{title}</p>
      {children}
    </div>
  );
}

export default function GapsPage() {
  const [byAgent, setByAgent] = useState<Group[]>([]);
  const [byType, setByType] = useState<Group[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [gaps, setGaps] = useState<AdminGap[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    adminAggregateGaps({ group_by: 'agent', resolved: 'false' })
      .then((r) => setByAgent(r.groups ?? []))
      .catch(() => {});
    adminAggregateGaps({ group_by: 'gap_type', resolved: 'false' })
      .then((r) => setByType(r.groups ?? []))
      .catch(() => {});
    adminAggregateGaps({ group_by: 'cluster', resolved: 'false' })
      .then((r) => setClusters(r.clusters ?? []))
      .catch(() => {});
    adminListGaps({ resolved: 'false', limit: 100 })
      .then((r) => setGaps(r.gaps))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => load(), [load]);

  const totalOpen = byAgent.reduce((s, g) => s + g.count, 0);

  const resolve = async (gapId: string) => {
    const src = window.prompt('Resolved by source (e.g. "CO-2B Aetna policies"):');
    if (!src) return;
    try {
      await adminResolveGap(gapId, src);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Knowledge gaps</h1>
      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}

      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card title="Open gaps">
          <p className="text-3xl font-bold text-sage">{totalOpen}</p>
        </Card>
        <Card title="By agent">
          {byAgent.length ? (
            byAgent.map((g) => (
              <div key={g.key} className="flex justify-between text-sm">
                <span className="text-white/60">{g.key}</span>
                <span className="text-white/80">{g.count}</span>
              </div>
            ))
          ) : (
            <p className="text-sm text-white/30">—</p>
          )}
        </Card>
        <Card title="By type">
          {byType.length ? (
            byType.map((g) => (
              <div key={g.key} className="flex justify-between text-sm">
                <span className="text-white/60">{g.key}</span>
                <span className="text-white/80">{g.count}</span>
              </div>
            ))
          ) : (
            <p className="text-sm text-white/30">—</p>
          )}
        </Card>
      </div>

      <h2 className="mb-2 text-sm font-semibold text-white/80">Top query clusters (open)</h2>
      <div className="mb-6 space-y-2">
        {clusters.length ? (
          clusters.map((c) => (
            <div
              key={c.cluster}
              className="flex items-center justify-between rounded-xl border border-white/10 bg-navy-soft p-3 text-sm"
            >
              <span className="text-white/80">{c.representative_query}</span>
              <span className="text-white/40">×{c.count}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-white/30">No open clusters</p>
        )}
      </div>

      <h2 className="mb-2 text-sm font-semibold text-white/80">Raw gap log (open)</h2>
      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
            <tr>
              <th className="px-4 py-2">Logged</th>
              <th className="px-4 py-2">Agent</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Query</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {gaps.map((g) => (
              <tr key={g.gap_id} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-4 py-2 text-white/40">
                  {g.logged_at ? new Date(g.logged_at).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-2 text-white/60">{g.agent_name}</td>
                <td className="px-4 py-2 text-white/60">{g.gap_type}</td>
                <td className="px-4 py-2 text-white/70">{g.query.slice(0, 80)}</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => resolve(g.gap_id)}
                    className="rounded-md border border-white/15 px-2 py-1 text-xs text-white/70 hover:bg-white/5"
                  >
                    Resolve
                  </button>
                </td>
              </tr>
            ))}
            {!gaps.length ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-white/30">
                  No open gaps
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
