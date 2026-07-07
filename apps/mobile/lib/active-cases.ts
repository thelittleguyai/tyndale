/**
 * Pure routing for the dashboard's status-aware Open Cases card (Item 1).
 *
 * The audit results screen polls until a terminal status, so it spins forever on a case that
 * hasn't been through encounter verification yet. Routing is therefore driven by the server's
 * status-derived `resume` field — never a single hard-coded path.
 */
import type { ActiveCase } from '@tyndale/shared';

export function activeCaseRoute(c: Pick<ActiveCase, 'case_file_id' | 'resume'>): string {
  return c.resume === 'encounter'
    ? `/audit/${c.case_file_id}/encounter`
    : `/audit/${c.case_file_id}`;
}
