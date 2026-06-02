'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

import type { QdrantChunkResult } from '@tyndale/shared';

import { AdminShell } from '@/components/admin-shell';
import { adminSearchCollection } from '@/lib/api-client';

function preview(p: Record<string, unknown>): string {
  const t = (p.chunk_text ?? p.descriptor ?? p.narrative_text ?? p.title ?? '') as unknown;
  return String(t).slice(0, 90);
}

export default function CollectionPage() {
  const params = useParams<{ collection: string }>();
  const collection = String(params.collection);
  const [query, setQuery] = useState('');
  const [includeStaging, setIncludeStaging] = useState(false);
  const [results, setResults] = useState<QdrantChunkResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await adminSearchCollection(collection, {
        query: query.trim(),
        include_staging: includeStaging,
        limit: 20,
      });
      setResults(r.results);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminShell>
      <div className="mb-4 flex items-center gap-3">
        <Link href="/knowledge" className="text-sm text-white/40 hover:text-white/70">
          ← Knowledge
        </Link>
        <h1 className="text-xl font-bold">{collection}</h1>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
          placeholder="Semantic search…"
          className="flex-1 rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
        />
        <label className="flex items-center gap-2 text-xs text-white/60">
          <input
            type="checkbox"
            checked={includeStaging}
            onChange={(e) => setIncludeStaging(e.target.checked)}
          />
          staging
        </label>
        <button
          onClick={search}
          disabled={busy}
          className="rounded-lg bg-sage px-4 py-2 text-sm font-bold text-ink disabled:opacity-40"
        >
          {busy ? '…' : 'Search'}
        </button>
      </div>

      {error ? <p className="mb-3 text-sm text-rose">{error}</p> : null}
      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-white/45">
            <tr>
              <th className="px-4 py-2">Chunk</th>
              <th className="px-4 py-2">Partition</th>
              <th className="px-4 py-2">Score</th>
              <th className="px-4 py-2">Preview</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.id} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-4 py-2">
                  <Link
                    href={`/knowledge/${collection}/${encodeURIComponent(r.id)}`}
                    className="text-sage hover:underline"
                  >
                    {r.id.slice(0, 16)}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`rounded-md px-2 py-0.5 text-xs ${
                      r.partition_status === 'staging'
                        ? 'bg-amber/20 text-amber'
                        : 'bg-sage/20 text-sage'
                    }`}
                  >
                    {r.partition_status}
                  </span>
                </td>
                <td className="px-4 py-2 text-white/50">{r.score.toFixed(3)}</td>
                <td className="px-4 py-2 text-white/60">{preview(r.payload)}</td>
              </tr>
            ))}
            {!results.length ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-white/30">
                  No results yet
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
