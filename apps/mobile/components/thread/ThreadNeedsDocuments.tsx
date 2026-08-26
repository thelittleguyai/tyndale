/**
 * needs_documents in the chat thread (DL-91). TRUE have/need state per item (DL-90 per-item API),
 * per-item how-to, and an inline "add a document" scoped to THIS case. Satisfied items show
 * checked; once all are satisfied the upload route auto-re-runs the audit (wired in the
 * needs-documents UX fix) and the bridge renders the re-run in the thread.
 */
import { CheckCircle2, Circle, Plus } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

import type { CoverageChecklistItem, NeedsDocumentsPayload, UnlockMorePayload } from '@tyndale/shared';
import { saveCoverageInput } from '../../lib/api-client';

/** "What is this?" (image-3 item 3): a tap-to-expand explainer under any checklist item.
 *  Copy is registry-authored and server-rendered into the payload — nothing engineering-voiced. */
function Explainer({ text, itemKey }: { text?: string; itemKey: string }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <View className="ml-6">
      <Pressable
        onPress={() => setOpen((o) => !o)}
        className="min-h-[44px] flex-row items-center self-start"
        testID={`explainer-toggle-${itemKey}`}
      >
        <Text className="text-caption text-secondary underline">What is this?</Text>
      </Pressable>
      {open ? (
        <Text className="mb-1 text-body leading-6 text-secondary" testID={`explainer-text-${itemKey}`}>
          {text}
        </Text>
      ) : null}
    </View>
  );
}

