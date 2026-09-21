import { describe, expect, it } from 'vitest';

import type { ReviewState } from './api-client';
import { PENDING_STATES, QUEUE_PILLS, pillCount, pillLabel } from './review-queue-filters';

const COUNTS: Record<ReviewState, number> = {
  unreviewed: 14,
  in_review: 2,
  re_review: 3,
  approved: 61,
  disapproved: 6,
  cant_verify: 0,
};
const pill = (key: string) => QUEUE_PILLS.find((p) => p.key === key)!;

describe('queue state pills', () => {
  it('offers every review state exactly once, in the mockup order, between Pending and All', () => {
    expect(QUEUE_PILLS.map((p) => p.key)).toEqual([
      'pending', 'unreviewed', 'in_review', 'approved', 'disapproved', 'cant_verify', 're_review', 'all',
    ]);
    const single = QUEUE_PILLS.filter((p) => p.states !== 'all' && p.states.length === 1).map((p) => p.key);
    expect(new Set(single)).toEqual(new Set(Object.keys(COUNTS)));
  });

  it('sends the API the states it counts — a pill never lists a view other than its number', () => {
    for (const p of QUEUE_PILLS) {
      expect(p.value).toBe(p.states === 'all' ? '' : p.states.join(','));
    }
    expect(pill('pending').value).toBe(PENDING_STATES.join(','));
  });

  it('labels a pill with its count, a grouping with the sum, and a zero as zero', () => {
    expect(pillLabel(pill('unreviewed'), COUNTS)).toBe('Unreviewed · 14');
    expect(pillLabel(pill('pending'), COUNTS)).toBe('Pending · 19');
    expect(pillLabel(pill('all'), COUNTS)).toBe('All · 86');
    expect(pillLabel(pill('cant_verify'), COUNTS)).toBe("Can't verify · 0");
  });

  it('shows NO number while counts are unknown — never a made-up 0', () => {
    expect(pillCount(pill('approved'), null)).toBeNull();
    expect(pillLabel(pill('approved'), undefined)).toBe('Approved');
  });

  it('treats a state the server omitted as zero rather than NaN', () => {
    expect(pillCount(pill('pending'), { unreviewed: 4 })).toBe(4);
  });
});
