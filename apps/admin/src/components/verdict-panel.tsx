'use client';

import { useState } from 'react';

import {
  adminReviewVerdict,
  type DisapprovalCause,
  type DisapprovalType,
  type ReviewQueueItem,
  type ReviewVerdictBody,
  type ReviewVerdictRecord,
} from '@/lib/api-client';
import { Card, SectionLabel, StatePill, humanize, when } from './review-ui';

// The right pane (doc 39 §2 + §7-2b/2c): Approve (optional note) / Disapprove… (type ·
// scope · exactly one cause · the three prompts) / Can't verify (excluded from the rate).
// Verdicts are append-only; the reviewer's UUID is the actor server-side.

const TYPES: { value: DisapprovalType; label: string }[] = [
  { value: 'missed_finding', label: 'Missed a finding' },
  { value: 'hallucinated', label: 'Hallucinated a claim' },
  { value: 'wrong', label: 'Wrong conclusion' },
  { value: 'partial', label: 'Partially right' },
  { value: 'partially_correct', label: 'Partially correct' },
];

const CAUSES: { value: DisapprovalCause; label: string; hint: string }[] = [
  { value: 'content_gap', label: 'Content gap', hint: 'a rule or source the corpus does not have yet' },
  { value: 'reasoning_error', label: 'Reasoning error', hint: 'the inputs were there; the conclusion was wrong' },
  { value: 'bad_input', label: 'Bad input', hint: 'extraction or intake fed the audit something wrong' },
  { value: 'stale_data_source', label: 'Stale data source', hint: 'a source Tyndale relies on is out of date' },
];

type Mode = 'approve' | 'disapprove' | 'cant_verify';

