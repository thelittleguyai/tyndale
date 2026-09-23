/**
 * The render-time control-line sanitizer (e2e re-test 2026-09-23 item 5): history persisted
 * before the server parser (2ac1e47) still carries raw `SUGGESTED:` / `CTA:` lines. The cases
 * are the SAME file the Python parser's suite runs — the two stay in lockstep by construction.
 */
import { render } from '@testing-library/react-native';

import type { Message } from '@tyndale/shared';

import { ChatMessage } from '../components/chat/ChatMessage';
import { chipsFor, hasControlLine, sanitizeControlLines } from '../lib/control-lines';

const shared = require('../../../runtime/tests/fixtures/control_line_cases.json') as {
  cases: { input: string; text: string; replies: string[]; cta: string | null }[];
};

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn() }) }));

describe('sanitizeControlLines — the Python parser, case for case', () => {
  it.each(shared.cases.map((c) => [c.input.slice(0, 40), c] as const))('%s', (_label, c) => {
    const got = sanitizeControlLines(c.input);
    expect(got.text).toBe(c.text);
    expect(got.replies).toEqual(c.replies);
    expect(got.cta).toBe(c.cta);
    expect(hasControlLine(got.text)).toBe(false);
  });

  it('leaves a message with no control line exactly as it is', () => {
    const text = '  Some prose.\n\n\n\nMore prose.  ';
    expect(sanitizeControlLines(text)).toEqual({ text, replies: [], cta: null, stripped: false });
  });
});

const FOOTER =
  'Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice.';

function oldMessage(overrides: Partial<Message> = {}): Message {
  return {
    message_id: 'm1',
    conversation_id: 'c1',
    sequence_number: 2,
    role: 'assistant',
    content: `Let's get your case started.\n\n\`\`\`\nCTA: create_case\n\`\`\`\nSUGGESTED: ["Yes, I have a bill", "No bill yet"]\n\n${FOOTER}`,
    content_chunks: [],
    citations: [],
    suggested_replies: [],
    status: 'complete',
    created_at: '2026-09-20T12:00:00Z',
    ...overrides,
  } as Message;
}

describe('ChatMessage renders old history clean', () => {
  it('no raw control line reaches the screen, and the old CTA line still becomes the button', () => {
    const { queryByText, getByText, toJSON } = render(
      <ChatMessage message={oldMessage()} conversationId="c1" onCitation={() => {}} />,
    );
    const rendered = JSON.stringify(toJSON());
    expect(rendered).not.toMatch(/SUGGESTED\s*:/);
    expect(rendered).not.toMatch(/CTA\s*:/);
    expect(rendered).not.toContain('```');
    expect(getByText(FOOTER, { exact: false })).toBeTruthy();
    expect(queryByText(/create a case|Upload documents/i)).toBeTruthy(); // CreateCaseCta
  });

  it('strips control lines inside tiered chunks too', () => {
    const { toJSON } = render(
      <ChatMessage
        message={oldMessage({
          content: 'x',
          content_chunks: [{ tier: 'A', text: 'Answer.\n`CTA: create_case`', citations: [] }],
        } as Partial<Message>)}
        conversationId="c1"
        onCitation={() => {}}
      />,
    );
    expect(JSON.stringify(toJSON())).not.toMatch(/CTA\s*:/);
  });

  it('the chips come from the old SUGGESTED line when the message has none of its own', () => {
    expect(chipsFor(oldMessage())).toEqual(['Yes, I have a bill', 'No bill yet']);
    expect(chipsFor(oldMessage({ suggested_replies: ['Mine'] }))).toEqual(['Mine']);
    expect(chipsFor(oldMessage({ content: 'Plain.' }))).toEqual([]);
  });
});

