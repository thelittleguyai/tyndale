import { describe, expect, it } from 'vitest';

import { frontDoorActions, frontDoorSummary } from './front-door';

describe('front-door override (doc 40 §D)', () => {
  it('offers only the moves that change something', () => {
    expect(frontDoorActions({ override: null, cohort: 'default', resolved: 'chat_first', source: 'default' })).toEqual([
      'route_guided',
      'route_chat_first',
    ]);
    expect(frontDoorActions({ override: 'guided', cohort: 'default', resolved: 'guided', source: 'override' })).toEqual([
      'route_chat_first',
      'route_clear',
    ]);
    expect(frontDoorActions({ override: 'chat_first', cohort: 'guided', resolved: 'chat_first', source: 'override' })).toEqual([
      'route_guided',
      'route_clear',
    ]);
  });

  it('offers nothing against an older runtime that sends no view — never a button that 404s', () => {
    expect(frontDoorActions(undefined)).toEqual([]);
  });

  it('says what the user resolves to AND why — an override is not confused with the cohort', () => {
    expect(frontDoorSummary({ override: null, cohort: 'guided', resolved: 'guided', source: 'cohort' })).toBe(
      'Guided intake — cohort (cohort: guided)',
    );
    expect(frontDoorSummary({ override: 'chat_first', cohort: 'guided', resolved: 'chat_first', source: 'override' })).toBe(
      'Chat-first — admin override (cohort: guided)',
    );
    expect(frontDoorSummary({ override: null, cohort: null, resolved: 'chat_first', source: 'default' })).toBe(
      'Chat-first — env default',
    );
  });
});
