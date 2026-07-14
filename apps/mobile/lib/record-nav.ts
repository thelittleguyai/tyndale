/**
 * Record navigation helpers (D5, Phase C §3 — DL-91). When ENABLE_RECORD_VIEW is on, the Record
 * and its sub-case views are the canonical surfaces, so a deep link to the legacy /audit/{id}
 * screen redirects to the right Record location. When the flag is off, nothing redirects — the
 * classic audit screen renders unchanged (flag-off IS the transition, D7).
 */

// Mirror of runtime app/routes/record.py `_RESULTS_BEARING`: a sub-case whose summary is fetchable
// (has results, or a terminal state with an honest summary) resumes at /case/{id}; anything still
// in flight resumes at its thread. Keep in sync with the server set.
export const RESULTS_BEARING: ReadonlySet<string> = new Set([
  'audit_complete',
  'audit_incomplete',
  'extraction_failed',
  'not_a_bill',
  'resolved',
  'archived',
]);

/**
 * Where a deep link to /audit/{id} should land. Returns null when the Record is disabled (render
 * the classic audit screen); otherwise the sub-case summary for a results-bearing case, or its
 * thread for an in-flight one.
 */
export function recordDeepLinkTarget(
  caseFileId: string,
  status: string,
  recordEnabled: boolean,
): string | null {
  if (!recordEnabled) return null;
  return RESULTS_BEARING.has(status) ? `/case/${caseFileId}` : `/audit/${caseFileId}/thread`;
}
