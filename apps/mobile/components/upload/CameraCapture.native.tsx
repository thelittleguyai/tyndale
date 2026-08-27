/**
 * Native camera capture (iOS/Android) — the fill for the `isCaptureSupported()` seam that
 * DL-44 kept empty until the worklets removal (2026-08-17) unblocked `expo-camera`.
 *
 * Metro resolves this file on native; web keeps the getUserMedia implementation in
 * `CameraCapture.tsx`. Same flow (live → review → keep/retake → page loop), same honesty
 * rules: NO "Looks readable" badge, a STATIC guide frame (no fake edge detection), and only
 * MEASURED warnings — on native that is the resolution floor alone, because there is no
 * cheap pixel access for the blur metric; `assessCapture` receives blurVariance=null, which
 * it treats as "not measured", never as "sharp". Captured pages leave as {uri, name,
 * mimeType} parts — the shape `uploadDocuments` already sends for native files — so a
 * photographed bill joins the exact same upload path as a picked one.
 */
import { useCallback, useRef, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Camera, RotateCcw, X } from 'lucide-react-native';

import {
  MIN_OCR_EDGE,
  assessCapture,
  capturePageNames,
  type CaptureAssessment,
} from '../../lib/capture';
import { Button } from '../ui';
import type { CapturedUpload } from './capture-types';
import { useThemeColors } from '../../theme/useThemeColors';

/** Native builds support capture whenever expo-camera is present (it is, since DL-44 fell).
 *  Permission is asked in-flow — the component owns the denied state, same as web. */
export function isCaptureSupported(): boolean {
  return true;
}

const WARNING_TEXT: Record<string, string> = {
  too_small: "This came out small — small print may not survive it. Retake, or use it anyway.",
  looks_blurry: 'This looks out of focus. Retake, or use it anyway.',
};

const FALLBACK = {
  looks_good: 'Use this photo',
  retake: 'Retake',
  add_page: 'Take another picture',
} as const;

type Pending = { uri: string; assessment: CaptureAssessment };

