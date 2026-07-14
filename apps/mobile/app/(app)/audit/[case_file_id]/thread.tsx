/**
 * Chat-first case thread (DL-91, Phase A). Reached from the upload flow when ENABLE_CHAT_FIRST_AUDIT
 * is on. The server-side event bridge writes typed thread entries; this screen loads the case
 * conversation, kicks extraction once, POLLS for live updates while the status card is non-terminal
 * (no out-of-band SSE push exists yet — a dedicated subscription stream is a Phase-B fast-follow),
 * and renders each entry via ThreadEntry. Verification is structured taps only (D4a); when every
 * line item is answered it auto-submits (D3 completion → the audit continues).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import type { LineItemResponse, Message, StatusCardPayload, VerificationRequestPayload } from '@tyndale/shared';

import {
  extractLineItems,
  getConversation,
  listConversations,
  submitConfirmations,
} from '../../../../lib/api-client';
import { ThreadEntry } from '../../../../components/thread/ThreadEntry';
import type { Draft } from './encounter';

export default function CaseThreadScreen() {
  const { case_file_id } = useLocalSearchParams<{ case_file_id: string }>();
  const router = useRouter();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const extractKicked = useRef(false);
  const submitted = useRef(false);

  const refresh = useCallback(async (id: string) => {
    const conv = await getConversation(id);
    setMessages(conv.messages ?? []);
  }, []);

  const load = useCallback(async () => {
    const list = await listConversations({ case_id: case_file_id, mode: 'per_case', limit: 1 });
    const cid = list.conversations[0]?.conversation_id ?? null;
    setConversationId(cid);
    if (cid) await refresh(cid);
    setLoading(false);
    // Kick extraction once (idempotent server-side) so line items + verification cards appear.
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

  // Poll for live thread updates while the audit is in flight.
  useEffect(() => {
    if (!conversationId || terminal) return undefined;
    const t = setInterval(() => {
      refresh(conversationId).catch(() => undefined);
    }, 2500);
    return () => clearInterval(t);
  }, [conversationId, terminal, refresh]);

  const allLineItems = useMemo(() => {
    const out: { line_item_id: string }[] = [];
    for (const m of messages) {
      if (m.kind === 'verification_request') {
        out.push(...((m.payload as unknown as VerificationRequestPayload).line_items ?? []));
      }
    }
    return out;
  }, [messages]);

  const onRespond = (id: string, r: LineItemResponse) =>
    setDrafts((d) => ({ ...d, [id]: { response: r, user_note: d[id]?.user_note ?? '' } }));
  const onNote = (id: string, n: string) =>
    setDrafts((d) => ({ ...d, [id]: { response: d[id]?.response ?? null, user_note: n } }));

  // D3: once every card is answered, auto-submit — the audit continues (server kicks finalize).
  useEffect(() => {
    if (submitted.current || allLineItems.length === 0 || !conversationId) return;
    const answered = allLineItems.every((li) => drafts[li.line_item_id]?.response);
    if (!answered) return;
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
        submitted.current = false; // allow a retry on transient failure
      }
      await refresh(conversationId);
    })();
  }, [allLineItems, drafts, conversationId, case_file_id, refresh]);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-navy-deep">
        <ActivityIndicator color="#3DAA7E" />
      </View>
    );
  }

  return (
    <ScrollView
      className="flex-1 bg-navy-deep"
      contentContainerStyle={{ padding: 20, paddingTop: 28 }}
    >
      <View className="w-full max-w-2xl self-center">
        <Pressable onPress={() => router.push('/')} className="mb-5 self-start">
          <Text className="text-sm text-white/60">← Back to dashboard</Text>
        </Pressable>
        {messages.map((m) => (
          <ThreadEntry
            key={m.message_id}
            message={m}
            caseFileId={case_file_id}
            conversationId={conversationId ?? ''}
            drafts={drafts}
            onRespond={onRespond}
            onNote={onNote}
          />
        ))}
      </View>
    </ScrollView>
  );
}
