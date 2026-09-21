import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { ReviewSettings } from '@/lib/api-client';
import { SamplingDialView, parseSamplePct, type DialLoad } from './sampling-dial';

const SETTINGS: ReviewSettings = {
  review_sample_pct: 40,
  env_default_pct: 100,
  triggers: { first_case: true, low_confidence: true, canary: false },
};
const noop = () => {};
const render = (load: DialLoad, over: { draft?: string; msg?: { text: string; bad: boolean } | null } = {}) =>
  renderToStaticMarkup(
    <SamplingDialView
      load={load}
      draft={over.draft ?? '40'}
      busy={false}
      msg={over.msg ?? null}
      onDraft={noop}
      onSave={noop}
      onRetry={noop}
    />,
  );

describe('SamplingDial', () => {
  it('never renders nothing — the deep-review bug was a dial that vanished on a failed load', () => {
    const states: DialLoad[] = [
      { status: 'loading' },
      { status: 'error', message: 'Failed to fetch' },
      { status: 'ready', settings: SETTINGS },
    ];
    for (const s of states) expect(render(s)).toContain('Sampling');
  });

  it('says it is loading', () => {
    expect(render({ status: 'loading' })).toContain('role="status"');
  });

  it('shows the failure as an alert, with the reason and a Retry', () => {
    const html = render({ status: 'error', message: 'Failed to fetch' });
    expect(html).toContain('role="alert"');
    expect(html).toContain('Failed to fetch');
    expect(html).toMatch(/<button[^>]*>Retry<\/button>/);
    expect(html).not.toContain('<input'); // no dial to type into when its value is unknown
  });

  it('shows the dial with only the ENABLED triggers, and Save disabled until the value changes', () => {
    const same = render({ status: 'ready', settings: SETTINGS });
    expect(same).toContain('value="40"');
    expect(same).toContain('first case · low confidence');
    expect(same).not.toContain('canary');
    expect(same).toMatch(/<button[^>]*disabled=""[^>]*>Save<\/button>/);
    expect(render({ status: 'ready', settings: SETTINGS }, { draft: '25' })).not.toMatch(/disabled=""[^>]*>Save</);
  });

  it('announces a failed save as an alert and a good one as a status', () => {
    const ready: DialLoad = { status: 'ready', settings: SETTINGS };
    expect(render(ready, { msg: { text: 'Not saved: 500', bad: true } })).toMatch(/role="alert"[^>]*>Not saved: 500/);
    expect(render(ready, { msg: { text: 'Saved', bad: false } })).toMatch(/role="status"[^>]*>Saved/);
  });

  it('parses a percent strictly — an empty box is not 0', () => {
    expect(parseSamplePct('0')).toBe(0);
    expect(parseSamplePct('100')).toBe(100);
    for (const bad of ['', ' ', '101', '-1', '12.5', 'ten']) expect(parseSamplePct(bad)).toBeNull();
  });
});
