import { activeCaseRoute } from '../lib/active-cases';
import { subCaseRoute } from '../components/record/RecordSection';

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

describe('a case still on the guided route resumes THERE (doc 40)', () => {
  it('Open Cases card → /intake for that case, never the verify screen', () => {
    expect(activeCaseRoute({ case_file_id: 'g-1', resume: 'intake' })).toBe('/intake?case=g-1');
  });

  it('Record row → /intake for that case; the other two targets are unchanged', () => {
    expect(subCaseRoute({ case_file_id: 'g-1', resume: 'intake' })).toBe('/intake?case=g-1');
    expect(subCaseRoute({ case_file_id: 'c-2', resume: 'summary' })).toBe('/case/c-2');
    expect(subCaseRoute({ case_file_id: 'c-3', resume: 'thread' })).toBe('/audit/c-3/thread');
  });
});

