/**
 * Camera-first capture (N1 · checklist C1 + C5, delta rows N1/B2).
 *
 * Three states: LIVE viewfinder with a framing guide → REVIEW of the frame just taken → the
 * page list, which can loop back for another page. Captured pages leave as `File`s and join the
 * normal upload queue, so everything downstream (magic-byte validation, classification,
 * extraction) treats a photo exactly like a picked file.
 *
 * ── Platform ────────────────────────────────────────────────────────────────────────────────
 * Web only today, via getUserMedia — and web is the live member surface (app.tyndaleapp.net).
 * The native camera needs `expo-camera`, which cannot be installed while DL-44's peer conflict
 * stands (`react-native-worklets@0.9.1` peers RN 0.83–0.86 against our 0.79.6, so any lockfile
 * regeneration ERESOLVEs). `isCaptureSupported()` is the single seam: when it returns false the
 * upload screen shows the picker alone, with no camera affordance to disappoint anyone. Wiring
 * Expo's camera in later means implementing one function, not rewriting this flow.
 *
 * ── What we do NOT claim ────────────────────────────────────────────────────────────────────
 * No "Looks readable" badge. `assessCapture` returns warnings we measured, never a pass — the
 * reasoning is in lib/capture.ts, and it is the whole reason this component exists rather than
 * the prototype's version. The guide frame is STATIC: we don't detect document edges, so an
 * animated "locking on" overlay would be a decoration pretending to be a capability.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, Pressable, Text, View } from 'react-native';
import { Camera, RotateCcw, X } from 'lucide-react-native';

import {
  CAPTURE_JPEG_QUALITY,
  MAX_CAPTURE_EDGE,
  assessCapture,
  capturePageNames,
  laplacianVariance,
  scaleToBounds,
  toGrayscale,
  BLUR_SAMPLE_EDGE,
  type CapturedPage,
} from '../../lib/capture';
import { Button } from '../ui';
import type { CapturedUpload } from './capture-types';

/** Can this build open a live viewfinder at all? False → the caller shows the picker alone. */
export function isCaptureSupported(): boolean {
  return (
    Platform.OS === 'web' &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === 'function' &&
    typeof document !== 'undefined'
  );
}

type Phase = 'starting' | 'live' | 'review' | 'denied' | 'unavailable';

/** The warning copy for a measured problem. Engineering-owned: each names the measurement that
 *  produced it, so it stays a statement of fact rather than a judgement about the photo. */
const WARNING_TEXT: Record<string, string> = {
  too_small: "This came out small — small print may not survive it. Retake, or use it anyway.",
  looks_blurry: "This looks out of focus. Retake, or use it anyway.",
};

/** Engineering fallbacks for the capture chrome. Each is replaced the moment its registry key
 *  carries authored copy; a key still holding an engineering placeholder is withheld by the copy
 *  route, so a button never reads "[PLACEHOLDER-eng] Retake". */
const FALLBACK = {
  looks_good: 'Use this photo',
  retake: 'Retake',
  add_page: 'Take another picture',
} as const;

