import { parseSseBlock } from '../../lib/api-client';

describe('SSE event parsing (ChatStream)', () => {
  it('parses an event block into { event, data }', () => {
    const ev = parseSseBlock('event: token\ndata: {"delta":"hello","tier":"A"}');
    expect(ev).toEqual({ event: 'token', data: { delta: 'hello', tier: 'A' } });
  });

  it('returns null when there is no data line', () => {
    expect(parseSseBlock('event: done')).toBeNull();
  });

  it('parses the completion payload', () => {
    const ev = parseSseBlock(
      'event: assistant_message_completed\ndata: {"message_id":"m1","citations":[]}',
    );
    expect(ev?.event).toBe('assistant_message_completed');
    expect(ev?.data.message_id).toBe('m1');
  });
});
