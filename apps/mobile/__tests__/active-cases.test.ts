import { activeCaseRoute } from '../lib/active-cases';

describe('activeCaseRoute — dashboard Open Cases card (Item 1)', () => {
  it('routes a pre-audit case to the encounter-verification screen', () => {
    // encounter_verification_pending / open / extraction_failed all resume === 'encounter'.
    expect(activeCaseRoute({ case_file_id: 'abc-123', resume: 'encounter' })).toBe(
      '/audit/abc-123/encounter',
    );
  });

  it('routes an audit-lifecycle case to the results screen', () => {
    // audit_running / audit_complete / audit_incomplete resume === 'results'; the results
    // screen would spin forever on a pre-encounter case, which is why routing is status-driven.
    expect(activeCaseRoute({ case_file_id: 'xyz-789', resume: 'results' })).toBe('/audit/xyz-789');
  });
});
