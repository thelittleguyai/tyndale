'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import type { AdminUserSummary } from '@tyndale/shared';

import { adminListUsers } from '@/lib/api-client';

const STATUSES = ['all', 'active', 'blocked', 'soft_deleted'];
const PAGE = 50;

function statusPill(s: string): string {
  if (s === 'active') return 'bg-sage/20 text-sage';
  if (s === 'blocked') return 'bg-amber/20 text-amber';
  return 'bg-rose/20 text-rose';
}

export function UserList() {
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const params: Record<string, string | number> = { limit: PAGE, offset: page * PAGE };
    if (q.trim()) params.q = q.trim();
    if (status !== 'all') params.status = status;
    adminListUsers(params)
      .then((r) => {
        if (alive) {
          setUsers(r.users);
          setError(null);
        }
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [q, status, page]);

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <input
          value={q}
          onChange={(e) => {
            setPage(0);
            setQ(e.target.value);
          }}
          placeholder="Search email or id…"
          className="flex-1 rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
        />
        <select
          value={status}
          onChange={(e) => {
            setPage(0);
            setStatus(e.target.value);
          }}
          className="rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
      {loading ? (
        <p className="text-sm text-white/40">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
              <tr>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Cases</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-t border-white/5 hover:bg-white/5">
                  <td className="px-4 py-2">
                    <Link href={`/users/${u.user_id}`} className="text-sage hover:underline">
                      {u.email}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-white/70">{u.user_type}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-md px-2 py-0.5 text-xs ${statusPill(u.status)}`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-white/60">{u.case_file_count}</td>
                  <td className="px-4 py-2 text-white/40">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
              {!users.length ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-white/30">
                    No users
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex items-center gap-3 text-sm">
        <button
          disabled={page === 0}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          className="rounded-lg border border-white/15 px-3 py-1 disabled:opacity-30"
        >
          Prev
        </button>
        <span className="text-white/40">Page {page + 1}</span>
        <button
          disabled={users.length < PAGE}
          onClick={() => setPage((p) => p + 1)}
          className="rounded-lg border border-white/15 px-3 py-1 disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  );
}
