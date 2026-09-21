// doc 40 §D — the per-user front-door override, as the admin user page presents it.
// Pure, so the rules are testable without mounting the page: only the moves that CHANGE
// something are offered, and the summary always says why the user resolves the way they do.
import type { AdminIntakeModeView } from '@tyndale/shared';

export type FrontDoorAction = 'route_guided' | 'route_chat_first' | 'route_clear';

const ROUTE_LABEL = { guided: 'Guided intake', chat_first: 'Chat-first' } as const;
const ROUTE_SOURCE = { override: 'admin override', cohort: 'cohort', default: 'env default' } as const;

/** An older runtime sends no view: offer nothing rather than a button that 404s. */
export function frontDoorActions(view: AdminIntakeModeView | undefined): FrontDoorAction[] {
  if (!view) return [];
  const out: FrontDoorAction[] = [];
  if (view.override !== 'guided') out.push('route_guided');
  if (view.override !== 'chat_first') out.push('route_chat_first');
  if (view.override) out.push('route_clear');
  return out;
}

export function frontDoorSummary(view: AdminIntakeModeView): string {
  const cohort = view.cohort ? ` (cohort: ${view.cohort})` : '';
  return `${ROUTE_LABEL[view.resolved]} — ${ROUTE_SOURCE[view.source]}${cohort}`;
}
