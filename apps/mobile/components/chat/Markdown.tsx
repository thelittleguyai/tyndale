/**
 * ChatMarkdown — the SMALLEST renderer that stops users seeing raw markdown
 * (Brock's 2026-08-22 field test: literal **bold**, asterisk lists, pipe tables).
 *
 * Supports exactly four constructs: **bold**, *italic* / _italic_, ordered and
 * unordered lists, paragraph breaks. Everything else DEGRADES TO PLAIN TEXT —
 * heading hashes, blockquote markers, backticks, link syntax and pipe-table rows
 * are stripped to their words, never shown as syntax. No deps; universal (RN + web).
 *
 * Applies WITHIN a chunk's text only — the tier A/B/C block structure and the
 * citation chips around it are untouched (ChatMessage owns those).
 */

import { Text, View } from 'react-native';

type Inline = { text: string; bold?: boolean; italic?: boolean };
type Block =
  | { kind: 'paragraph'; lines: Inline[][] }
  | { kind: 'list'; ordered: boolean; items: Inline[][] };

const INLINE_RE = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|_[^_\n]+_)/g;
const ORDERED_RE = /^\s*(\d{1,2})[.)]\s+(.*)$/;
const UNORDERED_RE = /^\s*[-*•]\s+(.*)$/;
const TABLE_SEP_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;

/** Unknown constructs → plain words. Exported for tests. */
export function degradeToPlain(text: string): string {
  return text
    .split('\n')
    .filter((line) => !(TABLE_SEP_RE.test(line) && line.includes('-')))
    .map((line) => {
      if (TABLE_ROW_RE.test(line)) {
        return line
          .trim()
          .replace(/^\||\|$/g, '')
          .split('|')
          .map((c) => c.trim())
          .filter(Boolean)
          .join(' — ');
      }
      return line
        .replace(/^\s{0,3}#{1,6}\s+/, '') // headings
        .replace(/^\s*>\s?/, '') // blockquotes
        .replace(/```[a-z]*/g, '') // code fences
        .replace(/`([^`]*)`/g, '$1') // inline code
        .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1'); // links/images → their text
    })
    .join('\n');
}

export function parseInline(line: string): Inline[] {
  const out: Inline[] = [];
  for (const part of line.split(INLINE_RE)) {
    if (!part) continue;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      out.push({ text: part.slice(2, -2), bold: true });
    } else if (
      ((part.startsWith('*') && part.endsWith('*')) ||
        (part.startsWith('_') && part.endsWith('_'))) &&
      part.length > 2
    ) {
      out.push({ text: part.slice(1, -1), italic: true });
    } else {
      out.push({ text: part });
    }
  }
  return out;
}

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of degradeToPlain(text).split(/\n\s*\n/)) {
    const lines = raw.split('\n').filter((l) => l.trim().length > 0);
    if (!lines.length) continue;
    const allOrdered = lines.every((l) => ORDERED_RE.test(l));
    const allUnordered = lines.every((l) => UNORDERED_RE.test(l));
    if (allOrdered || allUnordered) {
      blocks.push({
        kind: 'list',
        ordered: allOrdered,
        items: lines.map((l) => {
          const m = allOrdered ? ORDERED_RE.exec(l) : UNORDERED_RE.exec(l);
          return parseInline((m ? m[allOrdered ? 2 : 1] : l).trim());
        }),
      });
    } else {
      blocks.push({ kind: 'paragraph', lines: lines.map((l) => parseInline(l.trim())) });
    }
  }
  return blocks;
}

function InlineRun({ runs }: { runs: Inline[] }) {
  return (
    <>
      {runs.map((r, i) => (
        <Text
          key={i}
          style={{
            ...(r.bold ? { fontWeight: '700' as const } : null),
            ...(r.italic ? { fontStyle: 'italic' as const } : null),
          }}
        >
          {r.text}
        </Text>
      ))}
    </>
  );
}

export function ChatMarkdown({ text, className }: { text: string; className: string }) {
  const blocks = parseBlocks(text);
  if (!blocks.length) return <Text className={className}>{text}</Text>;
  return (
    <View>
      {blocks.map((b, bi) =>
        b.kind === 'list' ? (
          <View key={bi} className={bi > 0 ? 'mt-2' : undefined}>
            {b.items.map((item, ii) => (
              <View key={ii} className="flex-row">
                <Text className={`${className} w-5`}>{b.ordered ? `${ii + 1}.` : '•'}</Text>
                <Text className={`${className} flex-1`}>
                  <InlineRun runs={item} />
                </Text>
              </View>
            ))}
          </View>
        ) : (
          <Text key={bi} className={bi > 0 ? `${className} mt-2` : className}>
            {b.lines.map((line, li) => (
              <Text key={li}>
                {li > 0 ? '\n' : ''}
                <InlineRun runs={line} />
              </Text>
            ))}
          </Text>
        ),
      )}
    </View>
  );
}
