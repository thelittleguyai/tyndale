'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import type { QdrantCollectionInfo } from '@tyndale/shared';

import { AdminShell } from '@/components/admin-shell';
import { adminListCollections } from '@/lib/api-client';

export default function KnowledgePage() {
  const [cols, setCols] = useState<QdrantCollectionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminListCollections()
      .then((r) => setCols(r.collections))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Knowledge base</h1>
      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
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
    </AdminShell>
  );
}