export function VerdictPanel({
  caseId,
  review,
  findings,
  verdicts,
  onSubmitted,
}: {
  caseId: string;
  review: ReviewQueueItem | null;
  findings: { finding_id: string; label: string }[];
  verdicts: ReviewVerdictRecord[];
  onSubmitted: () => void;
}) {
  const [mode, setMode] = useState<Mode>('approve');
  const [note, setNote] = useState('');
  const [type, setType] = useState<DisapprovalType>('missed_finding');
  const [scope, setScope] = useState<'whole_case' | 'findings'>('whole_case');
  const [targets, setTargets] = useState<string[]>([]);
  const [cause, setCause] = useState<DisapprovalCause | null>(null);
  const [concluded, setConcluded] = useState('');
  const [should, setShould] = useState('');
  const [inputOrRule, setInputOrRule] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const toggleTarget = (id: string) =>
    setTargets((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const submit = async () => {
    setBusy(true);
    setError(null);
    setDone(null);
    const body: ReviewVerdictBody = { action: mode, note: note.trim() || undefined };
    if (mode === 'disapprove') {
      body.verdict_type = type;
      body.scope = scope;
      body.target_findings = scope === 'findings' ? targets : undefined;
      body.cause = cause ?? undefined;
      body.structured_note = { concluded, should_have_concluded: should, input_or_rule: inputOrRule };
    }
    try {
      const r = await adminReviewVerdict(caseId, body);
      setDone(`Recorded: ${humanize(r.state)}${r.phase2_route ? ` · Phase 2 route: ${humanize(r.phase2_route)}` : ''}`);
      setNote('');
      setConcluded('');
      setShould('');
      setInputOrRule('');
      setCause(null);
      setTargets([]);
      onSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const modeBtn = (m: Mode, label: string, cls: string) => (
    <button
      key={m}
      onClick={() => setMode(m)}
      className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${mode === m ? cls : 'border border-white/15 text-white/60 hover:bg-white/5'}`}
    >
      {label}
    </button>
  );
  const area = 'w-full rounded-lg border border-white/15 bg-transparent px-2 py-1.5 text-sm text-white placeholder:text-white/30';

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <SectionLabel>Verdict</SectionLabel>
          {review ? <StatePill state={review.state} /> : <span className="text-[11px] text-white/40">not in queue</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          {modeBtn('approve', 'Approve', 'bg-sage text-white')}
          {modeBtn('disapprove', 'Disapprove…', 'bg-rose text-white')}
          {modeBtn('cant_verify', "Can't verify", 'bg-white/15 text-white')}
        </div>

        {mode === 'disapprove' ? (
          <div className="space-y-3 text-sm">
            <label className="block text-xs text-white/60">
              Type
              <select value={type} onChange={(e) => setType(e.target.value as DisapprovalType)} className="mt-1 w-full rounded-lg border border-white/15 bg-navy-soft px-2 py-1.5 text-sm text-white">
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="text-xs text-white/60">
              Scope
              <div className="mt-1 flex gap-3">
                <label className="flex items-center gap-1">
                  <input type="radio" checked={scope === 'whole_case'} onChange={() => setScope('whole_case')} /> whole case
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" checked={scope === 'findings'} onChange={() => setScope('findings')} /> selected findings
                </label>
              </div>
              {scope === 'findings' ? (
                <div className="mt-2 space-y-1">
                  {findings.length ? (
                    findings.map((f) => (
                      <label key={f.finding_id} className="flex items-center gap-2 text-white/80">
                        <input type="checkbox" checked={targets.includes(f.finding_id)} onChange={() => toggleTarget(f.finding_id)} />
                        {f.label}
                      </label>
                    ))
                  ) : (
                    <p className="text-white/40">This run has no findings to select.</p>
                  )}
                </div>
              ) : null}
            </div>
            <div className="text-xs text-white/60">
              Cause · exactly one
              <div className="mt-1 space-y-1">
                {CAUSES.map((c) => (
                  <label key={c.value} className="flex items-start gap-2 text-white/80">
                    <input type="radio" className="mt-1" checked={cause === c.value} onChange={() => setCause(c.value)} />
                    <span>
                      {c.label}
                      <span className="block text-[11px] text-white/40">{c.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <label className="block text-xs text-white/60">
              Tyndale concluded…
              <textarea value={concluded} onChange={(e) => setConcluded(e.target.value)} rows={2} className={`mt-1 ${area}`} />
            </label>
            <label className="block text-xs text-white/60">
              It should have concluded…
              <textarea value={should} onChange={(e) => setShould(e.target.value)} rows={2} className={`mt-1 ${area}`} />
            </label>
            <label className="block text-xs text-white/60">
              Which input or rule…
              <textarea value={inputOrRule} onChange={(e) => setInputOrRule(e.target.value)} rows={2} className={`mt-1 ${area}`} />
            </label>
          </div>
        ) : null}

        <label className="mt-3 block text-xs text-white/60">
          <span className="font-semibold uppercase tracking-widest text-amber">Analyst notes · internal — never shown to users</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            placeholder={mode === 'cant_verify' ? 'What was missing? (optional)' : 'Optional'}
            className={`mt-1 ${area}`}
          />
        </label>
        {mode === 'cant_verify' ? (
          <p className="mt-1 text-[11px] text-white/40">Excluded from the approval rate.</p>
        ) : null}

        <button
          onClick={submit}
          disabled={busy}
          className="mt-3 w-full rounded-lg bg-white/10 px-3 py-2 text-sm font-semibold text-white hover:bg-white/15 disabled:opacity-40"
        >
          {busy ? 'Recording…' : 'Record verdict'}
        </button>
        {error ? <p className="mt-2 text-xs text-rose">{error}</p> : null}
        {done ? <p className="mt-2 text-xs text-sage-soft">{done}</p> : null}
      </Card>

      <Card>
        <SectionLabel>Verdict history · append-only</SectionLabel>
        {verdicts.length ? (
          <ul className="space-y-2 text-xs">
            {verdicts.map((v) => (
              <li key={v.verdict_id} className="rounded-lg bg-white/5 p-2">
                <p className="font-semibold text-white/80">
                  {humanize(v.verdict)}
                  {v.cause ? <span className="text-white/50"> · {humanize(v.cause)}</span> : null}
                </p>
                <p className="text-white/40">
                  {v.reviewer_masked ?? '—'} · {when(v.captured_at)}
                  {v.target_findings?.length ? ` · ${v.target_findings.length} finding(s)` : ''}
                </p>
                {v.structured_note ? (
                  <dl className="mt-1 space-y-0.5 text-white/60">
                    <div><dt className="inline text-white/40">concluded: </dt><dd className="inline">{v.structured_note.concluded}</dd></div>
                    <div><dt className="inline text-white/40">should have: </dt><dd className="inline">{v.structured_note.should_have_concluded}</dd></div>
                    <div><dt className="inline text-white/40">input/rule: </dt><dd className="inline">{v.structured_note.input_or_rule}</dd></div>
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
