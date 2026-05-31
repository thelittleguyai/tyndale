'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  adminGetCase,
  adminGetProvenance,
  adminGetVerdicts,
  type AdminCaseDetail,
  type AdminProvenance,
  type AdminVerdict,
} from '@/lib/api-client';
import { track } from '@/lib/analytics';
import { ProvenanceTree } from './provenance-tree';
import { VerdictForm } from './verdict-form';
import { ChatTranscript } from './chat-transcript';

type Tab = 'provenance' | 'response' | 'chat' | 'findings';
const TABS: { key: Tab; label: string }[] = [
  { key: 'provenance', label: 'Provenance' },
  { key: 'response', label: 'Response' },
  { key: 'chat', label: 'Chat' },
  { key: 'findings', label: 'Findings' },
];

export function CaseDetail({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<AdminCaseDetail | null>(null);
  const [prov, setProv] = useState<AdminProvenance | null>(null);
  const [verdicts, setVerdicts] = useState<AdminVerdict[]>([]);
  const [tab, setTab] = useState<Tab>('provenance');
  const [error, setError] = useState<string | null>(null);

  const loadVerdicts = useCallback(() => {
    adminGetVerdicts(caseId)
      .then((r) => setVerdicts(r.verdicts))
      .catch(() => undefined);
  }, [caseId]);

  useEffect(() => {
    let alive = true;
    Promise.all([adminGetCase(caseId), adminGetProvenance(caseId)])
      .then(([d, p]) => {
        if (!alive) return;
        setDetail(d);
        setProv(p);
        track('case_viewed', { case_id: caseId });
      })
      .catch((e) => alive && setError(e?.message ?? String(e)));
    loadVerdicts();
    return () => {
      alive = false;
    };
  }, [caseId, loadVerdicts]);

  if (error) return <p className="text-sm text-rose">{error}</p>;
  if (!detail || !prov) return <p className="text-sm text-white/40">Loading case…</p>;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
      {/* LEFT — forensic detail */}
      <div>
        <div className="mb-4">
          <p className="text-xs uppercase tracking-widest text-white/40">Case</p>
          <p className="font-mono text-sm text-white/70">{detail.case_file_id}</p>
          <p className="mt-1 text-sm text-white/60">
            {detail.user.email ?? '—'} · {detail.status} · intake {detail.intake_status ?? '—'}
          </p>
        </div>

        <div className="mb-4 flex gap-1 border-b border-white/10">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-2 text-sm ${
                tab === t.key
                  ? 'border-b-2 border-sage font-semibold text-white'
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'provenance' ? <ProvenanceTree prov={prov} /> : null}

        {tab === 'response' ? (
          <div className="rounded-xl border border-white/10 bg-navy-soft p-4 text-sm text-white/70">
            <p className="mb-2 text-xs uppercase tracking-wide text-white/40">
              Latest composed response
            </p>
            {detail.last_audit_result ? (
              <pre className="overflow-auto text-[12px] text-white/70">
                {JSON.stringify(detail.last_audit_result, null, 2)}
              </pre>
            ) : (
              <p>
                No separately-stored composed response yet — the three-number audit is available
                via the runtime <span className="font-mono">/v1/audit/{detail.case_file_id}</span>{' '}
                endpoint. See the Findings tab for what was written.
              </p>
            )}
          </div>
        ) : null}

        {tab === 'chat' ? <ChatTranscript messages={detail.conversation_history} /> : null}

        {tab === 'findings' ? (
          <div className="space-y-2">
            {detail.findings.length === 0 ? (
              <p className="text-sm text-white/40">No findings written for this case.</p>
            ) : (
              detail.findings.map((f) => (
                <div key={f.finding_id} className="rounded-xl border border-white/10 bg-navy-soft p-4">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="rounded-md bg-white/10 px-2 py-0.5 text-[11px] text-white/70">
                      {f.finding_type}
                    </span>
                    <span className="text-sm font-semibold text-white/85">{f.category}</span>
                    <span className="ml-auto text-[11px] text-white/40">Tier {f.voice_tier}</span>
                  </div>
                  <pre className="overflow-auto text-[11px] leading-4 text-white/55">
                    {JSON.stringify({ facts: f.facts, legal_claim: f.legal_claim, recommendation: f.recommendation }, null, 2)}
                  </pre>
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>

      {/* RIGHT — verdict capture (sticky) */}
      <div className="lg:sticky lg:top-6 lg:self-start">
        <VerdictForm caseId={caseId} findings={detail.findings} onSubmitted={loadVerdicts} />
        <div className="mt-4">
          <p className="mb-2 text-xs uppercase tracking-widest text-white/40">Recent verdicts</p>
          {verdicts.length === 0 ? (
            <p className="text-sm text-white/40">None yet.</p>
          ) : (
            <div className="space-y-2">
              {verdicts.map((v) => (
                <div key={v.verdict_id} className="rounded-lg border border-white/10 bg-navy-soft p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white/80">{v.verdict}</span>
                    <span className="text-[11px] text-white/40">
                      {v.captured_at ? new Date(v.captured_at).toLocaleString() : ''}
                    </span>
                  </div>
                  {v.notes ? <p className="mt-1 text-white/55">{v.notes}</p> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
