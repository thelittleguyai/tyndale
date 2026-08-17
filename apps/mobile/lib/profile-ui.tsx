/**
 * Profile-onboarding UI helpers (CO-17): DOB validation (18+, no future), phone
 * auto-format, and a web card-upload control (image -> base64 -> POST). Same dark
 * navy / teal / sage tokens + >=44px touch targets as the rest of the app (CO-11).
 */

import { useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, Text, View } from 'react-native';

import { uploadInsuranceCard, type CardUploadResult } from './api-client';
import { CameraCapture, isCaptureSupported } from '../components/upload/CameraCapture';
import { useThemeColors } from '../theme/useThemeColors';

export const ALLOWED_CARD_MIME = ['image/jpeg', 'image/jpg', 'image/png', 'image/heic', 'image/webp'];
export const MAX_CARD_BYTES = 10 * 1024 * 1024;
export const MIN_AGE_YEARS = 18;

/** Parse MM/DD/YYYY -> { iso: 'YYYY-MM-DD' } or an error. Blocks a future date and
 *  an age under 18 (DL-17). Empty input is neither valid nor an error (untouched). */
export function validateDob(input: string): { iso: string | null; error: string | null } {
  const s = (input ?? '').trim();
  if (!s) return { iso: null, error: null };
  const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return { iso: null, error: 'Use MM/DD/YYYY' };
  const mm = Number(m[1]);
  const dd = Number(m[2]);
  const yyyy = Number(m[3]);
  const d = new Date(yyyy, mm - 1, dd);
  if (d.getFullYear() !== yyyy || d.getMonth() !== mm - 1 || d.getDate() !== dd) {
    return { iso: null, error: 'That’s not a valid date' };
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (d > today) return { iso: null, error: 'Date of birth can’t be in the future' };
  let age = today.getFullYear() - yyyy;
  if (today.getMonth() < mm - 1 || (today.getMonth() === mm - 1 && today.getDate() < dd)) {
    age -= 1;
  }
  if (age < MIN_AGE_YEARS) {
    return { iso: null, error: `You must be at least ${MIN_AGE_YEARS} to use Tyndale` };
  }
  const iso = `${yyyy}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
  return { iso, error: null };
}

/** 'YYYY-MM-DD' -> 'MM/DD/YYYY' for prefilling the editable DOB field ('' if unset). */
export function isoToMdy(iso: string | null | undefined): string {
  const m = (iso ?? '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[2]}/${m[3]}/${m[1]}` : '';
}

/** Progressive (XXX) XXX-XXXX formatting as the user types. */
export function formatPhone(input: string): string {
  const digits = (input ?? '').replace(/\D/g, '').slice(0, 10);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

export type CardState = 'idle' | 'uploading' | 'done' | 'partial' | 'error';

const MAX_IMAGE_EDGE = 1600; // longest edge after downscale
const JPEG_QUALITY = 0.7;

async function fileToBase64(file: Blob): Promise<string> {
  const dataUrl: string = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('read failed'));
    reader.readAsDataURL(file);
  });
  return dataUrl.split(',')[1] ?? '';
}

/** Downscale + JPEG-compress a picked image on web (canvas) before upload — card OCR
 *  doesn't need full resolution, and this keeps the base64 body well under the upload
 *  cap (CO-18). Falls back to the original bytes if the canvas path is unavailable
 *  or fails (the server's size cap still protects us). */
async function compressImage(
  file: File,
): Promise<{ base64: string; mime: string; size: number }> {
  try {
    if (typeof document === 'undefined' || typeof createImageBitmap !== 'function') {
      return { base64: await fileToBase64(file), mime: file.type, size: file.size };
    }
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(bitmap.width, bitmap.height));
    const w = Math.round(bitmap.width * scale);
    const h = Math.round(bitmap.height * scale);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('no 2d context');
    ctx.drawImage(bitmap, 0, 0, w, h);
    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', JPEG_QUALITY),
    );
    if (!blob) throw new Error('toBlob failed');
    return { base64: await fileToBase64(blob), mime: 'image/jpeg', size: blob.size };
  } catch {
    return { base64: await fileToBase64(file), mime: file.type, size: file.size };
  }
}

/** Web image picker: pick -> base64 -> POST /v1/insurance/card/upload. Native shows a
 *  "use the web app" note (mirrors the intake UploadField until the native camera lands). */