const money = (v: number) =>
  `$${v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

/** One coverage-number / visit-confirm row. Tap opens the inline input (currency keyboard)
 *  or the candidate chips; SAVE is the only state change (D4(b)); "Not sure" is the honest
 *  opt-out. Saved state renders like the document items — check + strikethrough. */
function CoverageItemRow({
  item,
  caseFileId,
  suggested,
  onSaved,
}: {
  item: CoverageChecklistItem;
  caseFileId: string;
  /** A mapped free-text value (image-3 item 4): opens the row pre-filled — the Save tap
   *  is the confirming state change; the mapping itself never wrote anything. */
  suggested?: number | string | null;
  onSaved?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  useEffect(() => {
    if (suggested != null && item.value == null) {
      setOpen(true);
      setText(String(suggested));
    }
  }, [suggested, item.value]);
  const [savedValue, setSavedValue] = useState<number | string | null>(null);
  const [savedNotSure, setSavedNotSure] = useState(false);
  const [busy, setBusy] = useState(false);
  const value = savedValue ?? item.value;
  const notSure = savedNotSure || (item.not_sure && value == null);
  const done = value != null;

  const save = async (v?: number | string, asNotSure = false) => {
    if (busy) return;
    setBusy(true);
    try {
      await saveCoverageInput(caseFileId, item.key, v, asNotSure);
      if (asNotSure) setSavedNotSure(true);
      else if (v != null) setSavedValue(v);
      setOpen(false);
      onSaved?.();
    } catch {
      // The card re-renders from the server on the next thread refresh; a failed save
      // simply leaves the row open — no optimistic state to unwind.
    } finally {
      setBusy(false);
    }
  };

  const saveNumber = () => {
    const v = Number(text.replace(/[$,\s]/g, ''));
    if (Number.isFinite(v) && v >= 0) void save(Math.round(v * 100) / 100);
  };

  return (
    <View className="mt-3 border-t border-hairline pt-3">
      <Pressable
        onPress={() => (done ? null : setOpen((o) => !o))}
        className="min-h-[44px] flex-row items-center gap-2"
        testID={`coverage-item-${item.key}`}
      >
        {done ? (
          <CheckCircle2 size={18} color="var(--c-accent)" />
        ) : (
          <Circle size={18} color="var(--c-text-faint)" />
        )}
        <Text
          className={`flex-1 text-base font-bold ${done ? 'text-faint line-through' : 'text-primary'}`}
        >
          {item.label}
        </Text>
        {done ? (
          <Text className="text-body font-semibold text-secondary" testID={`coverage-value-${item.key}`}>
            {typeof value === 'number' ? money(value) : ''}
          </Text>
        ) : notSure ? (
          <Text className="text-caption text-faint">Not sure</Text>
        ) : null}
      </Pressable>
      {typeof value === 'string' && value ? (
        <Text className="ml-6 text-body text-secondary">{value}</Text>
      ) : null}
      {!done ? <Explainer text={item.explainer} itemKey={item.key} /> : null}
      {open && !done ? (
        <View className="ml-6 mt-2">
          {item.kind === 'visit_confirm' ? (
            <View className="mb-2 flex-row flex-wrap gap-2">
              {(item.candidates ?? []).map((c) => (
                <Pressable
                  key={c}
                  onPress={() => void save(c)}
                  className="min-h-[44px] justify-center rounded-full border border-accent px-4"
                  testID={`visit-candidate-${c}`}
                >
                  <Text className="text-body font-semibold text-accent">{c}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
          <View className="flex-row items-center gap-2">
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder={item.kind === 'number' ? '$0' : 'Something else — describe it'}
              inputMode={item.kind === 'number' ? 'decimal' : 'text'}
              className="min-h-[44px] flex-1 rounded-xl border border-hairline bg-surface px-3 text-body text-primary"
              testID={`coverage-input-${item.key}`}
            />
            <Pressable
              onPress={() => (item.kind === 'number' ? saveNumber() : text.trim() && void save(text.trim()))}
              disabled={busy}
              className="min-h-[44px] justify-center rounded-xl bg-accent px-4"
              testID={`coverage-save-${item.key}`}
            >
              <Text className="text-body font-bold text-on-accent">Save</Text>
            </Pressable>
          </View>
          <Pressable
            onPress={() => void save(undefined, true)}
            className="mt-1 min-h-[44px] justify-center self-start px-1"
            testID={`coverage-notsure-${item.key}`}
          >
            <Text className="text-body text-secondary underline">I'm not sure</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function ThreadNeedsDocuments({
  payload,
  caseFileId,
  unlock = false,
  suggestion,
  onCoverageSaved,
}: {
  payload: NeedsDocumentsPayload | UnlockMorePayload;
  caseFileId: string;
  /** Rung-2 unlock-more framing: the audit is DONE; these items deepen it. Same have/need
   *  component — only the surrounding voice differs (the intro/hint come from the server). */
  unlock?: boolean;
  suggestion?: { field: string; value: number | string } | null;
  onCoverageSaved?: () => void;
}) {
  const router = useRouter();
  const hint = unlock && 'item_hint' in payload ? payload.item_hint : null;
  return (
    <View
      className="my-2 w-full rounded-2xl border border-accent bg-accent-tint p-5"
      testID={unlock ? 'unlock-more-card' : 'needs-documents-card'}
    >
      <Text className="mb-3 text-base leading-6 text-primary">{payload.intro}</Text>
      {hint ? <Text className="mb-3 text-caption text-secondary">{hint}</Text> : null}
      {payload.items.map((d, i) => (
        <View key={d.key} className={i > 0 ? 'mt-3 border-t border-hairline pt-3' : ''}>
          <View className="mb-1 flex-row items-start gap-2">
            {d.have ? (
              <CheckCircle2 size={18} color="var(--c-accent)" />
            ) : (
              <Circle size={18} color="var(--c-text-faint)" />
            )}
            <Text
              className={`flex-1 text-base font-bold ${d.have ? 'text-faint line-through' : 'text-primary'}`}
            >
              {d.label}
            </Text>
          </View>
          {d.have ? null : (
            <>
              <Text className="ml-6 text-body leading-6 text-secondary">{d.how_to_get}</Text>
              <Pressable
                onPress={() =>
                  router.push({ pathname: '/upload', params: { caseId: caseFileId, expect: d.key } })
                }
                className="ml-6 mt-2 min-h-[44px] flex-row items-center gap-1.5 self-start rounded-xl border border-accent px-4"
                testID={`needs-add-${d.key}`}
              >
                <Plus size={15} color="var(--c-accent)" />
                <Text className="text-body font-semibold text-accent">Add</Text>
              </Pressable>
              <Explainer text={d.explainer} itemKey={d.key} />
            </>
          )}
        </View>
      ))}
      {(payload.coverage_items ?? []).map((c) => (
        <CoverageItemRow
          key={c.key}
          item={c}
          caseFileId={caseFileId}
          suggested={suggestion && suggestion.field === c.key ? suggestion.value : null}
          onSaved={onCoverageSaved}
        />
      ))}
      {/* Overall fallback — the per-item Add buttons above are the primary path (each opens
          the upload flow pre-tagged with the document type it should satisfy). */}
      <Pressable
        onPress={() => router.push({ pathname: '/upload', params: { caseId: caseFileId } })}
        className="mt-4 min-h-[44px] items-center justify-center rounded-xl bg-accent px-4 py-3"
      >
        <Text className="text-center text-base font-bold text-on-accent">Add a document</Text>
      </Pressable>
    </View>
  );
}
