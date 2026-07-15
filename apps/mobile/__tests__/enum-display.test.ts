import { displayEnum, humanizeEnum } from '../lib/enum-display';

describe('displayEnum — no raw snake_case reaches the screen (redesign §3 fix)', () => {
  it('maps a known finding action enum to a curated label', () => {
    expect(displayEnum('no_immediate_action_required')).toBe('No immediate action needed');
  });

  it('humanizes an unmapped enum token to sentence case', () => {
    expect(displayEnum('some_unmapped_enum_value')).toBe('Some unmapped enum value');
    expect(humanizeEnum('cost_sharing_miscalculation')).toBe('Cost sharing miscalculation');
  });

  it('passes real prose through untouched', () => {
    const prose = 'Call the payer to dispute the cost-sharing math.';
    expect(displayEnum(prose)).toBe(prose);
  });

  it('never returns a raw snake_case token', () => {
    for (const v of ['no_immediate_action_required', 'foo_bar', 'a_b_c_d', 'monitor_only']) {
      expect(displayEnum(v)).not.toMatch(/[a-z]_[a-z]/); // no snake_case survivors
    }
  });
});
