'use client';

import { useState } from 'react';

import { track } from '@/lib/analytics';
import { adminSubmitVerdict, type AdminFinding, type VerdictValue } from '@/lib/api-client';

const VERDICTS: { value: VerdictValue; label: string }[] = [
  { value: 'correct', label: 'Correct' },
  { value: 'missed_finding', label: 'Missed' },
  { value: 'hallucinated', label: 'Hallucinated' },
  { value: 'partial', label: 'Partial' },
  { value: 'unable_to_verify', label: 'Unverifiable' },
];

type Scope = 'whole' | 'finding' | 'response';

function lines(text: string): string[] | null {
  const out = text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  return out.length ? out : null;
}

export function VerdictForm({
  caseId,
  findings,
  onSubmitted,
}: {
  caseId: string;
  findings: AdminFinding[];
  onSubmitted: () => void;
}) {
  const [verdict, setVerdict] = useState<VerdictValue>('correct');
  const [notes, setNotes] = useState('');
  const [missed, setMissed] = useState('');
  const [hallucinated, setHallucinated] = useState('');
  const [scope, setScope] = useState<Scope>('whole');
  const [findingId, setFindingId] = useState<string>(findings[0]?.finding_id ?? '');
  const [responseId, setResponseId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await adminSubmitVerdict(caseId, {
        verdict,
        notes: notes || null,
        missed_findings: verdict === 'missed_finding' ? lines(missed) : null,
        hallucinated_claims: verdict === 'hallucinated' ? lines(hallucinated) : null,
        target_findings: scope === 'finding' && findingId ? [findingId] : null,
        target_response: scope === 'response' && responseId ? responseId : null,
      });
      track('verdict_submitted', { verdict, scope });
      setNotes('');
      setMissed('');
      setHallucinated('');
      onSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const inputClass =
    'mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white';

  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <h3 className="mb-3 text-sm font-semibold text-white/85">Capture a verdict</h3>

      <div className="mb-3 grid grid-cols-3 gap-2">
        {VERDICTS.map((v) => (
          <button
            key={v.value}
            onClick={() => setVerdict(v.value)}
            className={`rounded-lg border px-2 py-2 text-xs font-semibold ${
              verdict === v.value
                ? 'border-sage bg-sage/20 text-white'
                : 'border-white/10 bg-white/5 text-white/60'
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {verdict === 'missed_finding' ? (
        <textarea
          value={missed}
          onChange={(e) => setMissed(e.target.value)}
          placeholder="Missed findings (one per line)"
          rows={3}
          className={inputClass}
        />
      ) : null}
      {verdict === 'hallucinated' ? (
        <textarea
          value={hallucinated}
          onChange={(e) => setHallucinated(e.target.value)}
          placeholder="Hallucinated claims (one per line)"
          rows={3}
          className={inputClass}
        />
      ) : null}

      <label className="mb-1 block text-xs text-white/60">Scope</label>
      <select value={scope} onChange={(e) => setScope(e.target.value as Scope)} className={inputClass}>
        <option value="whole">Whole case</option>
        <option value="finding">Specific finding</option>
        <option value="response">Specific response</option>
      </select>

      {scope === 'finding' ? (
        <select value={findingId} onChange={(e) => setFindingId(e.target.value)} className={inputClass}>
          {findings.map((f) => (
            <option key={f.finding_id} value={f.finding_id}>
              {f.category} ({f.finding_type})
            </option>
          ))}
        </select>
      ) : null}

      {scope === 'response' ? (
        <input
          value={responseId}
          onChange={(e) => setResponseId(e.target.value)}
          placeholder="response id (blank = latest)"
          className={inputClass}
        />
      ) : null}

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes (optional)"
        rows={2}
        className={inputClass}
      />

      {error ? <p className="mb-2 text-xs text-rose">{error}</p> : null}

      <button
        disabled={busy}
        onClick={submit}
        className={`w-full rounded-lg px-3 py-2.5 text-sm font-bold ${
          busy ? 'bg-white/10 text-white/40' : 'bg-sage text-ink'
        }`}
      >
        {busy ? 'Saving…' : 'Submit verdict'}
      </button>
    </div>
  );
}
