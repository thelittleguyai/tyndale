'use client';

import { useCallback, useEffect, useState } from 'react';

import { adminReviewWorkspace, type ReviewFinding, type ReviewWorkspace as Workspace } from '@/lib/api-client';
import { BandPill, Card, FlagChips, Phase2Placeholder, SectionLabel, StatePill, humanize, money, shortId, when } from './review-ui';
import { VerdictPanel } from './verdict-panel';

// The case workspace (doc 39 §2 + mockup human_review_case.svg): left = source documents,
// extraction, user journey; center = four tabs; right = the verdict panel. Every field is
// read from existing data — a missing value renders "not recorded", never a guess.

type Tab = 'analysis' | 'conversation' | 'results' | 'provenance';
const TABS: { key: Tab; label: string }[] = [
  { key: 'analysis', label: 'Analysis' },
  { key: 'conversation', label: 'Conversation' },
  { key: 'results', label: 'Results & journey' },
  { key: 'provenance', label: 'Data & provenance' },
];

function NotRecorded() {
  return <span className="italic text-white/30">not recorded</span>;
}

function Json({ v }: { v: unknown }) {
  return <pre className="overflow-auto text-[11px] leading-4 text-white/60">{JSON.stringify(v, null, 2)}</pre>;
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : typeof v === 'number' ? String(v) : null;
}

function ThreeNumbers({ tn }: { tn: Record<string, unknown> | null }) {
  const n = (k: string) => (typeof tn?.[k] === 'number' ? (tn[k] as number) : null);
  const cell = (label: string, value: number | null, sub?: string | null) => (
    <div key={label} className="flex-1 rounded-lg bg-white/5 p-2">
      <p className="text-[10px] uppercase tracking-widest text-white/40">{label}</p>
      <p className="text-lg font-bold text-white">{value === null ? <NotRecorded /> : money(value)}</p>
      {sub ? <p className="text-[10px] text-white/40">{sub}</p> : null}
    </div>
  );
  const low = n('tyndale_computed_low');
  const high = n('tyndale_computed_high');
  return (
    <div className="flex flex-wrap gap-2">
      {cell('Provider billed', n('provider_billed'))}
      {cell('EOB says you owe', n('eob_member_responsibility'))}
      {cell(
        'Tyndale computed',
        n('tyndale_computed'),
        low !== null && high !== null ? `range ${money(low)} – ${money(high)} · ${str(tn?.computed_source) ?? ''}` : str(tn?.computed_source),
      )}
    </div>
  );
}

