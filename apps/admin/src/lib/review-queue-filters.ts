import type { ReviewState } from './api-client';

// The queue's state filter — one definition for the count pills AND the narrow-width select,
// so the two can never list different views. Order and labels follow the mockup
// (docs/design/mockups/human_review_queue.svg); "Pending" and "All" are groupings the
// mockup doesn't draw: Pending is the default worklist, All is the audit view.

export const PENDING_STATES: ReviewState[] = ['unreviewed', 'in_review', 're_review'];

export interface QueuePill {
  key: string;
  label: string;
  /** The `state` query value: a comma-joined list, or '' for every state. */
  value: string;
  states: ReviewState[] | 'all';
}

const one = (state: ReviewState, label: string): QueuePill => ({ key: state, label, value: state, states: [state] });

export const QUEUE_PILLS: QueuePill[] = [
  { key: 'pending', label: 'Pending', value: PENDING_STATES.join(','), states: PENDING_STATES },
  one('unreviewed', 'Unreviewed'),
  one('in_review', 'In review'),
  one('approved', 'Approved'),
  one('disapproved', 'Disapproved'),
  one('cant_verify', "Can't verify"),
  one('re_review', 'Re-review'),
  { key: 'all', label: 'All', value: '', states: 'all' },
];

/** Rows this pill would list, or null while the counts haven't loaded (or the API predates
 *  `state_counts`) — an unknown count is shown as no count, never as 0. */
export function pillCount(pill: QueuePill, counts: Partial<Record<ReviewState, number>> | null | undefined): number | null {
  if (!counts) return null;
  const states = pill.states === 'all' ? (Object.keys(counts) as ReviewState[]) : pill.states;
  return states.reduce((n, s) => n + (counts[s] ?? 0), 0);
}

export function pillLabel(pill: QueuePill, counts: Partial<Record<ReviewState, number>> | null | undefined): string {
  const n = pillCount(pill, counts);
  return n === null ? pill.label : `${pill.label} · ${n}`;
}
