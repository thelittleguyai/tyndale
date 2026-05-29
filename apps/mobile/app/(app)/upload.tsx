/**
 * Walking-skeleton upload screen.
 *
 * Web: native <input type="file"> rendered as a styled label.
 * Native: expo-document-picker (Phase 2H wires camera + better UX).
 *
 * On successful POST /v1/upload, kicks the line-item extraction (Phase 2I)
 * then navigates to the encounter-verification screen, where the user confirms
 * each line item before the audit finalizes.
 */

import { useState } from 'react';
import { Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { extractLineItems, upload } from '../../lib/api-client';

export default function UploadScreen() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const handleWebFile = async (e: any) => {
    const f: File | undefined = e?.target?.files?.[0];
    if (!f) return;
    setError(null);
    setUploading(true);
    setProgress(`Uploading ${f.name} (${Math.round(f.size / 1024)} KB)…`);
    try {
      const res = await upload(f);
      setProgress('Reading your bill…');
      // Phase 2I: extract + translate line items, then go to encounter verification.
      await extractLineItems(res.case_file_id);
      setProgress(`Ready. Opening case ${res.case_file_id.slice(0, 8)}…`);
      router.push(`/audit/${res.case_file_id}/encounter`);
    } catch (err: any) {
      setError(err?.message ?? String(err));
      setUploading(false);
      setProgress(null);
    }
  };

  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ padding: 24, paddingTop: 32 }}
    >
      <Text className="mb-2 text-3xl font-bold text-white">Upload a bill</Text>
      <Text className="mb-6 text-base text-white/70">
        Upload a bill, EOB, or insurance card image. Tyndale will run an independent
        three-number audit (billed / insurer-claimed / Tyndale-computed).
      </Text>

      {Platform.OS === 'web' ? (
        <View className="rounded-2xl border-2 border-dashed border-white/20 bg-navy-mid p-8">
          <Text className="mb-4 text-center text-base text-white/80">
            Drop a PDF or image, or click to pick a file
          </Text>
          {/* react-native-web maps the DOM <input> through createElement on web */}
          <input
            type="file"
            accept="application/pdf,image/*"
            onChange={handleWebFile}
            disabled={uploading}
            style={{
              display: 'block',
              width: '100%',
              padding: 12,
              borderRadius: 12,
              background: '#0e2030',
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.15)',
            }}
          />
        </View>
      ) : (
        <View className="rounded-2xl border border-white/10 bg-navy-mid p-6">
          <Text className="text-base text-white/80">
            Native file picker wires in Phase 2H. For now, please use Tyndale on the web
            (`expo start --web`) to upload a bill.
          </Text>
        </View>
      )}

      {progress ? (
        <Text className="mt-6 text-sm text-sage">{progress}</Text>
      ) : null}
      {error ? (
        <Text className="mt-6 text-sm text-rose">Upload failed: {error}</Text>
      ) : null}

      <Pressable
        className="mt-10 rounded-xl bg-white/5 px-4 py-3"
        onPress={() => router.back()}
      >
        <Text className="text-center text-sm text-white/70">Back</Text>
      </Pressable>

      <Text className="mt-12 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </ScrollView>
  );
}
