import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { Markdown, parseBlocks } from './markdown';

describe('Markdown (admin Analysis tab, M1)', () => {
  it('renders headings, bold, lists and rules instead of raw syntax', () => {
    const html = renderToStaticMarkup(
      <Markdown text={'## What I found\n\nThe **anesthesia** line is wrong.\n\n- one\n- two\n\n---\n\nFooter.'} />,
    );
    expect(html).not.toContain('##');
    expect(html).not.toContain('**');
    expect(html).not.toContain('---');
    expect(html).toContain('<strong');
    expect(html).toContain('<ul');
    expect(html).toContain('<hr');
    expect(html).toContain('What I found');
  });

  it('degrades unknown constructs to words and keeps plain text as one paragraph', () => {
    const blocks = parseBlocks('> quoted `code` [link](http://x)');
    expect(blocks).toEqual([{ kind: 'paragraph', lines: [[{ text: 'quoted code link' }]] }]);
    expect(renderToStaticMarkup(<Markdown text="plain" />)).toContain('plain');
  });
});
