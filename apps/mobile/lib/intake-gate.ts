/**
 * Intake-gate decision — extracted from (app)/_layout.tsx for testability.
 *
 * The wizard is mandatory ONLY for brand-new users: no case history AND intake not complete.
 * Anyone with a case file or a completed intake is never hard-redirected, so "Save & exit"
 * always exits. Case-work routes are never gated — a running audit, the Record, or a sub-case
 * view must always render regardless of intake state. (2026-07-06 regression fix: a fresh upload
 * creates a not_started case that used to re-gate returning users into a wizard loop and hide
 * their in-flight audit; D5 extends the same exemption to /record + /case.)
 */

/**
 * Routes that show a specific case's work: a running audit (`/audit`), the Tyndale Record
 * (`/record`), or a sub-case summary/thread (`/case`). NEITHER gate — intake or profile — may
 * bounce these: a user deep-linking here (from a notification, a Record row, an old link) must
 * always land on the content, never a wizard or onboarding loop (the 2026-07-06 re-gating class).
 * D5 (DL-91) adds /record + /case alongside the original /audit so all three are treated alike.
 */
export function isCaseWorkRoute(pathname: string | null): boolean {
  return (
    pathname?.startsWith('/audit') === true ||
    pathname?.startsWith('/record') === true ||
    pathname?.startsWith('/case') === true
  );
}

export function shouldRedirectToWizard(args: {
  intakeStatus: string;
  hasCases: boolean;
  deferred: boolean;
  pathname: string | null;
}): boolean {
  const { intakeStatus, hasCases, deferred, pathname } = args;
  if (isCaseWorkRoute(pathname)) return false; // a running audit / Record / sub-case is never gated
  if (intakeStatus === 'complete') return false; // completed intake → never re-gate
  if (hasCases) return false; // any case history → never trap; Save & exit exits
  if (deferred) return false; // brand-new user's explicit Save & exit escape
  return true; // brand-new user, no history → into the wizard
}
