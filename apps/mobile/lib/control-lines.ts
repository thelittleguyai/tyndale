/**
 * The render-time sanitizer for chat control lines (e2e re-test 2026-09-23, item 5).
 *
 * The model ends a chat turn with `SUGGESTED: ["…", "…"]` (tap-to-reply chips) and/or
 * `CTA: create_case` (the create-a-case button). The server parses and strips them at
 * completion (runtime/app/agents/chat_format.py) — since 2ac1e47 anywhere in the message,
 * fenced or not. Messages persisted BEFORE that still carry the raw lines, and history renders
 * them. This is the same parse, client-side: every control line is removed from what renders,
 * and the chips / the button are synthesized from it when the message's own fields lack them.
 *
 * Kept in lockstep with the Python by ONE shared case file
 * (runtime/tests/fixtures/control_line_cases.json), run by both suites.
 */

export const MAX_SUGGESTED = 4;
export const MAX_SUGGESTED_WORDS = 5;
export const KNOWN_CTAS = new Set(['create_case']);

// A control line with the decoration the model tends to add: inline backticks, a same-line
// fence (```CTA: create_case```), bold, a trailing period. (chat_format._DECORATED_LINE_RE)
const DECORATED_LINE_RE =
  /^\s*(?:`{1,3}\s*\w*\s*)?(?:\*\*)?\s*(SUGGESTED|CTA)\s*:\s*(.*?)\s*(?:\*\*)?\s*`{0,3}\s*\.?\s*$/i;
const FENCE_RE = /^\s*`{3,}\s*\w*\s*$/;
// Anything that still STARTS like a control line (after up to 8 non-word characters: quote
// markers, bullets) — the validator's net. (chat_format._CONTROL_TOKEN_RE)
const CONTROL_TOKEN_RE = /^\W{0,8}(SUGGESTED|CTA)\s*:/i;
const ANY_CONTROL_RE = /^\W{0,8}(SUGGESTED|CTA)\s*:/im;

export interface SanitizedText {
  text: string;
  replies: string[];
  cta: string | null;
  /** true when anything was removed — the message carried a raw control line */
  stripped: boolean;
}

function cleanReply(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const s = value.split(/\s+/).filter(Boolean).join(' ');
  if (!s || s.split(' ').length > MAX_SUGGESTED_WORDS || s.length > 60) return null;
  return s;
}

/** The chips from a SUGGESTED payload, or null when it is not a JSON array of strings. */
function parseSuggested(raw: string): string[] | null {
  const body = raw.trim().replace(/^`+|`+$/g, '').trim();
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed)) return null;
  const replies: string[] = [];
  for (const item of parsed) {
    const cleaned = cleanReply(item);
    if (cleaned && !replies.includes(cleaned)) replies.push(cleaned);
    if (replies.length >= MAX_SUGGESTED) break;
  }
  return replies;
}

/** Drop fences left empty by a removed control line; collapse runs of blank lines. */
function tidy(lines: string[]): string {
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (FENCE_RE.test(lines[i])) {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j += 1;
      if (j < lines.length && FENCE_RE.test(lines[j])) {
        i = j + 1;
        continue;
      }
    }
    out.push(lines[i]);
    i += 1;
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

export function hasControlLine(text: string | null | undefined): boolean {
  return ANY_CONTROL_RE.test(text ?? '');
}

/**
 * Every control line, anywhere, in any order, fenced or decorated or bare: removed. The LAST
 * SUGGESTED that parses gives the chips; the last known CTA gives the button; a malformed or
 * unknown one is removed and gives nothing. Prose around them (the footer) stays.
 */
export function sanitizeControlLines(text: string | null | undefined): SanitizedText {
  const source = text ?? '';
  if (!hasControlLine(source)) return { text: source, replies: [], cta: null, stripped: false };
  const kept: string[] = [];
  let replies: string[] = [];
  let cta: string | null = null;
  for (const line of source.split('\n')) {
    const m = DECORATED_LINE_RE.exec(line);
    if (m) {
      const kind = m[1].toUpperCase();
      if (kind === 'SUGGESTED') {
        const found = parseSuggested(m[2]);
        if (found !== null) replies = found;
      } else {
        const name = m[2].trim().replace(/^`+|`+$/g, '').trim().replace(/\.$/, '').toLowerCase();
        if (KNOWN_CTAS.has(name)) cta = name;
      }
      continue;
    }
    if (CONTROL_TOKEN_RE.test(line)) continue; // the validator's net: never rendered
    kept.push(line);
  }
  return { text: tidy(kept), replies, cta, stripped: true };
}

/**
 * The tap-to-reply chips for a message: its own `suggested_replies`, or — for a message
 * persisted before the server parsed them — the ones its raw SUGGESTED line names.
 */
export function chipsFor(message: {
  suggested_replies?: string[] | null;
  content?: string | null;
  content_chunks?: { text: string }[] | null;
}): string[] {
  const own = (message.suggested_replies ?? []).filter((r) => typeof r === 'string' && r.trim());
  if (own.length) return own;
  const fromContent = sanitizeControlLines(message.content).replies;
  if (fromContent.length) return fromContent;
  for (const ch of [...(message.content_chunks ?? [])].reverse()) {
    const found = sanitizeControlLines(ch.text).replies;
    if (found.length) return found;
  }
  return [];
}
