import { shouldRedirectToWizard } from '../lib/intake-gate';

describe('intake gate — 2026-07-06 re-gating regression', () => {
  const base = { intakeStatus: 'not_started', hasCases: false, deferred: false, pathname: '/' };

  it('routes a brand-new user (no cases, not complete) into the wizard', () => {
    expect(shouldRedirectToWizard(base)).toBe(true);
  });

  it('never re-gates a completed intake, even after a fresh not_started case exists', () => {
    // The reported bug: the dashboard derives 'complete' from the older completed case.
    expect(shouldRedirectToWizard({ ...base, intakeStatus: 'complete' })).toBe(false);
  });

  it('never hard-redirects a user with case history — Save & exit always exits', () => {
    // Any existing case file → the gate lets them through and they STAY on the dashboard
    // (no bounce back to the wizard), regardless of intake status.
    expect(
      shouldRedirectToWizard({ ...base, intakeStatus: 'in_progress', hasCases: true }),
    ).toBe(false);
    expect(
      shouldRedirectToWizard({ ...base, intakeStatus: 'not_started', hasCases: true }),
    ).toBe(false);
  });

  it("respects a brand-new user's Save & exit deferred flag", () => {
    expect(shouldRedirectToWizard({ ...base, deferred: true })).toBe(false);
  });

  it('never gates /audit/* — a running audit always renders', () => {
    expect(shouldRedirectToWizard({ ...base, pathname: '/audit/e29b38fe' })).toBe(false);
    expect(shouldRedirectToWizard({ ...base, pathname: '/audit/e29b38fe/encounter' })).toBe(false);
    // …even for a genuinely brand-new user who somehow deep-links to an audit.
    expect(shouldRedirectToWizard({ ...base, hasCases: false, pathname: '/audit/x' })).toBe(false);
  });
});
