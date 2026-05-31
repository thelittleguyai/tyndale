'use client';

import { useState } from 'react';

import type { AdminProvenance } from '@/lib/api-client';

type Leaf = { label: string; tone: 'grounded' | 'inferred' | 'ungrounded'; detail: unknown };
type Group = { key: string; title: string; leaves: Leaf[] };

const TONE_DOT: Record<Leaf['tone'], string> = {
  grounded: 'bg-sage', // has a source
  inferred: 'bg-amber', // reasonable but not directly sourced
  ungrounded: 'bg-rose', // would have been blocked by the Stop-hook citation layer
};

function buildGroups(p: AdminProvenance): Group[] {
  return [
    {
      key: 'documents',
      title: 'Documents (uploads + OCR)',
      leaves: p.documents.map((d, i) => ({
        label: String((d as { filename?: string }).filename ?? `document ${i + 1}`),
        tone: 'grounded',
        detail: d,
      })),
    },
    {
      key: 'skills_loaded',
      title: 'Skills loaded',
      leaves: p.skills_loaded.map((s) => ({ label: s, tone: 'grounded', detail: s })),
    },
    {
      key: 'tools_called',
      title: 'Tools called',
      leaves: p.tools_called.map((t, i) => ({
        label: String(
          (t as { tools_invoked?: string[] }).tools_invoked?.join(', ') ?? `tool ${i + 1}`,
        ),
        tone: 'grounded',
        detail: t,
      })),
    },
    {
      key: 'qdrant_chunks_retrieved',
      title: 'Qdrant chunks retrieved',
      leaves: p.qdrant_chunks_retrieved.map((c, i) => ({
        label: String((c as { policy_id?: string; chunk_id?: string }).policy_id ?? (c as { chunk_id?: string }).chunk_id ?? `chunk ${i + 1}`),
        tone: 'grounded',
        detail: c,
      })),
    },
    {
      key: 'subagent_calls',
      title: 'Subagent calls',
      leaves: p.subagent_calls.map((s, i) => ({
        label: String((s as { actor?: string }).actor ?? `subagent ${i + 1}`),
        tone: 'grounded',
        detail: s,
      })),
    },
    {
      key: 'findings_written',
      title: 'Findings written',
      leaves: p.findings_written.map((f) => ({
        label: `${f.category} (${f.finding_type})`,
        // A Tier-B finding without a legal_claim citation is "inferred"; grounded otherwise.
        tone: f.voice_tier === 'B' && !f.legal_claim ? 'inferred' : 'grounded',
        detail: f,
      })),
    },
    {
      key: 'llm_calls',
      title: 'LLM calls',
      leaves: p.llm_calls.map((m, i) => ({
        label: String((m as { model?: string }).model ?? `model call ${i + 1}`),
        tone: 'grounded',
        detail: m,
      })),
    },
  ];
}

export function ProvenanceTree({ prov }: { prov: AdminProvenance }) {
  const groups = buildGroups(prov);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [leafOpen, setLeafOpen] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      {groups.map((g) => (
        <div key={g.key} className="rounded-xl border border-white/10 bg-navy-soft">
          <button
            onClick={() => setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))}
            className="flex w-full items-center justify-between px-4 py-2.5 text-left"
          >
            <span className="text-sm font-semibold text-white/85">{g.title}</span>
            <span className="text-xs text-white/40">{g.leaves.length}</span>
          </button>
          {open[g.key] ? (
            <div className="border-t border-white/5 px-4 py-2">
              {g.leaves.length === 0 ? (
                <p className="py-1 text-xs text-white/30">none</p>
              ) : (
                g.leaves.map((leaf, i) => {
                  const id = `${g.key}-${i}`;
                  return (
                    <div key={id} className="py-1">
                      <button
                        onClick={() => setLeafOpen((cur) => (cur === id ? null : id))}
                        className="flex w-full items-center gap-2 text-left"
                      >
                        <span className={`h-2 w-2 rounded-full ${TONE_DOT[leaf.tone]}`} />
                        <span className="flex-1 truncate text-sm text-white/75">{leaf.label}</span>
                      </button>
                      {leafOpen === id ? (
                        <pre className="mt-1 max-h-64 overflow-auto rounded-lg bg-black/30 p-3 text-[11px] leading-4 text-white/60">
                          {JSON.stringify(leaf.detail, null, 2)}
                        </pre>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          ) : null}
        </div>
      ))}
      <div className="flex gap-4 px-1 pt-1 text-[11px] text-white/40">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-sage" /> grounded
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-amber" /> inferred
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-rose" /> ungrounded
        </span>
      </div>
    </div>
  );
}
