import { render } from '@testing-library/react-native';

import type { AuditResult, DocumentNeed } from '../lib/api-client';
import { NeedsDocuments } from '../app/(app)/audit/[case_file_id]/index';

function result(docs: DocumentNeed[]): AuditResult {
  return {
    case_file_id: 'c1',
    status: 'audit_incomplete',
    audit: null,
    findings: [],
    summary: '',
    incomplete_reason: 'needs_documents',
    documents_needed: docs,
  } as AuditResult;
}

describe('NeedsDocuments checklist', () => {
  it('reflects real have/need state — missing shows how-to-get, provided hides it', () => {
    const { getByText, queryByText } = render(
      <NeedsDocuments
        caseFileId="c1"
        result={result([
          { key: 'eob', label: 'Explanation of Benefits (EOB)', how_to_get: 'Ask your insurer.', have: false },
          { key: 'itemized_bill', label: 'Itemized bill', how_to_get: 'Ask billing.', have: true },
        ])}
      />,
    );
    // Both items are listed…
    expect(getByText('Explanation of Benefits (EOB)')).toBeTruthy();
    expect(getByText('Itemized bill')).toBeTruthy();
    // …but the how-to-get instructions show only for the MISSING one (unchecked),
    // never for the one we already have (checked).
    expect(getByText('Ask your insurer.')).toBeTruthy();
    expect(queryByText('Ask billing.')).toBeNull();
    // The header reflects "still need something", not "all set".
    expect(getByText('To finish your audit, we need')).toBeTruthy();
  });

  it('has a back-to-dashboard affordance and switches header when all satisfied', () => {
    const { getByText } = render(
      <NeedsDocuments
        caseFileId="c1"
        result={result([
          { key: 'eob', label: 'Explanation of Benefits (EOB)', how_to_get: 'x', have: true },
          { key: 'itemized_bill', label: 'Itemized bill', how_to_get: 'y', have: true },
          { key: 'sbc', label: 'Summary of Benefits and Coverage (SBC)', how_to_get: 'z', have: true },
        ])}
      />,
    );
    expect(getByText('← Back to dashboard')).toBeTruthy();
    expect(getByText('All set — re-checking your audit')).toBeTruthy();
  });
});
