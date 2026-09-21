'use client';

import { useRef, useState } from 'react';

import {
  adminReviewVerdict,
  type DisapprovalCause,
  type DisapprovalType,
  type ReviewQueueItem,
  type ReviewVerdictRecord,
} from '@/lib/api-client';
import {
  CAUSES,
  DISAPPROVAL_TYPES,
  toVerdictBody,
  toggleTarget,
  validateDraft,
  verdictLabel,
  type DraftField,
  type VerdictDraft,
  type VerdictMode,
} from '@/lib/verdict-draft';
import { Card, SectionLabel, StatePill, humanize, when } from './review-ui';

// The right pane (doc 39 §2 + §7-2b/2c): Approve (optional note) / Disapprove… (type · scope ·
// exactly one cause · the three prompts) / Can't verify (excluded from the rate). Verdicts are
// append-only; the reviewer's UUID is the actor server-side.
//
// The DRAFT is owned by the workspace (lib/verdict-draft.ts), not by this component: a refetch
// — even a failed one — must never cost a reviewer a half-written disapproval, and the finding
// cards in the center pane drive the same scope selection.

export type ClaimView =
  | { kind: 'none' } // the run never entered the queue
  | { kind: 'unclaimed' }
  | { kind: 'mine' }
  | { kind: 'other'; reviewerMasked: string | null }
  | { kind: 'decided' };

function Hint({ text }: { text?: string }) {
  return text ? <p className="mt-1 text-[11px] text-amber">{text}</p> : null;
}

