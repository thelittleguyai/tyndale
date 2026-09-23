/**
 * Verification cards are tap-to-confirm (2026-09-23 minor): the heading carries the code and ONE
 * plain sentence; anything longer or more clinical moves under "Show what this usually looks
 * like". Pure, so both the encounter screen and the thread card split the same way.
 */
const MAX_HEADLINE_CHARS = 90;

export function splitTranslation(translation: string | null | undefined): { headline: string; rest: string | null } {
  const text = (translation ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return { headline: '', rest: null };
  const sentences = text.split(/(?<=[.!?])\s+/);
  let headline = sentences[0];
  let rest = sentences.slice(1).join(' ').trim();
  if (headline.length > MAX_HEADLINE_CHARS) {
    // one sentence, but a long clinical one: cut at the last clause boundary before the cap
    const cut = Math.max(headline.lastIndexOf(', ', MAX_HEADLINE_CHARS), headline.lastIndexOf(' — ', MAX_HEADLINE_CHARS), headline.lastIndexOf('; ', MAX_HEADLINE_CHARS));
    if (cut > 30) {
      rest = [headline.slice(cut + 1).trim(), rest].filter(Boolean).join(' ');
      headline = headline.slice(0, cut).trim();
    }
  }
  return { headline, rest: rest || null };
}
