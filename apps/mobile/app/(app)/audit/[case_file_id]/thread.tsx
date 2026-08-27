/**
 * Chat-first case thread (DL-91). Phase A: the server bridge writes typed entries; this screen
 * loads the conversation, kicks extraction, polls while non-terminal, and auto-submits verification
 * once every card is answered. Phase B (D4b): a free-text reply routes to /verify-text; the mapper
 * posts a pre-selectable SUGGESTION which pre-fills the mapped cards in a "suggested" state; one
 * Confirm tap commits those (the existing confirmations endpoint) — free text never commits.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import type {
  LineItemResponse,
  Message,
  StatusCardPayload,
  VerificationRequestPayload,
  VerificationSuggestionPayload,
} from '@tyndale/shared';

import {
  extractLineItems,
  getConversation,
  listConversations,
  submitConfirmations,
  coverageText,
  streamMessage,
  verifyText,
} from '../../../../lib/api-client';
import { ThreadEntry } from '../../../../components/thread/ThreadEntry';
import type { Draft } from './encounter';
import { useThemeColors } from '../../../../theme/useThemeColors';
import { ChatComposer } from '../../../../components/chat/ChatComposer';

export default function CaseThreadScreen() {
  const tc = useThemeColors();
  const { case_file_id } = useLocalSearchParams<{ case_file_id: string }>();
  const router = useRouter();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null);
  const [coverageSuggestion, setCoverageSuggestion] = useState<{
    field: string;
    value: number | string;
  } | null>(null);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const extractKicked = useRef(false);
  const submitted = useRef(false);
  const appliedSuggestion = useRef<string | null>(null);

  const refresh = useCallback(async (id: string) => {
    const conv = await getConversation(id);
    setMessages(conv.messages ?? []);
  }, []);

  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    // Never a permanent spinner (audit 2026-08-27 item 2): a failed load renders an
    // error state with retry instead of hanging.
    try {
      setLoadError(false);
      const list = await listConversations({ case_id: case_file_id, mode: 'per_case', limit: 1 });
      const cid = list.conversations[0]?.conversation_id ?? null;
      setConversationId(cid);
      if (cid) await refresh(cid);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
    if (!extractKicked.current) {
      extractKicked.current = true;
      extractLineItems(case_file_id).catch(() => undefined);
    }
  }, [case_file_id, refresh]);

  useEffect(() => {
    load();
  }, [load]);

  const statusCard = useMemo(
    () => messages.find((m) => m.kind === 'status_card_update'),
    [messages],
  );
  const terminal = (statusCard?.payload as StatusCardPayload | undefined)?.terminal ?? false;

  useEffect(() => {
    if (!conversationId || terminal) return undefined;
    const t = setInterval(() => {
      refresh(conversationId).catch(() => undefined);
    }, 2500);
    return () => clearInterval(t);
  }, [conversationId, terminal, refresh]);

  const verificationMsgs = useMemo(
    () => messages.filter((m) => m.kind === 'verification_request'),
    [messages],
  );
  const allLineItems = useMemo(() => {
    const out: { line_item_id: string }[] = [];
    for (const m of verificationMsgs) {
      out.push(...((m.payload as unknown as VerificationRequestPayload).line_items ?? []));
    }
    return out;
  }, [verificationMsgs]);
  const pendingVerification = allLineItems.length > 0 && !submitted.current;
  // image-3 item 4: the checklist card on screen keeps the composer visible and usable —
  // pending = any coverage-number item still unanswered on the needs/unlock card.
  const coveragePending = messages.some((m) => {
    const p = m.payload as {
      needs_documents?: { coverage_items?: { value: unknown; not_sure?: boolean }[] };
      unlock_more?: { coverage_items?: { value: unknown; not_sure?: boolean }[] };
    } | null;
    const card = p?.needs_documents ?? p?.unlock_more;
    return (card?.coverage_items ?? []).some((c) => c.value == null && !c.not_sure);
  });

  // Apply the latest suggestion's pre-selection (D4b). New suggestions supersede old ones — the
  // prior pre-selection is cleared before the new one applies (no stacking of stale suggestions).
  useEffect(() => {
    const suggestions = messages.filter((m) => m.kind === 'verification_suggestion');
    const latest = suggestions[suggestions.length - 1];
    if (!latest || latest.message_id === appliedSuggestion.current) return;
    appliedSuggestion.current = latest.message_id;
    const payload = latest.payload as unknown as VerificationSuggestionPayload;
    setDrafts((d) => {
      const next: Record<string, Draft> = {};
      for (const [k, v] of Object.entries(d)) next[k] = v.suggested ? { response: null, user_note: '' } : v;
      for (const m of payload.mappings ?? []) {
        next[m.line_item_id] = { response: m.intended_answer, user_note: '', suggested: true };
      }
      return next;
    });
    setActiveSuggestionId(latest.message_id);
  }, [messages]);

  const onRespond = (id: string, r: LineItemResponse) => {
    // A direct tap is a confirmed answer (clears any suggested flag on that card).
    setDrafts((d) => ({ ...d, [id]: { response: r, user_note: d[id]?.user_note ?? '', suggested: false } }));
  };
  const onNote = (id: string, n: string) =>
    setDrafts((d) => ({ ...d, [id]: { response: d[id]?.response ?? null, user_note: n, suggested: d[id]?.suggested } }));

  // One confirming tap commits ALL pre-selections from the mapping event (suggested → confirmed).
  const onConfirmSuggestion = () => {
    setDrafts((d) => {
      const next = { ...d };
      for (const [k, v] of Object.entries(next)) if (v.suggested) next[k] = { ...v, suggested: false };
      return next;
    });
    setActiveSuggestionId(null);
  };

  const sendTextWith = async (raw: string) => {
    const text = raw.trim();
    if (!text || sending || !conversationId) return;
    // Clear any un-confirmed pre-selection before re-mapping (no stale stacking).
    setDrafts((d) => {
      const next: Record<string, Draft> = {};
      for (const [k, v] of Object.entries(d)) next[k] = v.suggested ? { response: null, user_note: '' } : v;
      return next;
    });
    setActiveSuggestionId(null);
    appliedSuggestion.current = null;
    setSending(true);
    try {
      // Structured verification is pending → map the free text; a pending checklist maps
      // coverage numbers (typed input takes precedence over chips — the mapping only
      // PRE-SELECTS; the confirming tap saves); anything unmapped is ordinary chat.
      if (pendingVerification) {
        await verifyText(case_file_id, text);
      } else if (coveragePending) {
        const r = await coverageText(case_file_id, text);
        if (r.mapped && r.field && r.value != null) {
          setCoverageSuggestion({ field: r.field, value: r.value });
        } else if (r.result === 'ok' && !r.mapped) {
          await new Promise<void>((resolve) =>
            streamMessage(conversationId, text, (ev) => {
              if (ev.event === 'done') resolve();
            }),
          );
        }
      }
      await refresh(conversationId);
    } catch {
      // swallow — the thread poll reflects whatever the server recorded
    } finally {
      setSending(false);
    }
  };

  // Auto-submit once every card is CONFIRMED (a suggested pre-selection does not count until the
  // confirming tap clears its `suggested` flag) — the invariant: free text never commits.
  useEffect(() => {
    if (submitted.current || allLineItems.length === 0 || !conversationId) return;
    const ready = allLineItems.every((li) => {
      const d = drafts[li.line_item_id];
      return d?.response && !d.suggested;
    });
    if (!ready) return;
    submitted.current = true;
    (async () => {
      const confirmations = allLineItems.map((li) => ({
        line_item_id: li.line_item_id,
        response: drafts[li.line_item_id].response as LineItemResponse,
        user_note: drafts[li.line_item_id].user_note || null,
      }));
      try {
        await submitConfirmations(case_file_id, confirmations);
      } catch {
        submitted.current = false;
      }
      await refresh(conversationId);
    })();
  }, [allLineItems, drafts, conversationId, case_file_id, refresh]);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-page">
        <ActivityIndicator color={tc.accent} />
      </View>
    );
  }

  return (
    <View className="flex-1 bg-page">
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 28 }}>
        <View className="w-full max-w-2xl self-center">
          <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
            <Text className="text-sm text-secondary">← Back to dashboard</Text>
          </Pressable>
          {loadError ? (
            <View className="rounded-2xl border border-hairline bg-surface p-5" testID="thread-load-error">
              <Text className="text-body leading-6 text-secondary">
                Something went wrong loading this case. Your documents are safe — try again.
              </Text>
              <Pressable
                onPress={() => { setLoading(true); void load(); }}
                className="mt-3 min-h-[44px] items-center justify-center self-start rounded-xl bg-accent px-4"
                testID="thread-retry"
              >
                <Text className="text-body font-bold text-on-accent">Try again</Text>
              </Pressable>
            </View>
          ) : null}
          {messages.map((m) => (
            <ThreadEntry
              key={m.message_id}
              message={m}
              caseFileId={case_file_id}
              conversationId={conversationId ?? ''}
              drafts={drafts}
              onRespond={onRespond}
              onNote={onNote}
              activeSuggestionId={activeSuggestionId}
              onConfirmSuggestion={onConfirmSuggestion}
              coverageSuggestion={coverageSuggestion}
              onCoverageSaved={() => {
                setCoverageSuggestion(null);
                if (conversationId) void refresh(conversationId);
              }}
            />
          ))}
        </View>
      </ScrollView>
      {pendingVerification || coveragePending ? (
        <View className="w-full max-w-2xl self-center border-t border-hairline bg-page px-4 py-2">
          {/* The shared composer (audit 2026-08-27 item 2): paperclip + a11y, one
              implementation instead of the hand-rolled twin. */}
          <ChatComposer
            onSend={(text) => void sendTextWith(text)}
            onStop={() => {}}
            streaming={false}
            disabled={sending}
            placeholder="Answer in your own words, or tap the cards…"
            onAttach={() =>
              router.push({ pathname: '/upload', params: { caseId: case_file_id } })
            }
          />
        </View>
      ) : null}
    </View>
  );
}
