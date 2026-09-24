/**
 * The "See an example" illustrations bundled with the app (Brock 2026-09-21, decision 8 —
 * docs/build-kit/41_example_illustrations_spec.md). A BUILD-TIME manifest: one line per image
 * that EXISTS in this folder. A static require() of a missing file fails the Metro build, so this
 * list is the truth about what can be shown — never a runtime 404.
 *
 * Claude Code cannot generate images. When Phil drops one in (generated from doc 41's prompt):
 *   1. save it here as `<slot>@2x.png` — 1560×1950 portrait; 1560×975 for `insurance_card` and
 *      `summary_vs_itemized` (Metro resolves the @2x file from the plain `<slot>.png` require);
 *   2. add its line below;
 *   3. set `pending_asset=False` for that entry in runtime/app/intake/examples.py.
 * runtime/tests/test_example_manifest.py fails until all three agree.
 *
 * Slots: itemized_bill · summary_vs_itemized · insurance_card · eob · msn · sbc · accumulators ·
 * eob_timeline — all pending as of 2026-09-24.
 */
import type { ImageSourcePropType } from 'react-native';

export const EXAMPLE_IMAGES: Partial<Record<string, ImageSourcePropType>> = {
  // itemized_bill: require('./itemized_bill.png'),
};