export function CameraCapture({
  label = 'bill',
  copy = {},
  onDone,
  onClose,
  allowMultiPage = true,
}: {
  label?: string;
  copy?: Record<string, string | null | undefined>;
  onDone: (files: CapturedUpload[]) => void;
  onClose: () => void;
  allowMultiPage?: boolean;
}) {
  const tc = useThemeColors();
  const prompt = (label === 'card' ? copy.capture_prompt_card : copy.capture_prompt_bill) ?? null;
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [pages, setPages] = useState<string[]>([]);
  const urisRef = useRef<string[]>([]);

  const finishWith = useCallback(
    (uris: string[]) => {
      const names = capturePageNames(uris.length, label);
      onDone(uris.map((uri, i) => ({ uri, name: names[i], mimeType: 'image/jpeg' })));
    },
    [label, onDone],
  );

  const shoot = useCallback(async () => {
    const cam = cameraRef.current;
    if (!cam) return;
    // quality 0.7 mirrors the web path's JPEG setting; exif off — nothing needs it and a
    // GPS tag on a medical bill photo is data we should never even hold.
    const photo = await cam.takePictureAsync({ quality: 0.7, exif: false }).catch(() => null);
    if (!photo?.uri) return;
    setPending({
      uri: photo.uri,
      // Blur is NOT measured on native (no pixel access without heavy deps) — null, which
      // assessCapture treats as no measurement, not as a pass.
      assessment: assessCapture({
        width: photo.width ?? MIN_OCR_EDGE,
        height: photo.height ?? MIN_OCR_EDGE,
        blurVariance: null,
      }),
    });
  }, []);

  const keep = useCallback(() => {
    if (!pending) return;
    const uris = [...urisRef.current, pending.uri];
    urisRef.current = uris;
    setPages((p) => [...p, pending.uri]);
    setPending(null);
    if (!allowMultiPage) finishWith(uris);
  }, [allowMultiPage, finishWith, pending]);

  const insets = useSafeAreaInsets();

  if (!permission) return null; // permission state still loading — nothing to claim yet
  if (!permission.granted) {
    // Denied (or not yet asked): one ask, one honest hand-off, no nagging (C1).
    return (
      <View className="rounded-card border border-hairline bg-surface p-5" testID="capture-unavailable">
        <Text className="text-body text-secondary">
          {permission.canAskAgain
            ? 'Tyndale needs camera access to photograph your bill — or pick a photo from your files instead.'
            : "Camera access is off for Tyndale in your device settings — you can pick a photo or PDF instead."}
        </Text>
        <View className="mt-3 flex-row gap-2">
          {permission.canAskAgain ? (
            <Pressable
              onPress={() => void requestPermission()}
              className="min-h-[44px] items-center justify-center rounded-control bg-accent px-4"
              testID="capture-request-permission"
            >
              <Text className="text-body font-medium text-on-accent">Allow camera</Text>
            </Pressable>
          ) : null}
          <Pressable
            onPress={onClose}
            className="min-h-[44px] items-center justify-center rounded-control bg-inset px-4"
            testID="capture-dismiss"
          >
            <Text className="text-body font-medium text-primary">Use the file picker</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const warning = pending?.assessment.warning ?? null;

  return (
    <View className="absolute inset-0 z-50 bg-page" testID="camera-capture">
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="text-caption text-faint">
          {pages.length > 0 ? `Page ${pages.length + (pending ? 1 : 0)}` : 'Add your bill'}
        </Text>
        <Pressable onPress={onClose} className="min-h-[44px] min-w-[44px] items-center justify-center" testID="capture-close">
          <X size={22} color={tc.text.secondary} />
        </Pressable>
      </View>

      <View className="flex-1 px-5">
        <View className="relative w-full max-w-xl flex-1 self-center overflow-hidden rounded-moment bg-navy">
          {pending ? (
            <Image source={{ uri: pending.uri }} style={{ width: '100%', height: '100%' }} resizeMode="contain" />
          ) : (
            <CameraView ref={cameraRef} style={{ width: '100%', height: '100%' }} facing="back" />
          )}
          {/* STATIC framing guide — a target, not a tracker (no edge detection exists). */}
          {!pending ? (
            <View pointerEvents="none" className="absolute inset-6 rounded-card border-2 border-white/70" />
          ) : null}
        </View>

        {!pending && prompt ? (
          <Text className="mt-4 text-center text-body text-secondary">{prompt}</Text>
        ) : null}
        {pending && warning ? (
          <Text className="mt-4 text-center text-body text-warning" testID="capture-warning">
            {WARNING_TEXT[warning]}
          </Text>
        ) : null}
      </View>

      {/* One fixed button ROW below the preview (Brock 2026-08-22); safe-area aware. */}
      <View className="px-5 pt-4" style={{ paddingBottom: Math.max(insets.bottom, 24) }}>
        {pending ? (
          <View className="flex-row gap-3">
            <Pressable
              onPress={() => setPending(null)}
              className="min-h-[48px] flex-row items-center justify-center gap-2 rounded-control border border-hairline bg-surface px-4"
              testID="capture-retake"
            >
              <RotateCcw size={17} color={tc.text.secondary} />
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
                  onPress={() => finishWith(urisRef.current)}
                  testID="capture-done"
                />
              </View>
            ) : null}
            <Pressable
              onPress={() => void shoot()}
              accessibilityRole="button"
              accessibilityLabel="Take photo"
              className="min-h-[56px] flex-1 flex-row items-center justify-center gap-2 rounded-control bg-accent px-4"
              testID="capture-shutter"
            >
              {/* pages>0: the label carries the meaning and the row is width-tight — the
                  glyph is what makes 'Take another picture' truncate at 390pt. */}
              {pages.length === 0 ? <Camera size={18} color={tc.onAccent} /> : null}
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
