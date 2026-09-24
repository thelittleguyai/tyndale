/**
 * The payer-instructions corpus's re-verify reminder (Admin › Knowledge). The portal guide's own
 * rule: re-verify quarterly, because portals change. A verified path a member relies on goes
 * stale silently; this says when the next check is due, and loudly once it is past.
 */
import type { PayerCorpusEntry, PayerCorpusView } from '@tyndale/shared';

export type ReverifyTone = 'overdue' | 'soon' | 'ok';

const DAY_MS = 86_400_000;

function daysUntil(today: string, due: string): number {
  return Math.round((Date.parse(`${due}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY_MS);
}

/** The banner over the corpus — null when nothing verified exists yet (no clock to keep). */
export function reverifyReminder(
  view: PayerCorpusView | null | undefined,
  soonDays = 30,
): { tone: ReverifyTone; text: string } | null {
  if (!view?.next_due) return null;
  if (view.overdue > 0) {
    const n = view.overdue === 1 ? '1 verified path is' : `${view.overdue} verified paths are`;
    return {
      tone: 'overdue',
      text: `${n} past the quarterly re-verify (due ${view.next_due}). Portals change — re-check them on the payer's own pages before members rely on them.`,
    };
  }
  const days = daysUntil(view.today, view.next_due);
  if (days <= soonDays) {
    return {
      tone: 'soon',
      text: `Re-verify due ${view.next_due} — in ${days} day${days === 1 ? '' : 's'}. Re-check every verified path on the payer's own pages; portals change quarterly.`,
    };
  }
  return { tone: 'ok', text: `Next re-verify due ${view.next_due}. Portals change — the guide re-verifies quarterly.` };
}

/** One entry's status line — an unverified one is never shown to members, and says so. */
export function entryStatus(e: PayerCorpusEntry): string {
  if (!e.verified) return 'UNVERIFIED — stored for the hands-on pass, never shown to members';
  const due = e.due_on ? ` · re-verify by ${e.due_on}${e.overdue ? ' (OVERDUE)' : ''}` : '';
  return `Verified ${e.verified_on ?? 'on an unknown date'}${due}`;
}
