/**
 * Profile-onboarding UI helpers (CO-17): DOB validation (18+, no future), phone
 * auto-format, and a web card-upload control (image -> base64 -> POST). Same dark
 * navy / teal / sage tokens + >=44px touch targets as the rest of the app (CO-11).
 */

import { useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, Text, View } from 'react-native';

import { uploadInsuranceCard, type CardUploadResult } from './api-client';

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
  const inputRef = useRef<any>(null);
  const [state, setState] = useState<CardState>(initialDone ? 'done' : 'idle');
  const [msg, setMsg] = useState<string | null>(null);

  if (Platform.OS !== 'web') {
    return (
      <View className="rounded-2xl border border-white/10 bg-navy-soft p-4">
        <Text className="text-sm text-white/80">
          Open Tyndale on the web to add your card photo — the native camera arrives with the
          iOS / Android app.
        </Text>
      </View>
    );
  }

  const onPicked = async (e: any) => {
    const file: File | undefined = e?.target?.files?.[0];
    if (!file) return;
    if (!ALLOWED_CARD_MIME.includes(file.type)) {
      setState('error');
      setMsg('Please pick a JPG, PNG, or HEIC image.');
      return;
    }
    if (file.size > MAX_CARD_BYTES) {
      setState('error');
      setMsg('That image is over the 10MB limit.');
      return;
    }
    setState('uploading');
    setMsg(null);
    onUploadingChange?.(true);
    try {
      const dataUrl: string = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error('read failed'));
        reader.readAsDataURL(file);
      });
      const base64 = dataUrl.split(',')[1] ?? '';
      const result = await uploadInsuranceCard(side, base64, file.type, file.size);
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
      <Pressable
        onPress={() => inputRef.current?.click?.()}
        className={`min-h-[44px] items-center justify-center rounded-2xl border-2 border-dashed ${border} bg-navy-soft p-5`}
      >
        {state === 'uploading' ? (
          <ActivityIndicator color="#3DAA7E" />
        ) : (
          <Text className="text-sm font-semibold text-white">
            {state === 'done' ? `✓ ${label} added` : `Add the ${side} of your card`}
          </Text>
        )}
      </Pressable>
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
