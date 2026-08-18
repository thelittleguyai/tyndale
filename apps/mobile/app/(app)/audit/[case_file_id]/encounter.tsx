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

import { Check, CircleHelp, X as XIcon } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { Disclosure } from '../../../../components/ui';
import {
  ExtractResult,
  LineItem,
  LineItemResponse,
  getLineItems,
  submitConfirmations,
} from '../../../../lib/api-client';

// `suggested` (D4b): the answer was pre-selected by the free-text mapper and is awaiting a
// confirming tap — a UI hint only, never committed until confirmed.
export type Draft = { response: LineItemResponse | null; user_note: string; suggested?: boolean };

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
      <View className="flex-1 items-center justify-center bg-page p-6">
        <Text className="text-base text-danger">{error}</Text>
      </View>
    );
  }

  // Honest degraded states — we NEVER show fabricated line items here (the invariant: no 0-item
  // encounter). 'extraction_failed' = couldn't read the docs; 'not_a_bill' = they read fine but
  // aren't a bill/EOB; 'needs_documents' (2026-08-18) = readable with a real amount but no
  // line-item detail — the ask is for MORE PAPER, not a better photo. All show the honest
  // reason + a path forward.
  if (
    extract &&
    (extract.status === 'extraction_failed' ||
      extract.status === 'not_a_bill' ||
      extract.status === 'needs_documents')
  ) {
    const isNotBill = extract.status === 'not_a_bill';
    const isNeedsDocs = extract.status === 'needs_documents';
    return (
      <ScrollView
        className="flex-1 bg-page"
        contentContainerStyle={{ padding: 20, paddingTop: 28 }}
      >
        <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
          <Text className="text-sm text-secondary">← Back to dashboard</Text>
        </Pressable>

        <View className="mb-5 rounded-2xl bg-surface-raised p-5">
          <Text className="text-3xl font-bold leading-tight text-primary">
            {isNeedsDocs
              ? 'One more document finishes this'
              : isNotBill
                ? "This doesn't look like a medical bill"
                : "We couldn't read your documents"}
          </Text>
          <Text className="mt-3 max-w-2xl text-body leading-6 text-secondary">
            {extract.extraction_message ??
              (isNeedsDocs
                ? "We can read this document and the amount on it — it just doesn't include the line-item detail we audit. Add the itemized bill or the EOB for this visit."
                : isNotBill
                  ? 'Upload a bill, an Explanation of Benefits, an insurance card, or a plan summary and I\'ll check it for you.'
                  : 'Try uploading a clearer photo or PDF — good lighting, all four corners in frame, one document per image.')}
          </Text>
        </View>

        {extract.documents?.length ? (
          <View className="mb-5 rounded-2xl border border-hairline bg-surface p-4">
            <Text className="mb-2 text-xs text-faint">
              What we received
            </Text>
            {extract.documents.map((d, i) => {
              const ok = d.extraction_status === 'extracted' && d.ocr_text_chars > 0;
              return (
                <View key={i} className="flex-row items-center justify-between py-1.5">
                  <Text className="flex-1 pr-3 text-body text-secondary" numberOfLines={1}>
                    {d.filename}
                  </Text>
                  <Text className={ok ? 'text-sm text-accent' : 'text-sm text-danger'}>
                    {ok ? 'Readable' : "Couldn't read"}
                  </Text>
                </View>
              );
            })}
          </View>
        ) : null}

        <Pressable
          onPress={() => router.push('/upload')}
          className="mt-2 rounded-xl bg-accent px-4 py-4"
        >
          <Text className="text-center text-base font-bold text-on-accent">Upload again</Text>
        </Pressable>

        <Text className="mt-10 text-center text-xs text-faint">
          Tyndale provides medical billing and coverage advocacy, not medical, legal, or
          financial advice.
        </Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
      <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
        <Text className="text-sm text-secondary">← Back to dashboard</Text>
      </Pressable>

      <View className="mb-5 rounded-2xl bg-surface-raised p-5">
        <Text className="text-3xl font-bold leading-tight text-primary">
          Can you confirm what you were seen for?
        </Text>
        <Text className="mt-3 max-w-2xl text-[15px] leading-6 text-secondary">
          Sometimes the bill doesn't reflect what actually occurred. That's why we try to confirm
          with you what actually happened during the visit.
        </Text>
      </View>

      <View className="mb-4 flex-row items-center justify-between">
        <Text className="text-xs text-faint">
          {confirmedCount} of {lineItems.length} confirmed
        </Text>
        <View className="h-1.5 w-32 overflow-hidden rounded-full bg-inset">
          <View
            className="h-full bg-accent"
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
            ? 'mt-2 rounded-xl bg-accent px-4 py-4'
            : 'mt-2 rounded-xl bg-inset px-4 py-4'
        }
      >
        <Text
          className={
            allConfirmed && !submitting
              ? 'text-center text-base font-bold text-on-accent'
              : 'text-center text-base font-semibold text-faint'
          }
        >
          {submitting
            ? 'Starting audit…'
            : allConfirmed
              ? 'Continue to audit'
              : `${lineItems.length - confirmedCount} line items left`}
        </Text>
      </Pressable>

      <Text className="mt-4 text-center text-xs text-faint">
        You can return later — your confirmations are saved when you continue.
      </Text>

      <Text className="mt-10 text-center text-xs text-faint">
        Tyndale provides medical billing and coverage advocacy, not medical, legal, or
        financial advice.
      </Text>
    </ScrollView>
  );
}

