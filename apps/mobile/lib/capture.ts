/**
 * Camera capture — the pure logic (N1 / checklist C1 + C5).
 *
 * Everything here is platform-free and unit-tested: sizing, compression bounds, the readability
 * assessment, and multi-page grouping. The surfaces that own pixels (web canvas today, an Expo
 * camera later) call in; nothing in here touches the DOM or React.
 *
 * ── The honesty rule (delta B2) ──────────────────────────────────────────────────────────────
 * The prototype stamps a green "Looks readable" badge on every capture, unconditionally. That is
 * a claim about the photo, and we only make claims we've checked, so this module does NOT return
 * a positive readability verdict at all. It returns either:
 *
 *   - a WARNING backed by a measurement we actually took (too small / measurably blurry), or
 *   - nothing, meaning "no problem detected" — which is not the same as "this will read".
 *
 * Two reasons for the asymmetry. First, the prompt's own bar for a badge is resolution + blur +
 * full-frame coverage, and coverage needs document-edge detection we don't have — so the badge is
 * unearned by its own definition. Second, and more important: passing a blur threshold doesn't
 * make a photo readable. Glare, a cut-off corner, a thumb over the total, 6pt print — all pass a
 * sharpness check and still fail OCR. A badge that says "readable" and is then contradicted by
 * "I couldn't read this" downstream costs more trust than it ever bought. A warning we can prove
 * costs nothing when it's wrong: the user just retakes a photo that would have worked.
 */

/** Longest edge kept after downscale. Matches the insurance-card path (profile-ui.tsx) — OCR
 *  doesn't need full sensor resolution, and this keeps a multi-page upload under the body cap. */
export const MAX_CAPTURE_EDGE = 1600;

/** JPEG quality for captured pages. Same as the card path. */
export const CAPTURE_JPEG_QUALITY = 0.7;

/** Below this longest edge, Document Intelligence starts losing small print (the line-item rows
 *  and the CPT column are the first to go). A capture under it is worth warning about — that is
 *  a measured fact about the file, not a guess about the photo. */
export const MIN_OCR_EDGE = 900;

/** Working edge for the blur metric. The Laplacian variance of an image scales with its
 *  resolution, so a fixed threshold is only meaningful at a fixed size — every frame is measured
 *  at this width before the variance is compared to BLUR_VARIANCE_FLOOR. */
export const BLUR_SAMPLE_EDGE = 640;

/** Variance-of-Laplacian floor at BLUR_SAMPLE_EDGE. Below it the frame is measurably soft.
 *  Deliberately conservative — a false "blurry" nags a user whose photo was fine, so the floor
 *  sits well under the value a typical in-focus phone photo of paper produces. */
export const BLUR_VARIANCE_FLOOR = 45;

export type CaptureWarning = 'too_small' | 'looks_blurry';

export type CaptureAssessment = {
  /** A problem we MEASURED, or null. Null never means "readable" — see the honesty rule. */
  warning: CaptureWarning | null;
  /** What was actually measured, so a caller (and a test) can see the basis for the verdict.
   *  `blurVariance` is null when the platform gave us no pixels to measure. */
  measured: { longestEdge: number; blurVariance: number | null };
};

/** Fit (w, h) inside `maxEdge` preserving aspect ratio. Never upscales. */
export function scaleToBounds(
  width: number,
  height: number,
  maxEdge: number = MAX_CAPTURE_EDGE,
): { width: number; height: number } {
  const longest = Math.max(width, height);
  if (longest <= 0) return { width: 0, height: 0 };
  const scale = Math.min(1, maxEdge / longest);
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** Rec. 601 luma from RGBA bytes. */
export function toGrayscale(rgba: ArrayLike<number>, pixelCount: number): Float64Array {
  const gray = new Float64Array(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    const o = i * 4;
    gray[i] = 0.299 * rgba[o] + 0.587 * rgba[o + 1] + 0.114 * rgba[o + 2];
  }
  return gray;
}

/**
 * Variance of the 3×3 Laplacian response — the standard sharpness proxy. A sharp edge produces a
 * large response; a blurred one produces almost none, so a soft frame has a low variance.
 *
 * Borders are skipped (the kernel needs all four neighbours). Returns 0 for an image too small to
 * convolve, which reads as "no measurement", not "blurry" — see `assessCapture`.
 */
export function laplacianVariance(gray: ArrayLike<number>, width: number, height: number): number {
  if (width < 3 || height < 3) return 0;
  let sum = 0;
  let sumSquares = 0;
  let n = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x;
      const response =
        gray[i - width] + gray[i + width] + gray[i - 1] + gray[i + 1] - 4 * gray[i];
      sum += response;
      sumSquares += response * response;
      n++;
    }
  }
  if (n === 0) return 0;
  const mean = sum / n;
  return sumSquares / n - mean * mean;
}

/**
 * The verdict for one captured frame. `blurVariance` is null on a platform that gave us no
 * pixels — there, the only real check available is the size one, and the blur half stays silent
 * rather than defaulting to a pass.
 *
 * Size is checked first: on a frame that's too small to read, "it's also blurry" is noise.
 */
export function assessCapture(input: {
  width: number;
  height: number;
  blurVariance?: number | null;
}): CaptureAssessment {
  const longestEdge = Math.max(input.width, input.height);
  const blurVariance = input.blurVariance ?? null;
  const measured = { longestEdge, blurVariance };
  if (longestEdge < MIN_OCR_EDGE) return { warning: 'too_small', measured };
  // A zero variance means "not measured" (frame too small to convolve), not "perfectly flat" —
  // treating it as blurry would warn on the strength of a measurement we never took.
  if (blurVariance !== null && blurVariance > 0 && blurVariance < BLUR_VARIANCE_FLOOR) {
    return { warning: 'looks_blurry', measured };
  }
  return { warning: null, measured };
}

/** One captured page, before it becomes an upload. */
export type CapturedPage = {
  id: string;
  /** JPEG bytes as a blob URL / file URI, for the review preview. */
  previewUri: string;
  width: number;
  height: number;
  bytes: number;
  assessment: CaptureAssessment;
};

/**
 * The filename for page `index` (0-based) of a multi-page capture.
 *
 * Grouping is by NAME because that's what survives the upload boundary: the server sees a list of
 * files, and pages of one paper document must arrive as an obvious, ordered set rather than three
 * unrelated photos. A single-page capture keeps a plain name — most captures are one page and
 * shouldn't look like a fragment of something bigger.
 */
export function capturePageName(index: number, totalPages: number, label = 'bill'): string {
  if (totalPages <= 1) return `${label}.jpg`;
  return `${label}-page-${String(index + 1).padStart(2, '0')}.jpg`;
}

/** Names for a whole captured document, in page order. */
export function capturePageNames(totalPages: number, label = 'bill'): string[] {
  return Array.from({ length: totalPages }, (_, i) => capturePageName(i, totalPages, label));
}

/** True when the compressed page is small enough to send. The server re-checks; this keeps a
 *  multi-page capture from being rejected after the user has already done the work. */
export function withinUploadBounds(bytes: number, maxBytes: number): boolean {
  return bytes > 0 && bytes <= maxBytes;
}