export function CardUpload({
  side,
  initialDone = false,
  onResult,
  onUploadingChange,
}: {
  side: 'front' | 'back';
  initialDone?: boolean;
  onResult?: (r: CardUploadResult) => void;
  onUploadingChange?: (uploading: boolean) => void;
}) {
  const c = useThemeColors();
  const inputRef = useRef<any>(null);
  const [state, setState] = useState<CardState>(initialDone ? 'done' : 'idle');
  const [msg, setMsg] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [cameraOffered] = useState(() => isCaptureSupported());

  if (Platform.OS !== 'web') {
    return (
      <View className="rounded-2xl border border-white/10 bg-navy-soft p-4">
        <Text className="text-body text-white/80">
          Open Tyndale on the web to add your card photo — the native camera arrives with the
          iOS / Android app.
        </Text>
      </View>
    );
  }

  /** The one upload path for a card image, whether it was picked or photographed (N1 item 5). */
  const uploadFile = async (file: File) => {
    if (!ALLOWED_CARD_MIME.includes(file.type)) {
      setState('error');
      setMsg('Please pick a JPG, PNG, or HEIC image.');
      return;
    }
    setState('uploading');
    setMsg(null);
    onUploadingChange?.(true);
    try {
      // Downscale + compress first (CO-18): card OCR doesn't need full resolution,
      // and this keeps the base64 body well under the cap even for high-res photos.
      const { base64, mime, size } = await compressImage(file);
      if (size > MAX_CARD_BYTES) {
        setState('error');
        setMsg('That image is too large even after compression — try a smaller photo.');
        return;
      }
      const result = await uploadInsuranceCard(side, base64, mime, size);
      const ok = ['extracted', 'merged'].includes(result.extraction_status);
      setState(ok ? 'done' : 'partial');
      setMsg(
        ok
          ? 'Got it — your card details were read.'
          : "Saved, but I couldn't read all of it — you can re-take it or fill the rest in.",
      );
      onResult?.(result);
    } catch {
      setState('error');
      setMsg("We couldn't upload that — check your connection and try again.");
    } finally {
      onUploadingChange?.(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const onPicked = (e: any) => {
    const file: File | undefined = e?.target?.files?.[0];
    if (file) void uploadFile(file);
  };

  const border =
    state === 'done'
      ? 'border-sage/50'
      : state === 'error'
        ? 'border-rose/50'
        : state === 'partial'
          ? 'border-amber/50'
          : 'border-white/20';
  const label = side === 'front' ? 'Front of card' : 'Back of card';

  return (
    <View>
      {/* react-native-web renders this as a real DOM <input>. */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={onPicked}
        style={{ display: 'none' }}
      />
      {/* N1 item 5 — the card reuses the SAME capture component as the bill, single-page. A card
          is one side per capture, so keeping the photo IS the confirmation; there's no page loop. */}
      {cameraOffered ? (
        <Pressable
          onPress={() => setCapturing(true)}
          accessibilityRole="button"
          className="mb-2 min-h-[44px] flex-row items-center justify-center gap-2 rounded-2xl bg-accent px-4"
          testID={`card-capture-${side}`}
        >
          <Text className="text-body font-semibold text-on-accent">
            Take a photo of the {side}
          </Text>
        </Pressable>
      ) : null}
      <Pressable
        onPress={() => inputRef.current?.click?.()}
        className={`min-h-[44px] items-center justify-center rounded-2xl border-2 border-dashed ${border} bg-navy-soft p-5`}
      >
        {state === 'uploading' ? (
          <ActivityIndicator color={c.accent} />
        ) : (
          <Text className="text-body font-semibold text-white">
            {state === 'done'
              ? `✓ ${label} added`
              : cameraOffered
                ? `Or pick a file for the ${side}`
                : `Add the ${side} of your card`}
          </Text>
        )}
      </Pressable>
      {capturing ? (
        <CameraCapture
          label="card"
          allowMultiPage={false}
          onDone={(files) => {
            setCapturing(false);
            if (files[0]) void uploadFile(files[0]);
          }}
          onClose={() => setCapturing(false)}
        />
      ) : null}
      {msg ? (
        <Text
          className={`mt-2 text-xs ${
            state === 'error' ? 'text-rose' : state === 'partial' ? 'text-amber' : 'text-sage'
          }`}
        >
          {msg}
        </Text>
      ) : null}
    </View>
  );
}
