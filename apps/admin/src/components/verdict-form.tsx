'use client';

import { useState } from 'react';

import { adminSubmitVerdict, type AdminFinding, type VerdictValue } from '@/lib/api-client';
import { track } from '@/lib/analytics';

const VERDICTS: { value: VerdictValue; label: string }[] = [
  { value: 'correct', label: 'Correct' },
  { value: 'partially_correct', label: 'Partially' },
  { value: 'wrong', label: 'Wrong' },
];

type Scope = 'whole' | 'finding' | 'response';

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
        target_findings: scope === 'finding' && findingId ? [findingId] : null,
        target_response: scope === 'response' && responseId ? responseId : null,
      });
      track('verdict_submitted', { verdict, scope });
      setNotes('');
      onSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <h3 className="mb-3 text-sm font-semibold text-white/85">Capture a verdict</h3>

      <div className="mb-3 flex gap-2">
        {VERDICTS.map((v) => (
          <button
            key={v.value}
            onClick={() => setVerdict(v.value)}
            className={`flex-1 rounded-lg border px-2 py-2 text-xs font-semibold ${
              verdict === v.value
                ? 'border-sage bg-sage/20 text-white'
                : 'border-white/10 bg-white/5 text-white/60'
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      <label className="mb-1 block text-xs text-white/60">Scope</label>
      <select
        value={scope}
        onChange={(e) => setScope(e.target.value as Scope)}
        className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
      >
        <option value="whole">Whole case</option>
        <option value="finding">Specific finding</option>
        <option value="response">Specific response</option>
      </select>

      {scope === 'finding' ? (
        <select
          value={findingId}
          onChange={(e) => setFindingId(e.target.value)}
          className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
        >
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
          className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
        />
      ) : null}

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes (optional)"
        rows={3}
        className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
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