export function CameraCapture({
  label = 'bill',
  copy = {},
  onDone,
  onClose,
  allowMultiPage = true,
}: {
  /** Filename stem + the thing being photographed ('bill', 'card'). */
  label?: string;
  /** Authored capture copy from GET /v1/copy/upload. A null/absent field falls back to the
   *  engineering label above — the viewfinder PROMPT has no fallback and simply doesn't render,
   *  because it's product voice rather than chrome and we don't write it for him. */
  copy?: Record<string, string | null | undefined>;
  /** Fires once with every captured page, in order, as upload-ready parts. */
  onDone: (files: CapturedUpload[]) => void;
  onClose: () => void;
  allowMultiPage?: boolean;
}) {
  const prompt = (label === 'card' ? copy.capture_prompt_card : copy.capture_prompt_bill) ?? null;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Seeded from the support probe rather than starting at 'starting': a build that can't open a
  // camera must never render the viewfinder markup at all, not even for one frame.
  const [phase, setPhase] = useState<Phase>(() =>
    isCaptureSupported() ? 'starting' : 'unavailable',
  );
  const [pages, setPages] = useState<CapturedPage[]>([]);
  const [pending, setPending] = useState<{ page: CapturedPage; blob: Blob } | null>(null);
  const blobsRef = useRef<Blob[]>([]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const start = useCallback(async () => {
    if (!isCaptureSupported()) {
      setPhase('unavailable');
      return;
    }
    try {
      // `environment` asks for the rear camera on a phone; a laptop just gives its only one.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setPhase('live');
    } catch {
      // Denied, or no camera present. Either way the answer is the same and we ask once.
      setPhase('denied');
    }
  }, []);

  useEffect(() => {
    void start();
    return stop;
  }, [start, stop]);

  /** Draw the current frame, measure it, and hold it for review. */
  const shoot = useCallback(async () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const { width, height } = scaleToBounds(video.videoWidth, video.videoHeight, MAX_CAPTURE_EDGE);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);

    // Blur is measured on a fixed-width copy so the threshold means the same thing on every
    // device — the Laplacian variance of the same scene scales with resolution.
    let blurVariance: number | null = null;
    try {
      const sample = scaleToBounds(width, height, BLUR_SAMPLE_EDGE);
      const sampleCanvas = document.createElement('canvas');
      sampleCanvas.width = sample.width;
      sampleCanvas.height = sample.height;
      const sampleCtx = sampleCanvas.getContext('2d');
      if (sampleCtx && sample.width >= 3 && sample.height >= 3) {
        sampleCtx.drawImage(canvas, 0, 0, sample.width, sample.height);
        const { data } = sampleCtx.getImageData(0, 0, sample.width, sample.height);
        const gray = toGrayscale(data, sample.width * sample.height);
        blurVariance = laplacianVariance(gray, sample.width, sample.height);
      }
    } catch {
      // Pixel access can be refused (a tainted canvas). No measurement is an honest null —
      // the review still offers retake, it just has nothing measured to warn about.
      blurVariance = null;
    }

    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', CAPTURE_JPEG_QUALITY),
    );
    if (!blob) return;
    setPending({
      blob,
      page: {
        id: `${Date.now()}-${pages.length}`,
        previewUri: URL.createObjectURL(blob),
        width,
        height,
        bytes: blob.size,
        assessment: assessCapture({ width, height, blurVariance }),
      },
    });
    setPhase('review');
  }, [pages.length]);

  const finishWith = useCallback(
    (blobs: Blob[]) => {
      const names = capturePageNames(blobs.length, label);
      stop();
      onDone(blobs.map((b, i) => new File([b], names[i], { type: 'image/jpeg' })));
    },
    [label, onDone, stop],
  );

  const keep = useCallback(() => {
    if (!pending) return;
    const blobs = [...blobsRef.current, pending.blob];
    blobsRef.current = blobs;
    setPages((p) => [...p, pending.page]);
    setPending(null);
    // Single-page surfaces (the insurance card) have nothing to loop for — keeping the photo IS
    // the confirmation, so we hand back rather than parking on an empty viewfinder.
    if (!allowMultiPage) {
      finishWith(blobs);
      return;
    }
    setPhase('live');
  }, [allowMultiPage, finishWith, pending]);

  const retake = useCallback(() => {
    if (pending) URL.revokeObjectURL(pending.page.previewUri);
    setPending(null);
    setPhase('live');
  }, [pending]);

  const finish = useCallback(() => finishWith(blobsRef.current), [finishWith]);

  const close = useCallback(() => {
    stop();
    onClose();
  }, [onClose, stop]);

  // Permission denied / no camera: say so once, hand back to the picker, and stop asking.
  if (phase === 'denied' || phase === 'unavailable') {
    return (
      <View className="rounded-2xl border border-hairline bg-surface p-5" testID="capture-unavailable">
        <Text className="text-body text-secondary">
          {phase === 'denied'
            ? "I can't reach your camera — you can pick a photo or PDF from your files instead."
            : 'Camera capture needs the web app on a phone — you can pick a photo or PDF instead.'}
        </Text>
        <Pressable
          onPress={close}
          className="mt-3 min-h-[44px] items-center justify-center self-start rounded-control bg-inset px-4"
          testID="capture-dismiss"
        >
          <Text className="text-body font-medium text-primary">Use the file picker</Text>
        </Pressable>
      </View>
    );
  }

  const warning = pending?.page.assessment.warning ?? null;

  return (
    <View className="absolute inset-0 z-50 bg-page" testID="camera-capture">
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="text-caption text-faint">
          {pages.length > 0 ? `Page ${pages.length + (pending ? 1 : 0)}` : 'Add your bill'}
        </Text>
        <Pressable
          onPress={close}
          className="min-h-[44px] min-w-[44px] items-center justify-center"
          testID="capture-close"
        >
          <X size={22} color="var(--c-text-secondary)" />
        </Pressable>
      </View>

      <View className="flex-1 px-5">
        <View className="relative w-full max-w-xl flex-1 self-center overflow-hidden rounded-2xl bg-navy">
          {/* The viewfinder. Hidden (not unmounted) during review so the stream keeps running —
              tearing the track down and back up between pages is slow and flickers. */}
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              display: phase === 'review' ? 'none' : 'block',
            }}
          />
          {phase === 'review' && pending ? (
            <img
              src={pending.page.previewUri}
              alt="The page you just captured"
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
          ) : null}

          {/* STATIC framing guide — a target to line the paper up against. It does not track the
              document (we don't detect edges), so it never moves or "locks on". */}
          {phase !== 'review' ? (
            <View pointerEvents="none" className="absolute inset-6 rounded-lg border-2 border-white/70" />
          ) : null}
        </View>

        {phase !== 'review' && prompt ? (
          <Text className="mt-4 text-center text-body text-secondary">{prompt}</Text>
        ) : null}

        {/* A warning states what we measured. There is no positive counterpart by design. */}
        {phase === 'review' && warning ? (
          <Text className="mt-4 text-center text-body text-warning" testID="capture-warning">
            {WARNING_TEXT[warning]}
          </Text>
        ) : null}
      </View>

      {/* One fixed button ROW below the preview (Brock 2026-08-22): actions sit side by
          side — secondary left, primary right — never hovering over the viewfinder. */}
      <View className="px-5 pb-10 pt-4">
        {phase === 'review' ? (
          <View className="flex-row gap-3">
            <Pressable
              onPress={retake}
              className="min-h-[48px] flex-row items-center justify-center gap-2 rounded-xl border border-hairline bg-surface px-4"
              testID="capture-retake"
            >
              <RotateCcw size={17} color="var(--c-text-secondary)" />
              <Text numberOfLines={1} className="text-body font-semibold text-secondary">
                {copy.capture_retake || FALLBACK.retake}
              </Text>
            </Pressable>
            <View className="flex-1">
              <Button
                variant="primary"
                label={copy.capture_looks_good || FALLBACK.looks_good}
                className="min-h-[48px]"
                onPress={keep}
                testID="capture-keep"
              />
            </View>
          </View>
        ) : (
          <View className="flex-row gap-3">
            {pages.length > 0 ? (
              <View>
                {/* Just "Done" — the banked count lives in the "Page N" header, and the count
                    suffix is what made this row truncate 'Take another picture' at 390pt. */}
                <Button
                  variant="secondary"
                  label="Done"
                  className="min-h-[56px]"
                  onPress={finish}
                  testID="capture-done"
                />
              </View>
            ) : null}
            <Pressable
              onPress={shoot}
              disabled={phase !== 'live'}
              accessibilityRole="button"
              accessibilityLabel="Take photo"
              className="min-h-[56px] flex-1 flex-row items-center justify-center gap-2 rounded-xl bg-accent px-4"
              testID="capture-shutter"
            >
              {/* pages>0: the label carries the meaning and the row is width-tight — the
                  glyph is what makes 'Take another picture' truncate at 390pt. */}
              {pages.length === 0 ? <Camera size={18} color="var(--c-on-accent)" /> : null}
              <Text numberOfLines={1} className="text-base font-bold text-on-accent">
                {pages.length > 0 ? copy.capture_add_page || FALLBACK.add_page : 'Take photo'}
              </Text>
            </Pressable>
          </View>
        )}
      </View>
    </View>
  );
}
