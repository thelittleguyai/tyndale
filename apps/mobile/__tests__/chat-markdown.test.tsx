/** Item 1 (Brock 2026-08-22): assistant chunk text renders markdown for exactly
 *  bold / italic / lists / paragraphs; everything else degrades to plain words. */

import { render } from '@testing-library/react-native';

import { ChatMarkdown, degradeToPlain, parseBlocks, parseInline } from '../components/chat/Markdown';
import { ChatMessage } from '../components/chat/ChatMessage';

describe('ChatMarkdown', () => {
  it('renders **x** as bold, not as literal asterisks', () => {
    const { getByText, queryByText } = render(
      <ChatMarkdown text="A deductible is **what you pay first** each year." className="t" />,
    );
    const bold = getByText('what you pay first');
    expect(bold.props.style).toEqual(expect.objectContaining({ fontWeight: '700' }));
    expect(queryByText(/\*\*/)).toBeNull();
  });

  it('renders *italic* and _italic_', () => {
    const { getByText } = render(<ChatMarkdown text="Try *this* or _that_." className="t" />);
    expect(getByText('this').props.style).toEqual(expect.objectContaining({ fontStyle: 'italic' }));
    expect(getByText('that').props.style).toEqual(expect.objectContaining({ fontStyle: 'italic' }));
  });

  it('renders ordered and unordered lists as rows with markers', () => {
    const { getByText } = render(
      <ChatMarkdown text={'Steps:\n\n1. Call the payer\n2. Ask for the EOB\n\n- keep notes\n- stay calm'} className="t" />,
    );
    expect(getByText('1.')).toBeTruthy();
    expect(getByText('2.')).toBeTruthy();
    expect(getByText('Call the payer')).toBeTruthy();
    expect(getByText('keep notes')).toBeTruthy();
    expect(parseBlocks('1. a\n2. b')[0]).toEqual(expect.objectContaining({ kind: 'list', ordered: true }));
  });

  it('a pipe table produces no visible | characters', () => {
    const table = 'Compare:\n\n| Term | Meaning |\n|---|---|\n| Copay | flat fee |\n\nDone.';
    const { queryByText, getByText } = render(<ChatMarkdown text={table} className="t" />);
    expect(queryByText(/\|/)).toBeNull();
    expect(queryByText(/---/)).toBeNull();
    expect(getByText(/Copay — flat fee/)).toBeTruthy();
  });

  it('unknown constructs degrade to plain words, never raw syntax', () => {
    expect(degradeToPlain('## Heading\n> quoted\n`code` and [a link](https://x)')).toBe(
      'Heading\nquoted\ncode and a link',
    );
    expect(parseInline('plain **b** *i*')).toEqual([
      { text: 'plain ' },
      { text: 'b', bold: true },
      { text: ' ' },
      { text: 'i', italic: true },
    ]);
  });
});

describe('ChatMessage uses the renderer within chunks', () => {
  it('tier blocks render markdown; the raw SUGGESTED line never shows while streaming', () => {
    const msg = {
      message_id: 'm1',
      conversation_id: 'c1',
      sequence_number: 2,
      role: 'assistant' as const,
      content: 'Partial answer **so far**\nSUGGESTED: ["Yes", "No"]',
      content_chunks: null,
      status: 'streaming' as const,
      created_at: new Date().toISOString(),
    };
    const { getByText, queryByText } = render(
      <ChatMessage message={msg} conversationId="c1" onCitation={() => undefined} />,
    );
    expect(getByText('so far').props.style).toEqual(expect.objectContaining({ fontWeight: '700' }));
    expect(queryByText(/SUGGESTED/)).toBeNull();
  });
});
