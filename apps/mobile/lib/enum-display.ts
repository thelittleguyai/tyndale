/**
 * Enum → display-string mapping (redesign §3 bug fix). Finding action/recommendation values can
 * arrive as raw snake_case enums (e.g. `no_immediate_action_required`) that must NEVER render
 * verbatim on screen. `displayEnum` prefers a curated label, then humanizes any enum-looking token
 * to sentence case, and passes real prose through untouched (a recommendation like "Call the payer
 * to dispute…" has spaces, so it isn't mangled).
 */

/** Curated labels for known finding action enums — nicer than the mechanical humanization. */
export const FINDING_ACTION_LABELS: Record<string, string> = {
  no_immediate_action_required: 'No immediate action needed',
  monitor_only: 'Keep an eye on this',
  call_provider: 'Call the provider',
  call_payer: 'Call your insurer',
  file_appeal: 'File an appeal',
  request_itemized_bill: 'Request an itemized bill',
  dispute_charge: 'Dispute the charge',
};

// A raw enum token: 2+ lowercase/digit segments joined by underscores, no spaces.
const ENUM_TOKEN = /^[a-z0-9]+(?:_[a-z0-9]+)+$/;

/** Humanize a snake_case token to sentence case: `no_immediate_action_required` → `No immediate
 *  action required`. */
export function humanizeEnum(value: string): string {
  return value
    .split('_')
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(' ');
}

/**
 * Display string for a possibly-enum value: curated label → humanized token → unchanged prose.
 * Never returns raw snake_case.
 */
export function displayEnum(value: string, map: Record<string, string> = FINDING_ACTION_LABELS): string {
  const trimmed = value.trim();
  if (map[trimmed]) return map[trimmed];
  if (ENUM_TOKEN.test(trimmed)) return humanizeEnum(trimmed);
  return value; // already human-readable prose — leave as authored
}
