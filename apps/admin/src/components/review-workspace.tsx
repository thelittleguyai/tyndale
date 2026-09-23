'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  adminReviewClaim,
  adminReviewWorkspace,
  type ReviewCitation,
  type ReviewDocumentCard,
  type ReviewFinding,
  type ReviewVerdictRecord,
  type ReviewWorkspace as Workspace,
} from '@/lib/api-client';
import { EMPTY_DRAFT, toggleTarget, type VerdictDraft } from '@/lib/verdict-draft';
import {
  BandPill,
  Card,
  DocumentSetChip,
  FlagChips,
  IntakeModeChip,
  KeyValues,
  NotRecorded,
  Phase2Placeholder,
  RawToggle,
  SectionLabel,
  Sheet,
  StatePill,
  caseTitle,
  humanize,
  money,
  serviceDate,
  shortId,
  when,
} from './review-ui';
import { Markdown } from './markdown';
import { DocumentViewer } from './document-viewer';
import { VerdictPanel, type ClaimView } from './verdict-panel';

// The case workspace (doc 39 §2 + mockup human_review_case.svg): left = source documents,
// extraction, user journey; center = four tabs; right = the verdict panel. Every field is
// read from existing data — a missing value renders "not recorded", never a guess — and nothing
// is printed as a raw JSON dump by default (this is a PHI console; "show raw" is collapsed).

type Tab = 'analysis' | 'conversation' | 'results' | 'provenance';
const TABS: { key: Tab; label: string }[] = [
  { key: 'analysis', label: 'Analysis' },
  { key: 'conversation', label: 'Conversation' },
  { key: 'results', label: 'Results & journey' },
  { key: 'provenance', label: 'Data & provenance' },
];

type Dict = Record<string, unknown>;

function str(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : typeof v === 'number' ? String(v) : null;
}

function asDict(v: unknown): Dict | null {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as Dict) : null;
}

function ThreeNumbers({ tn }: { tn: Dict | null }) {
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
  // joined from the parts that EXIST — a missing computed_source used to leave a dangling " · "
  const computedSub =
    [low !== null && high !== null ? `range ${money(low)} – ${money(high)}` : null, str(tn?.computed_source)]
      .filter(Boolean)
      .join(' · ') || null;
  return (
    <div className="flex flex-wrap gap-2">
      {cell('Provider billed', n('provider_billed'))}
      {cell('EOB says you owe', n('eob_member_responsibility'))}
      {cell('Tyndale computed', n('tyndale_computed'), computedSub)}
    </div>
  );
}

