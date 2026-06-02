'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import { adminGetChunk, adminPromoteChunk } from '@/lib/api-client';

export default function ChunkPage() {
  const params = useParams<{ collection: string; chunkId: string }>();
  const collection = String(params.collection);
  const chunkId = String(params.chunkId);
  const [chunk, setChunk] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    adminGetChunk(collection, chunkId)
      .then(setChunk)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [collection, chunkId]);

  useEffect(() => load(), [load]);

  const promote = async () => {
    setBusy(true);
    setError(null);
    try {
      await adminPromoteChunk(collection, chunkId);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (error && !chunk)
    return (
      <AdminShell>
        <p className="text-sm text-rose">{error}</p>
      </AdminShell>
    );
  if (!chunk)
    return (
      <AdminShell>
        <p className="text-sm text-white/40">Loading…</p>
      </AdminShell>
    );

  const partition = String(chunk.partition_status ?? 'live');
  const payload = (chunk.payload ?? {}) as Record<string, unknown>;
  const provenance = (chunk.ingestion_provenance ?? {}) as Record<string, unknown>;

  return (
    <AdminShell>
      <div className="mb-4 flex items-center gap-3">
        <Link href={`/knowledge/${collection}`} className="text-sm text-white/40 hover:text-white/70">
          ← {collection}
        </Link>
        <h1 className="text-lg font-bold">{chunkId.slice(0, 28)}</h1>
        <span
          className={`rounded-md px-2 py-0.5 text-xs ${
            partition === 'staging' ? 'bg-amber/20 text-amber' : 'bg-sage/20 text-sage'
          }`}
        >
          {partition}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
            <h3 className="mb-2 text-sm font-semibold text-white/85">Payload</h3>
            <pre className="max-h-[30rem] overflow-auto whitespace-pre-wrap break-words text-xs text-white/70">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
            <h3 className="mb-2 text-sm font-semibold text-white/85">Ingestion provenance</h3>
            <pre className="overflow-auto whitespace-pre-wrap break-words text-xs text-white/60">
              {JSON.stringify(provenance, null, 2)}
            </pre>
          </div>
          {error ? <p className="text-xs text-rose">{error}</p> : null}
          <button
            disabled={busy || partition !== 'staging'}
            onClick={promote}
            className="w-full rounded-lg bg-sage px-3 py-2 text-sm font-bold text-ink disabled:opacity-40"
          >
            {partition === 'staging' ? (busy ? '…' : 'Promote to live') : 'Already live'}
          </button>
        </div>
      </div>
    </AdminShell>
  );
}
