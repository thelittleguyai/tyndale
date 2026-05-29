/**
 * Encounter-verification screen (Phase 2I / L07).
 *
 * Bill Detective has translated each charged line item into plain language.
 * The user confirms each against their lived experience of the visit:
 * yes / no / not sure. The framing is "Tyndale double-checking on your behalf,"
 * NOT an interrogation. "Not sure" is a real, non-pressured option.
 *
 * HARD LINE (refusals.md): the translations describe WHAT HAPPENED — facts the
 * user can verify — never a clinical judgment about whether a service was
 * necessary. That discipline lives in Bill Detective's translate-mode prompt;
 * this screen just renders what it produced.
 *
 * On "Continue to audit": POST all confirmations (kicks finalize in the
 * background) and navigate to the results screen, which polls until complete.
 */

import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import {
  ExtractResult,
  LineItem,
  LineItemResponse,
  getLineItems,
  submitConfirmations,
} from '../../../../lib/api-client';

type Draft = { response: LineItemResponse | null; user_note: string };

export default function EncounterVerificationScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ case_file_id: string }>();
  const case_file_id = String(params.case_file_id);

  const [extract, setExtract] = useState<ExtractResult | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getLineItems(case_file_id)
      .then((r) => {
        setExtract(r);
        const init: Record<string, Draft> = {};
        for (const li of r.line_items) init[li.line_item_id] = { response: null, user_note: '' };
        setDrafts(init);
      })
      .catch((e) => setError(e?.message ?? String(e)));
  }, [case_file_id]);

  const lineItems = extract?.line_items ?? [];
  const confirmedCount = useMemo(
    () => Object.values(drafts).filter((d) => d.response).length,
    [drafts],
  );
  const allConfirmed = lineItems.length > 0 && confirmedCount === lineItems.length;

  const setResponse = (id: string, response: LineItemResponse) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], response } }));
  const setNote = (id: string, user_note: string) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], user_note } }));

  const onContinue = async () => {
    if (!allConfirmed || submitting) return;
    setSubmitting(true);
    try {
      const confirmations = lineItems.map((li) => ({
        line_item_id: li.line_item_id,
        response: drafts[li.line_item_id].response as LineItemResponse,
        user_note: drafts[li.line_item_id].user_note || null,
      }));
      await submitConfirmations(case_file_id, confirmations);
      router.push(`/audit/${case_file_id}`);
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep p-6">
        <Text className="text-base text-rose">{error}</Text>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-navy-deep" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
        <Text className="text-sm text-white/60">← Back to dashboard</Text>
      </Pressable>

      <View className="mb-5 rounded-2xl bg-teal-deep p-5">
        <Text className="text-2xl font-bold text-white">Let's double-check this bill</Text>
        <Text className="mt-2 text-sm leading-6 text-white/80">
          {extract?.intro_message ??
            'Insurers and billing systems make mistakes, so I want to make sure you were actually billed for what you got. Tap each line to confirm — and "not sure" is always a real option.'}
        </Text>
      </View>

      <View className="mb-4 flex-row items-center justify-between">
        <Text className="text-xs uppercase tracking-widest text-white/45">
          {confirmedCount} of {lineItems.length} confirmed
        </Text>
        <View className="h-1.5 w-32 overflow-hidden rounded-full bg-white/10">
          <View
            className="h-full bg-sage"
            style={{ width: `${lineItems.length ? (confirmedCount / lineItems.length) * 100 : 0}%` }}
          />
        </View>
      </View>

      {lineItems.map((item) => (
        <LineItemCard
          key={item.line_item_id}
          item={item}
          draft={drafts[item.line_item_id] ?? { response: null, user_note: '' }}
          onRespond={(r) => setResponse(item.line_item_id, r)}
          onNote={(n) => setNote(item.line_item_id, n)}
        />
      ))}

      <Pressable
        disabled={!allConfirmed || submitting}
        onPress={onContinue}
        className={
          allConfirmed && !submitting
            ? 'mt-2 rounded-xl bg-sage px-4 py-4'
            : 'mt-2 rounded-xl bg-white/10 px-4 py-4'
        }
      >
        <Text
          className={
            allConfirmed && !submitting
              ? 'text-center text-base font-bold text-ink'
              : 'text-center text-base font-semibold text-white/50'
          }
        >
          {submitting
            ? 'Starting audit…'
            : allConfirmed
              ? 'Continue to audit'
              : `${lineItems.length - confirmedCount} line items left`}
        </Text>
      </Pressable>

      <Text className="mt-4 text-center text-xs text-white/45">
        You can return later — your confirmations are saved when you continue.
      </Text>

      <Text className="mt-10 text-center text-xs text-white/40">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </ScrollView>
  );
}

function LineItemCard({
  item,
  draft,
  onRespond,
  onNote,
}: {
  item: LineItem;
  draft: Draft;
  onRespond: (r: LineItemResponse) => void;
  onNote: (n: string) => void;
}) {
  return (
    <View className="mb-3 rounded-2xl border border-white/10 bg-navy-soft p-4">
      <View className="mb-2 flex-row items-center justify-between">
        <View className="rounded-md bg-white/10 px-2 py-0.5">
          <Text className="text-[11px] font-semibold text-white/80">{item.code}</Text>
        </View>
        {item.billed_amount != null ? (
          <Text className="text-sm font-semibold text-white">
            ${item.billed_amount.toLocaleString(undefined, { minimumFractionDigits: 0 })}
          </Text>
        ) : null}
      </View>

      <Text className="text-base font-medium text-white">{item.plain_language_translation}</Text>
      {item.plain_language_context ? (
        <Text className="mt-1 text-xs italic text-white/50">{item.plain_language_context}</Text>
      ) : null}

      <View className="mt-3 flex-row gap-2">
        <OptionButton
          label="Yes, that's right"
          selected={draft.response === 'yes'}
          tone="sage"
          onPress={() => onRespond('yes')}
        />
        <OptionButton
          label="No, that didn't happen"
          selected={draft.response === 'no'}
          tone="rose"
          onPress={() => onRespond('no')}
        />
        <OptionButton
          label="Not sure"
          selected={draft.response === 'not_sure'}
          tone="amber"
          onPress={() => onRespond('not_sure')}
        />
      </View>

      {draft.response === 'no' ? (
        <View className="mt-3">
          <Text className="mb-1 text-xs text-white/60">What actually happened?</Text>
          <TextInput
            value={draft.user_note}
            onChangeText={onNote}
            placeholder="Optional — helps us understand the mismatch"
            placeholderTextColor="rgba(255,255,255,0.35)"
            className="rounded-md border border-white/15 bg-black/20 px-3 py-2 text-sm text-white"
          />
        </View>
      ) : null}
    </View>
  );
}

function OptionButton({
  label,
  selected,
  tone,
  onPress,
}: {
  label: string;
  selected: boolean;
  tone: 'sage' | 'rose' | 'amber';
  onPress: () => void;
}) {
  const selectedClass =
    tone === 'sage'
      ? 'border-sage bg-sage/20'
      : tone === 'rose'
        ? 'border-rose bg-rose/20'
        : 'border-amber bg-amber/20';
  return (
    <Pressable
      onPress={onPress}
      className={`flex-1 rounded-lg border px-2 py-2 ${selected ? selectedClass : 'border-white/10 bg-white/5'}`}
    >
      <Text
        className={`text-center text-xs font-semibold ${selected ? 'text-white' : 'text-white/70'}`}
      >
        {label}
      </Text>
    </Pressable>
  );
}
