/**
 * Camera capture logic (N1 · C1/C5, delta B2).
 *
 * The load-bearing test in this file is `assessCapture never returns a positive verdict` — that
 * is the whole delta-B2 rule expressed as code. Everything else supports it.
 */
import {
  BLUR_VARIANCE_FLOOR,
  MAX_CAPTURE_EDGE,
  MIN_OCR_EDGE,
  assessCapture,
  capturePageName,
  capturePageNames,
  laplacianVariance,
  scaleToBounds,
  toGrayscale,
  withinUploadBounds,
} from '../lib/capture';

// --- sizing / compression bounds -------------------------------------------------------
describe('scaleToBounds', () => {
  it('fits the longest edge and keeps the aspect ratio', () => {
    expect(scaleToBounds(4032, 3024, 1600)).toEqual({ width: 1600, height: 1200 });
    expect(scaleToBounds(3024, 4032, 1600)).toEqual({ width: 1200, height: 1600 });
  });

  it('never upscales a photo that is already small', () => {
    expect(scaleToBounds(800, 600, 1600)).toEqual({ width: 800, height: 600 });
  });

  it('degrades to zero rather than dividing by zero', () => {
    expect(scaleToBounds(0, 0, 1600)).toEqual({ width: 0, height: 0 });
  });

  it('defaults to the shared capture bound', () => {
    expect(scaleToBounds(4000, 3000).width).toBe(MAX_CAPTURE_EDGE);
  });
});

describe('withinUploadBounds', () => {
  it('accepts a normal page and rejects an empty or oversized one', () => {
    expect(withinUploadBounds(500_000, 20 * 1024 * 1024)).toBe(true);
    expect(withinUploadBounds(20 * 1024 * 1024, 20 * 1024 * 1024)).toBe(true); // the cap itself
    expect(withinUploadBounds(20 * 1024 * 1024 + 1, 20 * 1024 * 1024)).toBe(false);
    expect(withinUploadBounds(0, 20 * 1024 * 1024)).toBe(false);
  });
});

// --- the blur metric --------------------------------------------------------------------
/** A synthetic image: vertical stripes every `period` px, blurred by averaging over `blur` px. */
function stripes(width: number, height: number, period: number, blur = 1): Float64Array {
  const out = new Float64Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0;
      for (let k = 0; k < blur; k++) {
        sum += Math.floor((x + k) / period) % 2 === 0 ? 255 : 0;
      }
      out[y * width + x] = sum / blur;
    }
  }
  return out;
}

describe('laplacianVariance', () => {
  it('is high for a sharp edge pattern and low for the same pattern blurred', () => {
    const sharp = laplacianVariance(stripes(64, 64, 8, 1), 64, 64);
    const blurred = laplacianVariance(stripes(64, 64, 8, 9), 64, 64);
    expect(sharp).toBeGreaterThan(blurred);
    expect(sharp).toBeGreaterThan(BLUR_VARIANCE_FLOOR);
  });

  it('is zero for a flat field — no edges, no response', () => {
    expect(laplacianVariance(new Float64Array(64 * 64).fill(128), 64, 64)).toBeCloseTo(0);
  });

  it('returns 0 (= "not measured") rather than throwing on an image too small to convolve', () => {
    expect(laplacianVariance(new Float64Array(4), 2, 2)).toBe(0);
  });
});

describe('toGrayscale', () => {
  it('applies Rec. 601 luma weights', () => {
    // one white pixel, one black, one pure red
    const rgba = [255, 255, 255, 255, 0, 0, 0, 255, 255, 0, 0, 255];
    const gray = toGrayscale(rgba, 3);
    expect(gray[0]).toBeCloseTo(255);
    expect(gray[1]).toBeCloseTo(0);
    expect(gray[2]).toBeCloseTo(76.245);
  });
});

// --- THE honesty rule (delta B2) --------------------------------------------------------
describe('assessCapture', () => {
  const big = { width: 1600, height: 1200 };

  it('NEVER returns a positive readability verdict — only a measured problem, or nothing', () => {
    // The full cross-product of inputs: no combination yields a "this is readable" signal,
    // because the type has no field that could carry one. A future edit that adds an
    // `ok: true` to please the prototype's badge has to delete this test to do it.
    for (const blurVariance of [null, 0, 1, BLUR_VARIANCE_FLOOR, 5000]) {
      const result = assessCapture({ ...big, blurVariance });
      expect(Object.keys(result).sort()).toEqual(['measured', 'warning']);
      expect(result.warning === null || typeof result.warning === 'string').toBe(true);
    }
  });

  it('warns when the frame is below the OCR floor', () => {
    const r = assessCapture({ width: MIN_OCR_EDGE - 1, height: 400, blurVariance: 9999 });
    expect(r.warning).toBe('too_small');
  });

  it('warns when the frame is measurably soft', () => {
    const r = assessCapture({ ...big, blurVariance: BLUR_VARIANCE_FLOOR - 1 });
    expect(r.warning).toBe('looks_blurry');
  });

  it('stays silent when the measurements show no problem', () => {
    expect(assessCapture({ ...big, blurVariance: BLUR_VARIANCE_FLOOR + 1 }).warning).toBeNull();
    expect(assessCapture({ ...big, blurVariance: 9999 }).warning).toBeNull();
  });

  it('does not warn about blur when there was no blur measurement', () => {
    // A platform that gave us no pixels must not be treated as "sharp" OR as "blurry" — the
    // absence of a measurement is not evidence in either direction.
    expect(assessCapture({ ...big, blurVariance: null }).warning).toBeNull();
    expect(assessCapture({ ...big }).warning).toBeNull();
    expect(assessCapture({ ...big, blurVariance: 0 }).warning).toBeNull();
  });

  it('reports size before blur — "also blurry" is noise on a frame too small to read', () => {
    const r = assessCapture({ width: 320, height: 240, blurVariance: 1 });
    expect(r.warning).toBe('too_small');
  });

  it('exposes what was actually measured, so the verdict can be checked', () => {
    const r = assessCapture({ width: 1600, height: 1200, blurVariance: 12.5 });
    expect(r.measured).toEqual({ longestEdge: 1600, blurVariance: 12.5 });
  });
});

// --- multi-page grouping ----------------------------------------------------------------
describe('page naming', () => {
  it('leaves a single-page capture unnumbered', () => {
    expect(capturePageName(0, 1)).toBe('bill.jpg');
    expect(capturePageNames(1)).toEqual(['bill.jpg']);
  });

  it('numbers a multi-page capture in order, zero-padded so it sorts', () => {
    expect(capturePageNames(3)).toEqual(['bill-page-01.jpg', 'bill-page-02.jpg', 'bill-page-03.jpg']);
  });

  it('sorts correctly past nine pages', () => {
    const names = capturePageNames(11);
    expect([...names].sort()).toEqual(names);
  });

  it('carries the label so a card capture is not named "bill"', () => {
    expect(capturePageNames(2, 'card')).toEqual(['card-page-01.jpg', 'card-page-02.jpg']);
  });
});
