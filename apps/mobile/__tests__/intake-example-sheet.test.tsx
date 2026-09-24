/**
 * "See an example" (Brock 2026-09-21, decision 8 — doc 41). A drawn illustration shows only when
 * THIS build bundles its image (assets/examples is a build-time manifest), with Brock's numbered
 * legend as text beside it — never baked in. Without the image, the federal sample (SBC, MSN) keeps
 * its "look for this" steps; with neither, there is no button at all — never an empty sheet.
 */
import { fireEvent, render, within } from '@testing-library/react-native';
import { Linking } from 'react-native';

import type { IntakeExample } from '@tyndale/shared';

import { ExampleSheet, exampleShowable } from '../components/intake/IntakeSheets';

// this "build" bundles the EOB and MSN drawings only
jest.mock('../assets/examples', () => ({ EXAMPLE_IMAGES: { eob: 1, msn: 2 } }));
jest.mock('../lib/api-client', () => ({ emailIntakeHelp: jest.fn() }));

const CMS = { kind: 'external_pdf' as const, url: 'https://www.cms.gov/sample.pdf', publisher: 'CMS' };
const example = (over: Partial<IntakeExample>): IntakeExample => ({
  ask: 'x', title: 'An example', illustration: null, legend: [], callouts: [], asset: null,
  source_line: null, glosses: {}, ...over,
});
const drawnEob = example({
  ask: 'eob', title: 'An EOB',
  illustration: { slot: 'eob', aspect: 'portrait' },
  legend: ['Who got the care.', 'The date of the visit.', 'The **allowed amount** is the price your plan set.'],
  glosses: { coinsurance: 'Coinsurance is your share after the deductible.' },
});
const federalSbc = example({
  ask: 'sbc', title: 'A plan summary', callouts: ['Look for the deductible.', 'Look for the out-of-pocket limit.'],
  asset: CMS, source_line: 'This is a real sample from the federal government.',
});
const sheet = (ex: IntakeExample) =>
  render(<ExampleSheet example={ex} chrome={{ close: 'Close', open_sample: 'Open the sample' }} onClose={() => undefined} />);

describe('whether "See an example" is offered', () => {
  it('needs a bundled image or a federal sample — nothing else', () => {
    expect(exampleShowable(null)).toBe(false);
    expect(exampleShowable(drawnEob)).toBe(true);
    // the server says drawn, but this build does not carry the image and there is no sample
    expect(exampleShowable(example({ ask: 'itemized_bill', illustration: { slot: 'itemized_bill', aspect: 'portrait' }, legend: ['A line.'] }))).toBe(false);
    expect(exampleShowable(federalSbc)).toBe(true);
  });
});

describe('the sheet', () => {
  it('draws the illustration with Brock\'s legend, numbered to match its badges', () => {
    const r = sheet(drawnEob);
    expect(r.getByTestId('intake-example-image')).toBeTruthy();
    const legend = within(r.getByTestId('intake-example-legend'));
    expect(legend.getAllByText(/^[1-9]$/).map((n) => n.props.children)).toEqual([1, 2, 3]);
    expect(legend.getByText('Who got the care.')).toBeTruthy();
    expect(legend.getByText(/allowed amount/)).toBeTruthy();
    expect(r.queryByText(/\*\*/)).toBeNull(); // the bold is rendered, not shown as syntax
    expect(r.getByText('Coinsurance is your share after the deductible.')).toBeTruthy();
    expect(r.queryByTestId('intake-example-open')).toBeNull(); // a drawing has no sample to open
  });

  it('falls back to the federal sample, its steps and its source line', () => {
    const open = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const r = sheet(federalSbc);
    expect(r.queryByTestId('intake-example-image')).toBeNull();
    expect(r.getByText('Look for the out-of-pocket limit.')).toBeTruthy();
    expect(r.getByText('This is a real sample from the federal government.')).toBeTruthy();
    fireEvent.press(r.getByTestId('intake-example-open'));
    expect(open).toHaveBeenCalledWith(CMS.url);
  });

  it('a build without the new drawing still shows the whole federal sample', () => {
    // the runtime has flipped sbc to drawn; this tab still runs a bundle without sbc@2x.png
    const r = sheet({ ...federalSbc, illustration: { slot: 'sbc', aspect: 'portrait' }, legend: ['Your deductible.'] });
    expect(r.queryByTestId('intake-example-image')).toBeNull();
    expect(r.queryByText('Your deductible.')).toBeNull();
    expect(r.getByText('Look for the deductible.')).toBeTruthy();
    expect(r.getByText('This is a real sample from the federal government.')).toBeTruthy();
  });

  it('a drawn federal sample shows the drawing, and keeps the sample one tap away', () => {
    const r = sheet(example({
      ask: 'msn', title: 'A Medicare Summary Notice', illustration: { slot: 'msn', aspect: 'portrait' },
      legend: ['Your Medicare number.'], callouts: ['Look for "You may be billed".'], asset: CMS,
      source_line: 'This is a real sample from the federal government.',
    }));
    expect(r.getByTestId('intake-example-image')).toBeTruthy();
    expect(r.getByText('Your Medicare number.')).toBeTruthy();
    expect(r.queryByText('Look for "You may be billed".')).toBeNull();
    expect(r.queryByText('This is a real sample from the federal government.')).toBeNull();
    expect(r.getByTestId('intake-example-open')).toBeTruthy();
  });
});