function WhyExpander({ f }: { f: ReviewFinding }) {
  return (
    <details className="mt-2 rounded-lg bg-white/5 p-2 text-xs">
      <summary className="cursor-pointer text-white/60">Why this finding</summary>
      <dl className="mt-2 space-y-1">
        {f.why.map((line) => (
          <div key={line.key} className="grid grid-cols-[140px_1fr] gap-2">
            <dt className="text-white/40">{line.label}</dt>
            <dd className="text-white/80">
              {line.value === null ? (
                <NotRecorded />
              ) : typeof line.value === 'string' ? (
                line.value
              ) : (
                <span className="font-mono">
                  {Object.entries(line.value)
                    .map(([k, v]) => `${humanize(k)}: ${money(v)}`)
                    .join(' · ')}
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function FindingCard({ f, internalNotes }: { f: ReviewFinding; internalNotes: string[] }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">{humanize(f.category)}</p>
          <p className="text-[11px] text-white/50">
            {humanize(f.finding_type)} · responsible: {humanize(f.responsible_party)} · tier {f.voice_tier} · {f.status}
          </p>
        </div>
        <p className="text-base font-bold text-white">{f.amount_usd === null ? <NotRecorded /> : money(f.amount_usd)}</p>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px]">
        <span className="text-white/40">BASIS</span>
        {f.basis_codes.length ? (
          f.basis_codes.map((c) => (
            <span key={c} className="rounded bg-citation-soft px-1.5 py-0.5 font-mono text-citation-deep">
              {c}
            </span>
          ))
        ) : (
          <NotRecorded />
        )}
        <span className="ml-3 text-white/40">CONFIDENCE</span>
        {f.confidence === null ? <NotRecorded /> : <span className="text-white/80">{String(f.confidence)}</span>}
      </div>
      <div className="mt-1 text-[11px]">
        <span className="text-white/40">CITATIONS </span>
        {f.citations.length ? (
          f.citations.map((c) => (
            <span key={c.src_id} className="mr-2 font-mono text-citation-soft">
              {c.marker}
            </span>
          ))
        ) : (
          <NotRecorded />
        )}
      </div>
      <div className="mt-2 rounded-lg border border-amber/40 p-2 text-[11px]">
        <p className="font-semibold uppercase tracking-widest text-amber">Analyst notes · internal — never shown to users</p>
        {internalNotes.length ? (
          internalNotes.map((n, i) => (
            <p key={i} className="mt-1 text-white/70">
              {n}
            </p>
          ))
        ) : (
          <p className="mt-1 text-white/40">none yet</p>
        )}
      </div>
      <WhyExpander f={f} />
    </Card>
  );
}

function LeftPane({ left, caseRow }: { left: Workspace['left']; caseRow: Workspace['case'] }) {
  const docs = [...left.documents.map((d) => ({ ...d, kind: 'document' })), ...left.eobs.map((d) => ({ ...d, kind: 'eob' }))];
  return (
    <div className="space-y-4">
      <div>
        <SectionLabel>Source documents</SectionLabel>
        {docs.length ? (
          <div className="space-y-2">
            {docs.map((d) => (
              <Card key={`${d.kind}-${d.index}`} className="text-xs">
                <p className="font-semibold text-white/80">
                  {humanize(d.document_type ?? d.kind)}
                  <span className="text-white/40"> · {d.filename ?? 'unnamed'}</span>
                </p>
                <p className="text-white/40">
                  {d.page_count ? `${d.page_count} pages · ` : ''}
                  {d.text_chars ? `${d.text_chars.toLocaleString()} chars extracted` : 'no text extracted'}
                  {d.extraction_status ? ` · ${humanize(d.extraction_status)}` : ''}
                </p>
                {d.claim_number || d.account_number ? (
                  <p className="font-mono text-white/50">
                    {d.claim_number ? `claim ${d.claim_number}` : ''}
                    {d.claim_number && d.account_number ? ' · ' : ''}
                    {d.account_number ? `acct ${d.account_number}` : ''}
                  </p>
                ) : null}
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-xs text-white/40">No documents on this case.</p>
        )}
      </div>
      <div>
        <SectionLabel>Extraction</SectionLabel>
        {left.extraction.line_items.length ? (
          <table className="w-full text-[11px]">
            <thead className="text-white/40">
              <tr>
                <th className="py-1 text-left">Code</th>
                <th className="py-1 text-left">Description</th>
                <th className="py-1 text-right">Billed</th>
              </tr>
            </thead>
            <tbody>
              {left.extraction.line_items.map((li, i) => (
                <tr key={i} className="border-t border-white/10 text-white/70">
                  <td className="py-1 font-mono">{str(li.code) ?? '—'}</td>
                  <td className="py-1">{str(li.plain_language_translation) ?? str(li.raw_description) ?? '—'}</td>
                  <td className="py-1 text-right">{typeof li.billed_amount === 'number' ? money(li.billed_amount) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs text-white/40">No line items extracted.</p>
        )}
        {Object.keys(left.extraction.coverage).length ? (
          <div className="mt-2 text-[11px] text-white/60">
            <p className="text-white/40">Coverage terms</p>
            {Object.entries(left.extraction.coverage).map(([k, v]) => (
              <p key={k}>
                {humanize(k)}: <span className="font-mono">{v === null || v === undefined ? '—' : String(v)}</span>
              </p>
            ))}
          </div>
        ) : null}
      </div>
      <div>
        <SectionLabel>User journey</SectionLabel>
        <ul className="space-y-1 text-[11px] text-white/60">
          <li>
            <span className="text-white/40">{when(caseRow.created_at)}</span> · case created · intake {humanize(caseRow.intake_status)}
          </li>
          {left.journey.map((j, i) => (
            <li key={i}>
              <span className="text-white/40">{when(j.at)}</span> · {humanize(j.event)}
              {Object.keys(j.properties).length ? (
                <span className="text-white/40">
                  {' '}
                  ({Object.entries(j.properties)
                    .map(([k, v]) => `${k}=${String(v)}`)
                    .join(', ')})
                </span>
              ) : null}
            </li>
          ))}
          <li>
            <span className="text-white/40">{when(caseRow.updated_at)}</span> · now {humanize(caseRow.status)}
            {caseRow.incomplete_reason ? ` (${humanize(caseRow.incomplete_reason)})` : ''}
          </li>
        </ul>
      </div>
    </div>
  );
}

function ConversationTab({ messages }: { messages: Record<string, unknown>[] }) {
  if (!messages.length) {
    return <p className="text-sm text-white/40">No conversation on this case yet.</p>;
  }
  return (
    <div className="space-y-2">
      {messages.map((m, i) => {
        const role = str(m.role) ?? 'system';
        const kind = str(m.kind);
        const content = str(m.content);
        return (
          <div key={str(m.message_id) ?? i} className={`rounded-xl px-3 py-2 text-sm ${role === 'user' ? 'bg-white/5 text-white/80' : 'bg-teal-deep text-white'}`}>
            <p className="mb-0.5 text-[11px] uppercase tracking-wide text-white/40">
              {role}
              {kind && kind !== 'message' ? ` · ${humanize(kind)}` : ''}
              {' · '}
              {when(str(m.created_at))}
              {str(m.status) && m.status !== 'complete' ? ` · ${String(m.status)}` : ''}
            </p>
            {content ? <p className="whitespace-pre-wrap leading-5">{content}</p> : <Json v={m.payload ?? {}} />}
          </div>
        );
      })}
    </div>
  );
}

function ResultsTab({ r, documentsNeeded }: { r: Workspace['tabs']['results']; documentsNeeded: Workspace['tabs']['analysis']['documents_needed'] }) {
  const ids = Object.entries(r.identifiers).filter(([, v]) => v);
  return (
    <div className="space-y-4">
      <div>
        <SectionLabel>Gameplan · call scripts</SectionLabel>
        {r.gameplan.length ? (
          <div className="space-y-2">
            {r.gameplan.map((g, i) => {
              const script = (g.script ?? {}) as Record<string, unknown>;
              return (
                <Card key={i} className="text-xs">
                  <p className="text-sm font-semibold text-white">
                    {String(g.index ?? i + 1)}. {str(g.title) ?? '—'}
                    <span className="text-white/40">
                      {' '}
                      · call {str(g.party_label) ?? str(g.party) ?? '—'} · {typeof g.dollar_impact === 'number' ? money(g.dollar_impact) : 'no estimate'}
                    </span>
                  </p>
                  <p className="text-white/40">
                    {str(g.reference_kind) ? `${humanize(str(g.reference_kind))} ${str(g.reference_number) ?? ''}` : 'no reference number'}
                    {str(g.phone) ? ` · ${str(g.phone)}` : ' · no phone on document'}
                  </p>
                  <dl className="mt-1 space-y-0.5 text-white/70">
                    {(['when_they_pick_up', 'the_problem', 'the_ask', 'get_it_in_writing'] as const).map((k) => (
                      <div key={k}>
                        <dt className="inline text-white/40">{humanize(k)}: </dt>
                        <dd className="inline">{str(script[k]) ?? '—'}</dd>
                      </div>
                    ))}
                  </dl>
                </Card>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-white/40">No actionable findings — no calls to script.</p>
        )}
      </div>
      <div>
        <SectionLabel>Identifiers</SectionLabel>
        {ids.length ? (
          <p className="font-mono text-xs text-white/70">{ids.map(([k, v]) => `${humanize(k)} ${v}`).join(' · ')}</p>
        ) : (
          <p className="text-xs text-white/40">No claim / account / phone identifiers on the documents.</p>
        )}
      </div>
      <div>
        <SectionLabel>Tier renderings</SectionLabel>
        {r.tiers.length ? (
          <div className="space-y-2">
            {r.tiers.map((t) => (
              <Card key={t.finding_id} className="text-xs">
                <p className="font-mono text-white/40">
                  {shortId(t.finding_id)} · voice tier {t.voice_tier}
                </p>
                <p className="mt-1 text-white/40">A · facts</p>
                <Json v={t.tier_a_facts} />
                <p className="mt-1 text-white/40">B · claim</p>
                {t.tier_b_claim ? <Json v={t.tier_b_claim} /> : <NotRecorded />}
                <p className="mt-1 text-white/40">C · recommendation</p>
                {t.tier_c_recommendation ? <Json v={t.tier_c_recommendation} /> : <NotRecorded />}
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-xs text-white/40">No findings.</p>
        )}
      </div>
      {documentsNeeded.length ? (
        <div>
          <SectionLabel>Documents still needed</SectionLabel>
          <ul className="text-xs text-white/70">
            {documentsNeeded.map((d) => (
              <li key={d.key}>
                {d.have ? '☑' : '☐'} {d.label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div>
        <SectionLabel>Deadlines</SectionLabel>
        {r.deadlines.length ? <Json v={r.deadlines} /> : <p className="text-xs text-white/40">None.</p>}
      </div>
      <div>
        <SectionLabel>Outcomes reported by the user</SectionLabel>
        {r.outcomes.length ? <Json v={r.outcomes} /> : <p className="text-xs text-white/40">None reported yet.</p>}
      </div>
    </div>
  );
}

function ProvenanceTab({ p }: { p: Workspace['tabs']['provenance'] }) {
  return (
    <div className="space-y-4">
      {p.tripwires.length ? (
        <Card className="border-rose/40">
          <SectionLabel>Tripwires fired</SectionLabel>
          <Json v={p.tripwires} />
        </Card>
      ) : null}
      <div>
        <SectionLabel>Skills loaded</SectionLabel>
        {p.skills_loaded.length ? (
          <p className="text-xs text-white/70">{p.skills_loaded.join(' · ')}</p>
        ) : (
          <p className="text-xs text-white/40">None recorded.</p>
        )}
      </div>
      <div>
        <SectionLabel>Tools called · {p.tools_called.length}</SectionLabel>
        {p.tools_called.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.tools_called.map((t, i) => (
              <li key={i}>
                <span className="font-mono">{(t.tools_invoked ?? []).join(', ') || '—'}</span>
                <span className="text-white/40">
                  {' '}
                  · {t.outcome ?? '—'} · {when(t.timestamp)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-white/40">None recorded.</p>
        )}
      </div>
      <div>
        <SectionLabel>Retrieval · {p.qdrant_chunks_retrieved.length} chunks</SectionLabel>
        {p.qdrant_chunks_retrieved.length ? <Json v={p.qdrant_chunks_retrieved.slice(0, 20)} /> : <p className="text-xs text-white/40">No chunks recorded.</p>}
      </div>
      <div>
        <SectionLabel>Subagent calls · {p.subagent_calls.length} · Model calls · {p.llm_calls.length}</SectionLabel>
        {p.subagent_calls.length || p.llm_calls.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.subagent_calls.map((s, i) => (
              <li key={`s${i}`}>
                {s.actor ?? 'subagent'} · {s.outcome ?? '—'} · {when(s.timestamp)}
              </li>
            ))}
            {p.llm_calls.map((l, i) => (
              <li key={`l${i}`}>
                {l.model ?? 'model'} · {l.outcome ?? '—'} · {when(l.timestamp)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-white/40">None recorded.</p>
        )}
      </div>
      <div>
        <SectionLabel>Findings written · {p.findings_written.length} · research log · {p.research_log.length} entries</SectionLabel>
        {p.research_log.length ? <Json v={p.research_log} /> : null}
      </div>
      <div>
        <SectionLabel>Phase 2</SectionLabel>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <Phase2Placeholder title="API pulls" label={p.api_pulls.label} />
          <Phase2Placeholder title="Live lookups" label={p.live_lookups.label} />
          <Phase2Placeholder title="Missing data" label={p.missing_data.label} />
          <Phase2Placeholder title="Retrieval misses" label={p.retrieval_misses.label} />
        </div>
      </div>
    </div>
  );
}

export function ReviewWorkspace({ caseId }: { caseId: string }) {
  const [ws, setWs] = useState<Workspace | null>(null);
  const [tab, setTab] = useState<Tab>('analysis');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    adminReviewWorkspace(caseId)
      .then((w) => {
        setWs(w);
        setError(null);
      })
      .catch((e) => setError(e?.message ?? String(e)));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <p className="text-sm text-rose">{error}</p>;
  if (!ws) return <p className="text-sm text-white/40">Loading workspace…</p>;

  const a = ws.tabs.analysis;
  const notesFor = (fid: string) =>
    ws.verdicts.filter((v) => v.notes && v.target_findings?.includes(fid)).map((v) => v.notes as string);
  const findingLabels = a.findings.map((f) => ({
    finding_id: f.finding_id,
    label: `${humanize(f.category)}${f.amount_usd !== null ? ` · ${money(f.amount_usd)}` : ''}`,
  }));

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-white/40">Review · case</p>
          <p className="font-mono text-sm text-white/70">
            {shortId(ws.case.case_file_id)} · {ws.case.user_masked ?? '—'}
            {ws.review ? ` · run #${ws.review.run_seq}` : ''}
          </p>
          <p className="mt-1 text-sm text-white/60">
            {humanize(ws.case.status)}
            {ws.case.incomplete_reason ? ` · ${humanize(ws.case.incomplete_reason)}` : ''}
            {a.disclosure ? ` · disclosure tier ${a.disclosure.tier} (${a.disclosure.label})` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {ws.review ? (
            <>
              <BandPill band={ws.review.confidence_band} />
              <StatePill state={ws.review.state} />
              <FlagChips flags={ws.review.flags} sampled={ws.review.sampled} />
            </>
          ) : null}
          {ws.review_chain.length > 1 ? (
            <span className="text-[11px] text-white/40">
              runs: {ws.review_chain.map((r) => `#${r.run_seq} ${humanize(r.state)}`).join(' → ')}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
        <LeftPane left={ws.left} caseRow={ws.case} />

        <div>
          <div className="mb-4 flex gap-1 border-b border-white/10">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 py-2 text-sm ${tab === t.key ? 'border-b-2 border-sage font-semibold text-white' : 'text-white/50 hover:text-white/80'}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'analysis' ? (
            <div className="space-y-4">
              <ThreeNumbers tn={a.three_numbers} />
              {a.summary ? <p className="text-sm leading-6 text-white/80">{a.summary}</p> : <p className="text-xs text-white/40">No summary composed.</p>}
              {a.findings.length ? (
                <div className="space-y-3">
                  {a.findings.map((f) => (
                    <FindingCard key={f.finding_id} f={f} internalNotes={notesFor(f.finding_id)} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-white/40">No findings on this run.</p>
              )}
            </div>
          ) : null}
          {tab === 'conversation' ? <ConversationTab messages={ws.tabs.conversation} /> : null}
          {tab === 'results' ? <ResultsTab r={ws.tabs.results} documentsNeeded={a.documents_needed} /> : null}
          {tab === 'provenance' ? <ProvenanceTab p={ws.tabs.provenance} /> : null}
        </div>

        <VerdictPanel caseId={caseId} review={ws.review} findings={findingLabels} verdicts={ws.verdicts} onSubmitted={load} />
      </div>
    </div>
  );
}
