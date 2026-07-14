import { RESULTS_BEARING, recordDeepLinkTarget } from '../lib/record-nav';

describe('recordDeepLinkTarget — /audit/{id} deep-link redirect (D5 §3)', () => {
  it('returns null when the Record is disabled (render the classic audit screen)', () => {
    expect(recordDeepLinkTarget('c1', 'audit_complete', false)).toBeNull();
    expect(recordDeepLinkTarget('c1', 'audit_running', false)).toBeNull();
  });

  it('sends a results-bearing case to its sub-case summary', () => {
    for (const status of RESULTS_BEARING) {
      expect(recordDeepLinkTarget('c1', status, true)).toBe('/case/c1');
    }
  });

  it('sends an in-flight case to its thread', () => {
    for (const status of ['audit_running', 'encounter_verification_pending', 'encounter_verified', 'awaiting_eob_confirmation']) {
      expect(recordDeepLinkTarget('c1', status, true)).toBe('/audit/c1/thread');
    }
  });
});
