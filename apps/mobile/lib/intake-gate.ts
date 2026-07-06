/**
 * Intake-gate decision — extracted from (app)/_layout.tsx for testability.
 *
 * The wizard is mandatory ONLY for brand-new users: no case history AND intake not complete.
 * Anyone with a case file or a completed intake is never hard-redirected, so "Save & exit"
 * always exits. /audit/* is never gated — a running audit must always render regardless of
 * intake state. (2026-07-06 regression fix: a fresh upload creates a not_started case that
 * used to re-gate returning users into a wizard loop and hide their in-flight audit.)
 */
export function shouldRedirectToWizard(args: {
  intakeStatus: string;
  hasCases: boolean;
  deferred: boolean;
  pathname: string | null;
}): boolean {
  const { intakeStatus, hasCases, deferred, pathname } = args;
  if (pathname?.startsWith('/audit')) return false; // a running audit is never gated
  if (intakeStatus === 'complete') return false; // completed intake → never re-gate
  if (hasCases) return false; // any case history → never trap; Save & exit exits
  if (deferred) return false; // brand-new user's explicit Save & exit escape
  return true; // brand-new user, no history → into the wizard
}