function WhyExpander({ f }: { f: ReviewFinding }) {
  return (
    <details className="mt-2 rounded-lg bg-white/5 p-2 text-xs">
      <summary className="min-h-[28px] cursor-pointer text-white/60">Why this finding</summary>
      <dl className="mt-2 space-y-1">
        {f.why.map((line) => (
          <div key={line.key} className="grid grid-cols-[140px_1fr] gap-2">
            <dt className="text-white/40">{line.label}</dt>
            <dd className="text-white/80">
              {line.value === null ? (
                <NotRecorded />
              ) : typeof line.value === 'string' || typeof line.value === 'number' ? (
                String(line.value)
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

function FindingCard({
  f,
  selected,
  onToggle,
  onOpenCitation,
}: {
  f: ReviewFinding;
  selected: boolean;
  onToggle: () => void;
  onOpenCitation: (c: ReviewCitation) => void;
}) {
  return (
    <Card className={selected ? 'border-rose/60' : ''}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          {/* click-to-select scope (doc 39 §2): the same selection the verdict panel lists */}
          <label className="flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center">
            <input type="checkbox" checked={selected} onChange={onToggle} aria-label={`Select ${humanize(f.category)} for the verdict scope`} />
          </label>
          <div>
            <p className="text-sm font-semibold text-white">
              {humanize(f.category)}
              {selected ? (
                <span className="ml-2 rounded bg-rose px-1.5 py-0.5 text-[10px] font-semibold text-white">selected ✓</span>
              ) : null}
            </p>
            <p className="text-[11px] text-white/50">
              {humanize(f.finding_type)} · responsible: {humanize(f.responsible_party)} · tier {f.voice_tier} · {f.status}
            </p>
          </div>
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
      <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px]">
        <span className="text-white/40">CITATIONS</span>
        {f.citations.length ? (
          f.citations.map((c) => (
            <button
              key={c.src_id + c.marker}
              type="button"
              onClick={() => onOpenCitation(c)}
              className="min-h-[28px] rounded border border-citation/50 px-1.5 font-mono text-citation-soft hover:bg-white/5"
              title="Open the cited source"
            >
              {c.marker}
            </button>
          ))
        ) : (
          <NotRecorded />
        )}
      </div>
      <div className="mt-2 rounded-lg border border-amber/40 p-2 text-[11px]">
        <p className="font-semibold uppercase tracking-widest text-amber-soft">Analyst notes · internal — never shown to users</p>
        {/* the AGENT'S reasoning, or "not recorded". A reviewer's verdict note never appears here. */}
        <p className="mt-1 whitespace-pre-wrap text-white/70">{f.analyst_notes ?? <NotRecorded />}</p>
      </div>
      <WhyExpander f={f} />
    </Card>
  );
}

function CitationSheet({
  citation,
  onClose,
  onOpenDocument,
}: {
  citation: ReviewCitation;
  onClose: () => void;
  onOpenDocument?: (docIndex: number, page: number | null) => void;
}) {
  const s = citation.source;
  return (
    <Sheet title={citation.marker} subtitle={[citation.authority, citation.section].filter(Boolean).join(' · ')} onClose={onClose}>
      {s.kind === 'chunk' ? (
        <div className="space-y-3 text-sm">
          <KeyValues
            data={{ collection: s.collection, title: s.title, effective_date: s.effective_date, last_verified: s.last_verified, source_id: citation.src_id }}
          />
          {s.text ? (
            <p className="whitespace-pre-wrap rounded-lg bg-white/5 p-3 leading-6 text-white/80">
              {s.text}
              {s.truncated ? <span className="text-white/40"> … (truncated)</span> : null}
            </p>
          ) : (
            <p className="text-xs text-white/40">The retrieved chunk carried no text.</p>
          )}
        </div>
      ) : s.kind === 'document' ? (
        <div className="space-y-3 text-sm text-white/80">
          <p>
            Cites one of this case’s documents — document #{s.doc_index + 1}
            {s.page ? `, page ${s.page}` : ''}.
          </p>
          {onOpenDocument ? (
            <button
              type="button"
              onClick={() => onOpenDocument(s.doc_index, s.page)}
              className="min-h-[44px] rounded-lg border border-white/15 px-3 text-xs text-white/80 hover:bg-white/5"
            >
              Open the document
            </button>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-white/60">
          This citation’s source (<span className="font-mono">{citation.src_id}</span>) was not among the chunks this run retrieved, and it
          isn’t one of the case’s documents — <NotRecorded />. A citation with no retrievable source is itself worth a look.
        </p>
      )}
    </Sheet>
  );
}

function LeftPane({
  left,
  caseRow,
  onOpenDocument,
}: {
  left: Workspace['left'];
  caseRow: Workspace['case'];
  onOpenDocument?: (doc: Workspace['left']['documents'][number]) => void;
}) {
  // One namespace: the server numbers documents and eobs together (doc_index).
  const docs = [...left.documents, ...left.eobs];
  return (
    <div className="space-y-4">
      <div>
        <SectionLabel>Source documents</SectionLabel>
        {docs.length ? (
          <div className="space-y-2">
            {docs.map((d) => {
              const body = (
                <>
                  <p className="font-semibold text-white/80">
                    {humanize(d.document_type ?? d.kind)}
                    <span className="text-white/40"> · {d.filename ?? 'unnamed'}</span>
                  </p>
                  <p className="text-white/40">
                    {d.page_count ? `${d.page_count} pages · ` : ''}
                    {d.has_text ? `${d.text_chars.toLocaleString()} chars extracted` : 'no text extracted'}
                    {d.extraction_status ? ` · ${humanize(d.extraction_status)}` : ''}
                  </p>
                  {d.claim_number || d.account_number ? (
                    <p className="font-mono text-white/50">
                      {d.claim_number ? `claim ${d.claim_number}` : ''}
                      {d.claim_number && d.account_number ? ' · ' : ''}
                      {d.account_number ? `acct ${d.account_number}` : ''}
                    </p>
                  ) : null}
                </>
              );
              return onOpenDocument ? (
                <button
                  key={d.doc_index}
                  type="button"
                  onClick={() => onOpenDocument(d)}
                  className="block min-h-[44px] w-full rounded-xl border border-white/10 bg-navy-soft p-3 text-left text-xs hover:border-white/30"
                >
                  {body}
                  <span className="mt-1 block text-[11px] text-citation-soft">Open viewer →</span>
                </button>
              ) : (
                <Card key={d.doc_index} className="text-xs">
                  {body}
                </Card>
              );
            })}
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
          <div className="mt-2">
            <p className="text-[11px] text-white/40">Coverage terms</p>
            <KeyValues data={left.extraction.coverage} skip={['user_input_provenance']} />
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

/** A non-text thread message (status card, verification request, moment card…): its kind-specific
 *  essentials as label/value rows — never the raw payload. */
function MessagePayload({ payload }: { payload: unknown }) {
  const d = asDict(payload);
  if (!d) return <NotRecorded />;
  return (
    <>
      <KeyValues data={d} />
      <RawToggle value={d} />
    </>
  );
}

function ConversationTab({ messages }: { messages: Dict[] }) {
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
            {content ? <p className="whitespace-pre-wrap leading-5">{content}</p> : <MessagePayload payload={m.payload} />}
          </div>
        );
      })}
    </div>
  );
}

function TierRendering({ t }: { t: Workspace['tabs']['results']['tiers'][number] }) {
  const claim = asDict(t.tier_b_claim);
  const rec = asDict(t.tier_c_recommendation);
  return (
    <Card className="text-xs">
      <p className="font-mono text-white/40">
        {shortId(t.finding_id)} · voice tier {t.voice_tier}
      </p>
      <p className="mt-2 text-[10px] uppercase tracking-widest text-white/40">A · facts</p>
      <KeyValues data={t.tier_a_facts} skip={['notes', 'analyst_notes']} />
      <p className="mt-2 text-[10px] uppercase tracking-widest text-white/40">B · claim</p>
      {claim ? (
        <>
          <p className="text-white/80">{str(claim.claim) ?? str(claim.text) ?? <NotRecorded />}</p>
          <KeyValues data={claim} skip={['claim', 'text', 'citations', 'citation']} />
        </>
      ) : (
        <NotRecorded />
      )}
      <p className="mt-2 text-[10px] uppercase tracking-widest text-white/40">C · recommendation</p>
      {rec ? (
        <>
          <p className="text-white/80">{str(rec.action) ?? <NotRecorded />}</p>
          {str(rec.reasoning) ? <p className="text-white/50">because: {str(rec.reasoning)}</p> : null}
        </>
      ) : (
        <NotRecorded />
      )}
      <RawToggle value={{ facts: t.tier_a_facts, claim: t.tier_b_claim, recommendation: t.tier_c_recommendation }} />
    </Card>
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
              const script = asDict(g.script) ?? {};
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
              <TierRendering key={t.finding_id} t={t} />
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
        {r.deadlines.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {r.deadlines.map((d, i) => (
              <li key={str(d.deadline_id) ?? i}>
                <span className="font-mono">{str(d.deadline_date) ?? '—'}</span> · {humanize(str(d.deadline_type))} ·{' '}
                <span className="text-white/40">{humanize(str(d.status))}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-white/40">None.</p>
        )}
      </div>
      <div>
        <SectionLabel>Outcomes reported by the user</SectionLabel>
        {r.outcomes.length ? (
          <ul className="space-y-2 text-xs text-white/70">
            {r.outcomes.map((o, i) => {
              const payload = asDict(o.payload) ?? {};
              return (
                <li key={i} className="rounded-lg bg-white/5 p-2">
                  <p>
                    {humanize(str(o.feedback_type))} · <span className="text-white/40">{when(str(o.created_at))}</span>
                  </p>
                  <KeyValues data={payload} />
                  <RawToggle value={o} />
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-xs text-white/40">None reported yet.</p>
        )}
      </div>
    </div>
  );
}

function NoneOnThisRun({ what }: { what: string }) {
  return <p className="text-xs text-white/40">None on this run — {what}.</p>;
}

function ProvenanceTab({ p }: { p: Workspace['tabs']['provenance'] }) {
  return (
    <div className="space-y-4">
      {p.tripwires.length ? (
        <Card className="border-rose/40">
          <SectionLabel>Tripwires fired</SectionLabel>
          <ul className="space-y-1 text-xs text-white/80">
            {p.tripwires.map((tw, i) => (
              <li key={i}>
                <span className="font-semibold">{humanize(str(tw.which))}</span>
                {Array.isArray(tw.codes) && tw.codes.length ? <span className="font-mono"> · {tw.codes.join(', ')}</span> : null}
                {str(tw.category) ? ` · ${humanize(str(tw.category))}` : ''}
                <span className="text-white/40"> · {when(str(tw.at))}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div>
        <SectionLabel>User answers &amp; attestations · {p.user_answers.length}</SectionLabel>
        {p.user_answers.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.user_answers.map((a, i) => (
              <li key={i}>
                <span className="text-white/40">{humanize(a.kind)}</span> · {a.code ? <span className="font-mono">{a.code} </span> : null}
                {a.label}: <span className="font-semibold text-white/90">{a.value === null ? '—' : String(a.value)}</span>
                {a.note ? <span className="text-white/50"> — “{a.note}”</span> : null}
                <span className="text-white/40"> · {a.at ? when(a.at) : 'time not recorded'}</span>
              </li>
            ))}
          </ul>
        ) : (
          <NoneOnThisRun what="the user confirmed no line items, typed no coverage values and was not asked to attest" />
        )}
      </div>

      <div>
        <SectionLabel>Priors applied · {p.priors_applied.length}</SectionLabel>
        {p.priors_applied.length ? (
          <table className="w-full text-[11px] text-white/70">
            <thead className="text-white/40">
              <tr>
                <th className="py-1 text-left">Missing input</th>
                <th className="py-1 text-left">Prior (low · base · high)</th>
                <th className="py-1 text-left">Tier</th>
                <th className="py-1 text-left">Resulting range</th>
                <th className="py-1 text-left">Source</th>
              </tr>
            </thead>
            <tbody>
              {p.priors_applied.map((pr) => {
                const fmt = (v: number) => (pr.unit === 'usd' ? money(v) : `${Math.round(v * 100)}%`);
                return (
                  <tr key={pr.input} className="border-t border-white/10">
                    <td className="py-1">{humanize(pr.input)}</td>
                    <td className="py-1 font-mono">
                      {fmt(pr.low)} · {fmt(pr.base)} · {fmt(pr.high)}
                    </td>
                    <td className="py-1">{pr.tier ?? '—'}</td>
                    <td className="py-1 font-mono">
                      {pr.resulting_range ? `${money(pr.resulting_range.low)} – ${money(pr.resulting_range.high)}` : 'point form (no range shown)'}
                    </td>
                    <td className="py-1 text-white/40">
                      {pr.source}
                      {pr.placeholder ? ' · placeholder' : ''}
                      {pr.as_of ? ` · as of ${pr.as_of}` : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <NoneOnThisRun what="every cost-share input the engine needs was stated by a document or the user" />
        )}
      </div>

      <div>
        <SectionLabel>Pricing &amp; reference data · {p.pricing_reference.length}</SectionLabel>
        {p.pricing_reference.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.pricing_reference.map((x, i) => (
              <li key={i}>
                <span className="font-mono">{x.tool}</span> · {x.outcome ?? '—'} · {x.source ?? <NotRecorded />} · as of {x.as_of ?? <NotRecorded />}
                <span className="text-white/40"> · {when(x.at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <NoneOnThisRun what="no pricing or fee-schedule lookup was recorded" />
        )}
      </div>

      <div>
        <SectionLabel>Knowledge chunks retrieved · {p.qdrant_chunks_retrieved.length}</SectionLabel>
        {p.qdrant_chunks_retrieved.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.qdrant_chunks_retrieved.slice(0, 25).map((c, i) => {
              const d = asDict(c) ?? {};
              return (
                <li key={i}>
                  <span className="font-mono">{str(d.src_id) ?? str(d.source_id) ?? str(d.chunk_id) ?? str(d.id) ?? `#${i + 1}`}</span>
                  {str(d.collection) ? ` · ${str(d.collection)}` : ''}
                  {str(d.title) ?? str(d.authority) ? ` · ${str(d.title) ?? str(d.authority)}` : ''}
                  {str(d.effective_date) ? <span className="text-white/40"> · effective {str(d.effective_date)}</span> : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-xs text-white/40">No chunks recorded.</p>
        )}
        {p.qdrant_chunks_retrieved.length ? <RawToggle value={p.qdrant_chunks_retrieved} /> : null}
      </div>

      <div>
        <SectionLabel>Skills loaded</SectionLabel>
        {p.skills_loaded.length ? <p className="text-xs text-white/70">{p.skills_loaded.join(' · ')}</p> : <p className="text-xs text-white/40">None recorded.</p>}
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
        <SectionLabel>
          Subagent calls · {p.subagent_calls.length} · Model calls · {p.llm_calls.length}
        </SectionLabel>
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
        <SectionLabel>
          Findings written · {p.findings_written.length} · research log · {p.research_log.length} entries
        </SectionLabel>
        {p.research_log.length ? (
          <ul className="space-y-1 text-xs text-white/70">
            {p.research_log.map((e, i) => {
              const d = asDict(e) ?? {};
              return (
                <li key={i}>
                  <span className="font-semibold">{humanize(str(d.kind) ?? 'entry')}</span>
                  {str(d.which) ? ` · ${humanize(str(d.which))}` : ''}
                  {str(d.query) ? ` · “${str(d.query)}”` : ''}
                  {str(d.at) ?? str(d.timestamp) ? <span className="text-white/40"> · {when(str(d.at) ?? str(d.timestamp))}</span> : null}
                </li>
              );
            })}
          </ul>
        ) : null}
        {p.research_log.length ? <RawToggle value={p.research_log} /> : null}
      </div>
      <div>
        <SectionLabel>Not collected yet</SectionLabel>
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

const LOAD_TIMEOUT_MS = 30_000;

export function ReviewWorkspace({ caseId }: { caseId: string }) {
  const [ws, setWs] = useState<Workspace | null>(null);
  const [tab, setTab] = useState<Tab>('analysis');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The reviewer's in-progress verdict lives HERE, above everything a refetch can replace.
  const [draft, setDraft] = useState<VerdictDraft>(EMPTY_DRAFT);
  const [recorded, setRecorded] = useState<ReviewVerdictRecord[]>([]);
  const [justRecordedId, setJustRecordedId] = useState<string | null>(null);
  const [citation, setCitation] = useState<ReviewCitation | null>(null);
  const [viewing, setViewing] = useState<{ doc: ReviewDocumentCard; page: number | null } | null>(null);
  const inflight = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    inflight.current?.abort();
    const ctl = new AbortController();
    inflight.current = ctl;
    // No permanent "Loading workspace…": the fetch is aborted at 30 s and says so.
    const timer = setTimeout(() => ctl.abort(new DOMException('timeout', 'TimeoutError')), LOAD_TIMEOUT_MS);
    setLoading(true);
    adminReviewWorkspace(caseId, ctl.signal)
      .then((w) => {
        setWs(w);
        setRecorded([]); // the server copy now carries them
        setError(null);
      })
      .catch((e: unknown) => {
        if (ctl.signal.aborted && ctl.signal.reason?.name !== 'TimeoutError') return; // superseded
        const timedOut = ctl.signal.reason?.name === 'TimeoutError';
        setError(timedOut ? 'The workspace took longer than 30 s to load.' : e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        clearTimeout(timer);
        if (inflight.current === ctl) setLoading(false);
      });
  }, [caseId]);

  useEffect(() => {
    load();
    return () => inflight.current?.abort();
  }, [load]);

  const onClaim = useCallback(
    (takeOver: boolean) => {
      adminReviewClaim(caseId, takeOver)
        .then(() => load())
        .catch(() => undefined); // a failed claim never blocks a verdict — that route records the reviewer
    },
    [caseId, load],
  );

  // ONLY the very first load may take over the screen. Once a workspace is on screen, a failed
  // refetch is a banner above it — never an unmount (that is how a draft used to be lost).
  if (!ws) {
    if (error) {
      return (
        <div role="alert" className="rounded-xl border border-rose/40 bg-navy-soft p-4 text-sm">
          <p className="text-rose-soft">Couldn’t load this case: {error}</p>
          <button
            type="button"
            onClick={load}
            className="mt-3 min-h-[44px] rounded-lg border border-white/15 px-3 text-xs text-white/80 hover:bg-white/5"
          >
            Retry
          </button>
        </div>
      );
    }
    return <p className="text-sm text-white/40">Loading workspace…</p>;
  }

  const viewerMasked = ws.viewer?.masked ?? null;
  const claim: ClaimView = !ws.review
    ? { kind: 'none' }
    : ws.review.state === 'unreviewed' || ws.review.state === 're_review'
      ? { kind: 'unclaimed' }
      : ws.review.state === 'in_review'
        ? ws.review.reviewer_masked && ws.review.reviewer_masked === viewerMasked
          ? { kind: 'mine' }
          : { kind: 'other', reviewerMasked: ws.review.reviewer_masked }
        : { kind: 'decided' };
  const verdicts = [...recorded.filter((r) => !ws.verdicts.some((v) => v.verdict_id === r.verdict_id)), ...ws.verdicts];
  const onRecorded = (record: ReviewVerdictRecord) => {
    setRecorded((prev) => [record, ...prev]); // shown in the history at once
    setJustRecordedId(record.verdict_id);
    setDraft(EMPTY_DRAFT); // mode / type / scope / cause / notes all reset — nothing sticky
    load();
  };

  const a = ws.tabs.analysis;
  const findingLabels = a.findings.map((f) => ({
    finding_id: f.finding_id,
    label: `${humanize(f.category)}${f.amount_usd !== null ? ` · ${money(f.amount_usd)}` : ''}`,
  }));

  return (
    <div>
      {error ? (
        <div role="alert" className="mb-3 flex flex-wrap items-center gap-3 rounded-xl border border-rose/40 bg-navy-soft px-3 py-2 text-xs">
          <span className="text-rose-soft">Refresh failed: {error} — showing the last loaded copy; your draft is untouched.</span>
          <button type="button" onClick={load} className="min-h-[44px] rounded-lg border border-white/15 px-3 text-white/80 hover:bg-white/5">
            Retry
          </button>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-white/40">
            Review · case{loading ? ' · refreshing…' : ''}
          </p>
          <h1 className="text-lg font-bold text-white">
            {caseTitle(ws.case.provider)}
            {serviceDate(ws.case.service_date) ? (
              <span className="font-normal text-white/60"> · {serviceDate(ws.case.service_date)}</span>
            ) : null}
          </h1>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-sm text-white/70">
            <span>
              {shortId(ws.case.case_file_id)} · {ws.case.user_masked ?? '—'}
              {ws.review ? ` · run #${ws.review.run_seq}` : ''}
            </span>
            <DocumentSetChip set={ws.case.document_set} />
            <IntakeModeChip mode={ws.case.intake_mode} />
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
        <LeftPane left={ws.left} caseRow={ws.case} onOpenDocument={(doc) => setViewing({ doc, page: null })} />

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
              {/* M1 (2026-09-23): the planner's narrative is markdown — rendered, never raw syntax */}
              {a.summary ? (
                <Markdown text={a.summary} />
              ) : a.summary_pending ? (
                <p className="text-xs text-amber-soft" data-testid="summary-pending">
                  Summary owed — the provider refused it in time; audit_retry writes it
                  {a.summary_retry_attempts ? ` (${a.summary_retry_attempts} attempt(s) so far` : ' (none yet'}
                  {a.summary_retry_after ? `, next not before ${a.summary_retry_after})` : ')'}.
                </p>
              ) : (
                <p className="text-xs text-white/40">No summary composed.</p>
              )}
              {a.findings.length ? (
                <div className="space-y-3">
                  {a.findings.map((f) => (
                    <FindingCard
                      key={f.finding_id}
                      f={f}
                      selected={draft.targets.includes(f.finding_id)}
                      onToggle={() => setDraft((d) => toggleTarget(d, f.finding_id))}
                      onOpenCitation={setCitation}
                    />
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

        <VerdictPanel
          caseId={caseId}
          review={ws.review}
          viewerMasked={viewerMasked}
          claim={claim}
          onClaim={onClaim}
          findings={findingLabels}
          verdicts={verdicts}
          justRecordedId={justRecordedId}
          draft={draft}
          onDraft={setDraft}
          onRecorded={onRecorded}
        />
      </div>
      {citation ? (
        <CitationSheet
          citation={citation}
          onClose={() => setCitation(null)}
          onOpenDocument={(docIndex, page) => {
            const doc = [...ws.left.documents, ...ws.left.eobs].find((d) => d.doc_index === docIndex);
            setCitation(null);
            if (doc) setViewing({ doc, page });
          }}
        />
      ) : null}
      {viewing ? <DocumentViewer caseId={caseId} doc={viewing.doc} page={viewing.page} onClose={() => setViewing(null)} /> : null}
    </div>
  );
}