export function VerdictPanel({
  caseId,
  review,
  viewerMasked,
  claim,
  onClaim,
  findings,
  verdicts,
  justRecordedId,
  draft,
  onDraft,
  onRecorded,
}: {
  caseId: string;
  review: ReviewQueueItem | null;
  viewerMasked: string | null;
  claim: ClaimView;
  onClaim: (takeOver: boolean) => void;
  findings: { finding_id: string; label: string }[];
  verdicts: ReviewVerdictRecord[];
  justRecordedId: string | null;
  draft: VerdictDraft;
  onDraft: (next: VerdictDraft) => void;
  onRecorded: (record: ReviewVerdictRecord, state: ReviewQueueItem['state']) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // `busy` is state and lands a render late; the ref closes the double-click window so a
  // second submit can never append a second verdict + review row (deep review C6).
  const submitting = useRef(false);

  const findingIds = findings.map((f) => f.finding_id);
  const { valid, problems } = validateDraft(draft, findingIds);
  const set = (patch: Partial<VerdictDraft>) => onDraft({ ...draft, ...patch });
  const hint = (f: DraftField) => problems[f];

  // Intent, not a page view, claims the run (the claim route is idempotent and never steals).
  const intend = () => {
    if (claim.kind === 'unclaimed') onClaim(false);
  };

  const submit = async () => {
    if (submitting.current || !valid) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      const body = toVerdictBody(draft);
      const r = await adminReviewVerdict(caseId, body);
      onRecorded(
        {
          verdict_id: r.verdict_id,
          verdict: r.verdict,
          notes: body.note ?? null,
          cause: r.cause,
          structured_note: body.structured_note ?? null,
          target_findings: body.target_findings ?? null,
          reviewer_masked: viewerMasked,
          captured_at: new Date().toISOString(),
        },
        r.state,
      );
    } catch (e: unknown) {
      // the server's 422 list (or any failure) — the draft is untouched, so nothing is lost
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  const modeBtn = (m: VerdictMode, label: string, cls: string) => (
    <button
      key={m}
      type="button"
      aria-pressed={draft.mode === m}
      onClick={() => {
        set({ mode: m });
        intend();
      }}
      className={`min-h-[44px] rounded-lg px-3 text-xs font-semibold ${
        draft.mode === m ? cls : 'border border-white/15 text-white/60 hover:bg-white/5'
      }`}
    >
      {label}
    </button>
  );
  const area =
    'w-full rounded-lg border border-white/15 bg-transparent px-2 py-1.5 text-sm text-white placeholder:text-white/30';

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <SectionLabel>Verdict</SectionLabel>
          {review ? <StatePill state={review.state} /> : <span className="text-[11px] text-white/40">not in queue</span>}
        </div>

        {claim.kind === 'unclaimed' ? (
          <button
            type="button"
            onClick={() => onClaim(false)}
            className="mb-3 min-h-[44px] w-full rounded-lg border border-white/15 px-3 text-xs text-white/70 hover:bg-white/5"
          >
            Start review · assign to me
          </button>
        ) : null}
        {claim.kind === 'mine' ? (
          <p className="mb-3 text-[11px] text-sage-soft">Reviewing as {viewerMasked ?? 'you'}</p>
        ) : null}
        {claim.kind === 'other' ? (
          <div className="mb-3 rounded-lg border border-amber/40 p-2 text-[11px] text-amber">
            Claimed by {claim.reviewerMasked ?? 'another reviewer'}.
            <button
              type="button"
              onClick={() => onClaim(true)}
              className="ml-2 min-h-[44px] rounded-lg border border-amber/40 px-2 font-semibold hover:bg-white/5"
            >
              Take over?
            </button>
          </div>
        ) : null}

        <div className="mb-3 flex flex-wrap gap-2">
          {modeBtn('approve', 'Approve', 'bg-sage text-white')}
          {modeBtn('disapprove', 'Disapprove…', 'bg-rose text-white')}
          {modeBtn('cant_verify', "Can't verify", 'bg-white/15 text-white')}
        </div>

        {draft.mode === 'disapprove' ? (
          <div className="space-y-3 text-sm">
            <label className="block text-xs text-white/60">
              Type
              <select
                value={draft.type ?? ''}
                onChange={(e) => set({ type: (e.target.value || null) as DisapprovalType | null })}
                className="mt-1 min-h-[44px] w-full rounded-lg border border-white/15 bg-navy-soft px-2 text-sm text-white"
              >
                <option value="">Choose…</option>
                {DISAPPROVAL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <Hint text={hint('type')} />
            </label>

            <fieldset className="text-xs text-white/60">
              <legend>Scope</legend>
              <div className="mt-1 flex gap-3">
                <label className="flex min-h-[44px] items-center gap-1">
                  <input type="radio" name="scope" checked={draft.scope === 'whole_case'} onChange={() => set({ scope: 'whole_case' })} /> whole
                  case
                </label>
                <label className="flex min-h-[44px] items-center gap-1">
                  <input type="radio" name="scope" checked={draft.scope === 'findings'} onChange={() => set({ scope: 'findings' })} /> selected
                  findings{draft.targets.length ? ` (${draft.targets.length})` : ''}
                </label>
              </div>
              {draft.scope === 'findings' ? (
                <div className="mt-1 space-y-1">
                  {findings.length ? (
                    findings.map((f) => (
                      <label key={f.finding_id} className="flex items-center gap-2 text-white/80">
                        <input
                          type="checkbox"
                          checked={draft.targets.includes(f.finding_id)}
                          onChange={() => onDraft(toggleTarget(draft, f.finding_id))}
                        />
                        {f.label}
                      </label>
                    ))
                  ) : (
                    <p className="text-white/40">This run has no findings to select — use whole case.</p>
                  )}
                  <p className="text-[11px] text-white/40">You can also tick a finding on its card.</p>
                </div>
              ) : null}
              <Hint text={hint('scope') ?? hint('targets')} />
            </fieldset>

            <fieldset className="text-xs text-white/60">
              <legend>Cause · exactly one</legend>
              <div className="mt-1 space-y-1">
                {CAUSES.map((c) => (
                  <label key={c.value} className="flex items-start gap-2 text-white/80">
                    <input
                      type="radio"
                      name="cause"
                      className="mt-1"
                      checked={draft.cause === c.value}
                      onChange={() => set({ cause: c.value as DisapprovalCause })}
                    />
                    <span>
                      {c.label}
                      <span className="block text-[11px] text-white/40">{c.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
              <Hint text={hint('cause')} />
            </fieldset>

            <label className="block text-xs text-white/60">
              Tyndale concluded…
              <textarea value={draft.concluded} onChange={(e) => set({ concluded: e.target.value })} rows={2} className={`mt-1 ${area}`} />
              <Hint text={hint('concluded')} />
            </label>
            <label className="block text-xs text-white/60">
              It should have concluded…
              <textarea value={draft.shouldHave} onChange={(e) => set({ shouldHave: e.target.value })} rows={2} className={`mt-1 ${area}`} />
              <Hint text={hint('shouldHave')} />
            </label>
            <label className="block text-xs text-white/60">
              Which input or rule…
              <textarea value={draft.inputOrRule} onChange={(e) => set({ inputOrRule: e.target.value })} rows={2} className={`mt-1 ${area}`} />
              <Hint text={hint('inputOrRule')} />
            </label>
          </div>
        ) : null}

        <label className="mt-3 block text-xs text-white/60">
          Reviewer note · optional — no patient identifiers needed (the case link carries context)
          <textarea
            value={draft.note}
            onChange={(e) => set({ note: e.target.value })}
            onFocus={intend}
            rows={3}
            placeholder={draft.mode === 'cant_verify' ? 'What was missing?' : ''}
            className={`mt-1 ${area}`}
          />
        </label>
        {draft.mode === 'cant_verify' ? (
          <p className="mt-1 text-[11px] text-white/40">Excluded from the approval rate.</p>
        ) : null}

        <button
          type="button"
          onClick={submit}
          disabled={busy || !valid}
          aria-disabled={busy || !valid}
          className="mt-3 min-h-[44px] w-full rounded-lg bg-white/10 px-3 text-sm font-semibold text-white hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Recording…' : valid ? 'Record verdict' : 'Complete the fields above to record'}
        </button>
        {error ? (
          <p role="alert" className="mt-2 text-xs text-rose-soft">
            {error}
          </p>
        ) : null}
      </Card>

      <Card>
        <SectionLabel>Verdict history · append-only</SectionLabel>
        {verdicts.length ? (
          <ul className="space-y-2 text-xs">
            {verdicts.map((v) => (
              <li
                key={v.verdict_id}
                className={`rounded-lg p-2 ${v.verdict_id === justRecordedId ? 'border border-sage/60 bg-sage/10' : 'bg-white/5'}`}
              >
                <p className="font-semibold text-white/80">
                  {verdictLabel(v.verdict)}
                  {v.cause ? <span className="text-white/50"> · {humanize(v.cause)}</span> : null}
                  {v.verdict_id === justRecordedId ? <span className="ml-2 text-sage-soft">recorded just now</span> : null}
                </p>
                <p className="text-white/40">
                  {v.reviewer_masked ?? '—'} · {when(v.captured_at)}
                  {v.target_findings?.length ? ` · ${v.target_findings.length} finding(s)` : ''}
                </p>
                {v.structured_note ? (
                  <dl className="mt-1 space-y-0.5 text-white/60">
                    <div>
                      <dt className="inline text-white/40">concluded: </dt>
                      <dd className="inline">{v.structured_note.concluded}</dd>
                    </div>
                    <div>
                      <dt className="inline text-white/40">should have: </dt>
                      <dd className="inline">{v.structured_note.should_have_concluded}</dd>
                    </div>
                    <div>
                      <dt className="inline text-white/40">input/rule: </dt>
                      <dd className="inline">{v.structured_note.input_or_rule}</dd>
                    </div>
                  </dl>
                ) : null}
                {v.notes ? <p className="mt-1 italic text-white/50">{v.notes}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-white/40">No verdicts yet.</p>
        )}
      </Card>
    </div>
  );
}
