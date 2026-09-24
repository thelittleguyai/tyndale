import { describe, expect, it } from 'vitest';

import type { PayerCorpusEntry, PayerCorpusView } from '@tyndale/shared';

import { entryStatus, reverifyReminder } from './reverify';

const view = (over: Partial<PayerCorpusView>): PayerCorpusView => ({
  source: 'docs/research/portal_navigation_guide_2026-07-02.md',
  reverify_every_months: 3,
  today: '2026-09-24',
  next_due: '2026-10-02',
  overdue: 0,
  verified: 12,
  unverified: 20,
  payers: [],
  ...over,
});

describe('the quarterly re-verify reminder (portal guide: portals change)', () => {
  it('warns ahead of the due date, and counts the days', () => {
    expect(reverifyReminder(view({}))).toEqual({
      tone: 'soon',
      text: "Re-verify due 2026-10-02 — in 8 days. Re-check every verified path on the payer's own pages; portals change quarterly.",
    });
  });

  it('is loud once a verified path is past its quarter', () => {
    const r = reverifyReminder(view({ today: '2026-10-05', overdue: 12 }));
    expect(r?.tone).toBe('overdue');
    expect(r?.text).toMatch(/^12 verified paths are past the quarterly re-verify \(due 2026-10-02\)/);
  });

  it('stays quiet-but-present far from the date, and absent with nothing verified', () => {
    expect(reverifyReminder(view({ today: '2026-07-10' }))?.tone).toBe('ok');
    expect(reverifyReminder(view({ next_due: null }))).toBeNull();
    expect(reverifyReminder(undefined)).toBeNull();
  });
});

describe('an entry says whether members ever see it', () => {
  const e = (over: Partial<PayerCorpusEntry>): PayerCorpusEntry => ({
    document_type: 'accumulators', screen_id: null, verified: true, verified_on: '2026-07-02',
    due_on: '2026-10-02', overdue: false, source: 'public pages', claim: '', steps: ['Sign in.'],
    origin: 'portal_guide', ...over,
  });
  it('verified: when, and when again', () => {
    expect(entryStatus(e({}))).toBe('Verified 2026-07-02 · re-verify by 2026-10-02');
    expect(entryStatus(e({ overdue: true }))).toBe('Verified 2026-07-02 · re-verify by 2026-10-02 (OVERDUE)');
  });
  it('unverified: never shown', () => {
    expect(entryStatus(e({ verified: false, verified_on: null, due_on: null, steps: [] }))).toMatch(/never shown to members/);
  });
});