export function LineItemCard({
  item,
  draft,
  onRespond,
  onNote,
  suggested,
}: {
  item: LineItem;
  draft: Draft;
  onRespond: (r: LineItemResponse) => void;
  onNote: (n: string) => void;
  suggested?: boolean;
}) {
  const answered = draft.response !== null;
  return (
    <View
      className={`mb-3 rounded-card border p-4 ${
        suggested ? 'border-dashed border-accent bg-accent-tint' : 'border-hairline bg-surface'
      }`}
    >
      {suggested ? (
        <Text className="mb-2 text-caption font-medium text-accent">Suggested — tap to confirm</Text>
      ) : null}

      {/* Heading row: code · name · billed amount (redesign §3). */}
      <View className="mb-2 flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-body font-medium text-primary" numberOfLines={1}>
          {item.code} · {item.plain_language_translation}
        </Text>
        {item.billed_amount != null ? (
          <Text className="text-body text-primary">
            ${item.billed_amount.toLocaleString(undefined, { minimumFractionDigits: 0 })}
          </Text>
        ) : null}
      </View>

      {/* One body sentence; the explainer + typical-scenarios collapse behind a Disclosure. */}
      {item.plain_language_context || item.example_scenarios?.length ? (
        <Disclosure summary="Show what this usually looks like">
          {item.plain_language_context ? (
            <Text className="text-caption italic leading-5 text-secondary">
              {item.plain_language_context}
            </Text>
          ) : null}
          {item.example_scenarios?.length ? (
            <View className="mt-2">
              <Text className="mb-1 text-caption text-faint">
                For this kind of visit, you'd typically have:
              </Text>
              {item.example_scenarios.map((s, i) => (
                <View key={i} className="mb-1 flex-row gap-2">
                  <Text className="text-accent">•</Text>
                  <Text className="flex-1 text-caption leading-5 text-secondary">{s}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </Disclosure>
      ) : null}

      {/* Primary / secondary / tertiary — visual hierarchy, not three equal grays. The chosen
          answer keeps a check + full opacity; the others dim so the pick reads at a glance. */}
      <View className="mt-3 flex-row items-center gap-2">
        <OptionButton label="Yes, that's right" variant="primary" selected={draft.response === 'yes'} answered={answered} onPress={() => onRespond('yes')} />
        <OptionButton label="That didn't happen" variant="secondary" selected={draft.response === 'no'} answered={answered} onPress={() => onRespond('no')} />
        <OptionButton label="Not sure" variant="tertiary" selected={draft.response === 'not_sure'} answered={answered} onPress={() => onRespond('not_sure')} />
      </View>

      {draft.response === 'no' ? (
        <View className="mt-3">
          <Text className="mb-1 text-caption text-secondary">What actually happened?</Text>
          <TextInput
            value={draft.user_note}
            onChangeText={onNote}
            placeholder="Optional — helps us understand the mismatch"
            placeholderTextColor="var(--c-text-faint)"
            className="rounded-control border border-hairline bg-inset px-3 py-2 text-body text-primary"
          />
        </View>
      ) : null}
    </View>
  );
}

function OptionButton({
  label,
  variant,
  selected,
  answered,
  onPress,
}: {
  label: string;
  variant: 'primary' | 'secondary' | 'tertiary';
  selected: boolean;
  answered: boolean;
  onPress: () => void;
}) {
  const base =
    variant === 'primary'
      ? 'bg-accent'
      : variant === 'secondary'
        ? 'border border-hairline'
        : '';
  const textCls =
    variant === 'primary' ? 'text-on-accent' : variant === 'tertiary' ? 'text-secondary' : 'text-primary';
  const grow = variant === 'tertiary' ? 'self-stretch' : 'flex-1';
  // L5 (round-2) — an icon beside each label so the three answers scan without reading.
  const iconColor =
    variant === 'primary' ? 'var(--c-on-accent)' : variant === 'tertiary' ? 'var(--c-text-secondary)' : 'var(--c-text-primary)';
  const Icon = variant === 'primary' ? Check : variant === 'secondary' ? XIcon : CircleHelp;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      className={`min-h-[44px] ${grow} flex-row items-center justify-center gap-1 rounded-control px-3 py-2 ${base} ${
        answered && !selected ? 'opacity-45' : ''
      }`}
    >
      <Icon size={14} color={iconColor} />
      <Text className={`text-center text-caption font-medium ${textCls}`}>{label}</Text>
      {selected ? <Text className={`text-caption ${textCls}`}>✓</Text> : null}
    </Pressable>
  );
}
