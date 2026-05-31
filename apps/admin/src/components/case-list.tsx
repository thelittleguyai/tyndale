'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { adminListCases, type AdminCaseSummary } from '@/lib/api-client';

export function CaseList({ limit }: { limit?: number }) {
  const [cases, setCases] = useState<AdminCaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    adminListCases(limit ? { limit } : {})
      .then((r) => alive && setCases(r.cases))
      .catch((e) => alive && setError(e?.message ?? String(e)))
      .finally(() => alive && setLoading(false));
  }, [limit]);

  if (loading) return <p className="text-sm text-white/40">Loading cases…</p>;
  if (error) return <p className="text-sm text-rose">{error}</p>;
  if (!cases.length) return <p className="text-sm text-white/40">No cases yet.</p>;

  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
          <tr>
            <th className="px-4 py-2">User</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Summary</th>
            <th className="px-4 py-2">Verdict</th>
            <th className="px-4 py-2">Updated</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.case_file_id} className="border-t border-white/5 hover:bg-white/5">
              <td className="px-4 py-2">
                <Link href={`/cases/${c.case_file_id}`} className="text-sage hover:underline">
                  {c.user_email ?? c.case_file_id.slice(0, 8)}
                </Link>
              </td>
              <td className="px-4 py-2 text-white/70">{c.status}</td>
              <td className="px-4 py-2 text-white/60">{c.summary}</td>
              <td className="px-4 py-2">
                <span
                  className={`rounded-md px-2 py-0.5 text-xs ${
                    c.verdict_status === 'captured'
                      ? 'bg-sage/20 text-sage'
                      : 'bg-amber/20 text-amber'
                  }`}
                >
                  {c.verdict_status}
                </span>
              </td>
              <td className="px-4 py-2 text-white/40">
                {c.last_activity_at ? new Date(c.last_activity_at).toLocaleDateString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
