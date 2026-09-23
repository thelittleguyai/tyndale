/**
 * The smallest markdown renderer the console needs (e2e 2026-09-23 M1): the Lead Planner's
 * narrative reached the Analysis tab as raw `##`, `**` and `---`. Headings, bold/italic,
 * lists, horizontal rules and paragraphs render; everything else degrades to plain words —
 * never to syntax. No dependencies; the same four-construct discipline as the mobile renderer.
 */
import { Fragment, type ReactNode } from 'react';

type Inline = { text: string; bold?: boolean; italic?: boolean };
type Block =
  | { kind: 'heading'; level: number; runs: Inline[] }
  | { kind: 'rule' }
  | { kind: 'list'; ordered: boolean; items: Inline[][] }
  | { kind: 'paragraph'; lines: Inline[][] };

const INLINE_RE = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|_[^_\n]+_)/g;
const ORDERED_RE = /^\s*(\d{1,2})[.)]\s+(.*)$/;
const UNORDERED_RE = /^\s*[-*•]\s+(.*)$/;
const HEADING_RE = /^\s{0,3}(#{1,6})\s+(.*)$/;
const RULE_RE = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/;

function plain(line: string): string {
  return line
    .replace(/^\s*>\s?/, '')
    .replace(/```[a-z]*/g, '')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1');
}

export function parseInline(line: string): Inline[] {
  const out: Inline[] = [];
  for (const part of line.split(INLINE_RE)) {
    if (!part) continue;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) out.push({ text: part.slice(2, -2), bold: true });
    else if (((part.startsWith('*') && part.endsWith('*')) || (part.startsWith('_') && part.endsWith('_'))) && part.length > 2)
      out.push({ text: part.slice(1, -1), italic: true });
    else out.push({ text: part });
  }
  return out;
}

export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of (text ?? '').split(/\n\s*\n/)) {
    const lines = raw.split('\n').map(plain).filter((l) => l.trim().length > 0);
    if (!lines.length) continue;
    // a heading or a rule on its own line splits the block
    let para: string[] = [];
    const flush = () => {
      if (!para.length) return;
      const allOrdered = para.every((l) => ORDERED_RE.test(l));
      const allUnordered = para.every((l) => UNORDERED_RE.test(l));
      if (allOrdered || allUnordered) {
        blocks.push({
          kind: 'list',
          ordered: allOrdered,
          items: para.map((l) => {
            const m = allOrdered ? ORDERED_RE.exec(l) : UNORDERED_RE.exec(l);
            return parseInline((m ? m[allOrdered ? 2 : 1] : l).trim());
          }),
        });
      } else {
        blocks.push({ kind: 'paragraph', lines: para.map((l) => parseInline(l.trim())) });
      }
      para = [];
    };
    for (const line of lines) {
      const h = HEADING_RE.exec(line);
      if (h) {
        flush();
        blocks.push({ kind: 'heading', level: h[1].length, runs: parseInline(h[2].trim()) });
      } else if (RULE_RE.test(line)) {
        flush();
        blocks.push({ kind: 'rule' });
      } else para.push(line);
    }
    flush();
  }
  return blocks;
}

function Runs({ runs }: { runs: Inline[] }) {
  return (
    <>
      {runs.map((r, i) => (
        <Fragment key={i}>
          {r.bold ? <strong className="font-semibold text-white">{r.text}</strong> : r.italic ? <em>{r.text}</em> : r.text}
        </Fragment>
      ))}
    </>
  );
}

export function Markdown({ text, className = 'text-sm leading-6 text-white/80' }: { text: string; className?: string }): ReactNode {
  const blocks = parseBlocks(text);
  if (!blocks.length) return <p className={className}>{text}</p>;
  return (
    <div className={className} data-testid="markdown">
      {blocks.map((b, i) => {
        if (b.kind === 'heading')
          return (
            <p key={i} className={`${i ? 'mt-3 ' : ''}font-semibold text-white ${b.level <= 2 ? 'text-base' : 'text-sm'}`}>
              <Runs runs={b.runs} />
            </p>
          );
        if (b.kind === 'rule') return <hr key={i} className="my-3 border-white/10" />;
        if (b.kind === 'list')
          return b.ordered ? (
            <ol key={i} className="my-2 list-decimal space-y-1 pl-5">
              {b.items.map((runs, j) => (
                <li key={j}>
                  <Runs runs={runs} />
                </li>
              ))}
            </ol>
          ) : (
            <ul key={i} className="my-2 list-disc space-y-1 pl-5">
              {b.items.map((runs, j) => (
                <li key={j}>
                  <Runs runs={runs} />
                </li>
              ))}
            </ul>
          );
        return (
          <p key={i} className={i ? 'mt-2' : undefined}>
            {b.lines.map((runs, j) => (
              <Fragment key={j}>
                {j ? <br /> : null}
                <Runs runs={runs} />
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
