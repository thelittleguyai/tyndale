/**
 * Findings on the results surfaces (e2e 2026-09-23 M1): every surviving finding the API
 * returns is rendered — error findings first, and the informational context (all-clear notes,
 * audit-performed summaries, $0 context) under an EXPLICIT "N more notes" expander. Nothing
 * hidden by materiality is ever hidden silently.
 */
/** Mirror of the doctrine config's informational category family (X2). */
const INFORMATIONAL = new Set([
  'out_of_scope',
  'regime_document_mismatch',
  'cap_constant_not_loaded',
  'diagnostic_clear',
  'upcoding_diagnostic_clear',
  'diagnostic_audit_complete_no_confirmed_errors',
  'cost_sharing_audit',
]);
const INFORMATIONAL_STEMS = ['_clear', '_clean', '_audit', 'no_confirmed', '_complete', '_pass'];

/** The fields the split reads — the audit's FindingOut and the sub-case's FindingBrief both fit. */
export interface SplittableFinding {
  category: string;
  presentation?: string | null;
  facts?: Record<string, unknown> | null;
  dollar_impact?: number | null;
}

export function isInformational(f: SplittableFinding): boolean {
  if (f.presentation === 'informational_context') return true;
  const c = (f.category ?? '').toLowerCase();
  if (INFORMATIONAL.has(c)) return true;
  const gap = f.facts?.gap ?? f.dollar_impact;
  const claimsMoney = typeof gap === 'number' && gap > 0;
  return !claimsMoney && INFORMATIONAL_STEMS.some((s) => c.includes(s));
}

export function splitFindings<T extends SplittableFinding>(findings: T[]): { errors: T[]; notes: T[] } {
  const errors: T[] = [];
  const notes: T[] = [];
  for (const f of findings) (isInformational(f) ? notes : errors).push(f);
  return { errors, notes };
}

export function notesLabel(n: number): string {
  return n === 1 ? '1 more note' : `${n} more minor notes`;
}
