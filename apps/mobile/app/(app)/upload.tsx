/**
 * Multi-document upload screen (Phase 2L — Brock feedback 1).
 *
 * Fixes the auto-submit-on-first-file bug: files are added to a QUEUE; nothing
 * is sent until the user taps Submit. Per the acceptance narrative ("Maya
 * uploads four crumpled photos"), the user can add bill + EOB + insurance card
 * + plan summary as one case-opening motion, see them listed, remove any, add
 * more, then submit all in one request.
 *
 * Web (the live app.tyndaleapp.net surface, which is what Brock used) is fully
 * wired via a multiple <input type="file">. Native picker + camera capture land
 * with the iOS/Android app (Phase 3) — adding expo-document-picker now would
 * require an npm install that ERESOLVEs on the react-native-worklets peer
 * conflict (DL-44), so native shows a "use the web" message for now.
 */

import { useRef, useState } from 'react';
import { Platform, Pressable, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { FileText, Plus, X } from 'lucide-react-native';

import { extractLineItems, uploadDocuments } from '../../lib/api-client';
import {
  ACCEPTED_UPLOAD_HINT,
  UPLOAD_ACCEPT_ATTR,
  partitionUploads,
} from '../../lib/upload-validation';
import { PressableScale } from '../../components/ui/PressableScale';
import { Screen } from '../../components/ui/Screen';
import { Button, ListRow } from '../../components/ui';

type Queued = { id: string; file: File; name: string; size: number };

function prettyBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadScreen() {
  const router = useRouter();
  // When present, attach to an existing case (e.g. "Add a document" from the needs_documents
  // checklist) instead of opening a new one.
  const { caseId } = useLocalSearchParams<{ caseId?: string }>();
  const [queue, setQueue] = useState<Queued[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const inputRef = useRef<any>(null);

  const pickFiles = () => inputRef.current?.click?.();

  const onPicked = (e: any) => {
    const picked: FileList | undefined = e?.target?.files;
    if (!picked || picked.length === 0) return;
    // Enforce the file-type allowlist on the client too (the accept="" attr is only a hint the
    // user can override). Rejected files never enter the queue; the server re-checks by content.
    const { accepted, rejectedNames } = partitionUploads(Array.from(picked) as File[]);
    const added: Queued[] = accepted.map((f: File) => ({
      id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 8)}`,
      file: f,
      name: f.name,
      size: f.size,
    }));
    setQueue((q) => [...q, ...added]);
    setError(
      rejectedNames.length
        ? `Skipped ${rejectedNames.join(', ')} — ${ACCEPTED_UPLOAD_HINT}`
        : null,
    );
    if (inputRef.current) inputRef.current.value = ''; // allow re-picking the same file
  };

  const remove = (id: string) => setQueue((q) => q.filter((x) => x.id !== id));

  const submitAll = async () => {
    if (queue.length === 0 || uploading) return;
    setError(null);
    setUploading(true);
    setProgress(`Uploading ${queue.length} document${queue.length === 1 ? '' : 's'}…`);
    try {
      const res = await uploadDocuments(queue.map((q) => q.file), caseId);
      if (caseId) {
        // Adding to an existing case (needs_documents checklist): the server re-runs the audit if
        // this completes the set. Return to the case's results screen — it polls the new status.
        router.replace(`/audit/${caseId}`);
        return;
      }
      if (res.chat_first) {
        // Chat-first (DL-91): the thread was bootstrapped server-side; the thread screen drives
        // extraction + renders the live status card. Classic flow is untouched when the flag is off.
        router.push(`/audit/${res.case_file_id}/thread`);
        return;
      }
      setProgress('Reading your documents…');
      await extractLineItems(res.case_file_id);
      router.push(`/audit/${res.case_file_id}/encounter`);
    } catch (err: any) {
      setError(err?.message ?? String(err));
      setUploading(false);
      setProgress(null);
    }
  };

  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 24, paddingTop: 32 }}>
      <Pressable
        onPress={() => router.push('/')}
        className="mb-5 self-start active:opacity-70"
      >
        <Text className="text-sm text-secondary hover:text-primary">← Back to dashboard</Text>
      </Pressable>

      <View className="mb-6">
        <Text className="text-title text-primary">Upload your documents</Text>
        <Text className="mt-1 text-body text-secondary">
          Add as many as you have — bills, EOBs, insurance cards, plan summaries. We sort them
          out for you.
        </Text>
      </View>

      {Platform.OS === 'web' ? (
        <>
          {/* Hidden DOM input (react-native-web renders this as a real <input>). */}
          <input
            ref={inputRef}
            type="file"
            accept={UPLOAD_ACCEPT_ATTR}
            multiple
            onChange={onPicked}
            style={{ display: 'none' }}
          />
          {queue.length === 0 ? (
            <PressableScale
              onPress={pickFiles}
              className="items-center rounded-2xl border-2 border-dashed border-hairline bg-surface p-8 shadow-card hover:border-accent"
            >
              <Plus size={24} color="var(--c-accent)" />
              <Text className="mt-2 text-base font-semibold text-primary">Add documents</Text>
              <Text className="mt-1 text-xs text-faint">PDF or image — pick one or several</Text>
            </PressableScale>
          ) : (
            <View className="gap-2">
              {queue.map((q) => (
                <ListRow
                  key={q.id}
                  leading={
                    <View className="h-9 w-9 items-center justify-center rounded-control bg-inset">
                      <FileText size={18} color="var(--c-text-primary)" />
                    </View>
                  }
                  title={q.name}
                  subtitle={prettyBytes(q.size)}
                  trailing={
                    <PressableScale
                      onPress={() => remove(q.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Remove ${q.name}`}
                      className="h-8 w-8 items-center justify-center rounded-full bg-inset"
                    >
                      <X size={16} color="var(--c-text-secondary)" />
                    </PressableScale>
                  }
                />
              ))}
              <PressableScale
                onPress={pickFiles}
                className="mt-1 flex-row items-center gap-2 self-start rounded-control bg-inset px-3 py-2"
              >
                <Plus size={16} color="var(--c-accent)" />
                <Text className="text-body font-medium text-accent">Add another</Text>
              </PressableScale>
            </View>
          )}
        </>
      ) : (
        <View className="rounded-2xl border border-hairline bg-surface p-6">
          <Text className="text-base text-secondary">
            Open Tyndale on the web to upload for now. The native file picker and camera capture
            arrive with the iOS/Android app.
          </Text>
        </View>
      )}

      <View className="mt-6">
        <Button
          variant="primary"
          disabled={queue.length === 0 || uploading}
          onPress={submitAll}
          label={
            uploading
              ? `Uploading ${queue.length}…`
              : queue.length === 0
                ? 'Select documents to start'
                : `Submit ${queue.length} document${queue.length === 1 ? '' : 's'}`
          }
        />
      </View>

      {progress ? <Text className="mt-4 text-sm text-accent">{progress}</Text> : null}
      {error ? <Text className="mt-4 text-sm text-danger">Upload failed: {error}</Text> : null}

      <Text className="mt-12 text-center text-xs text-faint">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial
        advice.
      </Text>
    </Screen>
  );
}
