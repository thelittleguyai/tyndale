/**
 * useChatStream — SSE chat state machine (Phase CO-10).
 *
 * Loads the conversation, sends a message, and consumes the SSE stream
 * (token / tool-call / citation / completion events), updating the message list
 * optimistically. Exposes send / stop and the live tool-call list.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type { ChatStreamEvent, Message, ToolCall } from '@tyndale/shared';

import {
  getConversation,
  stopStream,
  streamMessage,
} from '../../lib/api-client';

export interface UseChatStream {
  messages: Message[];
  streaming: boolean;
  activeTools: ToolCall[];
  error: string | null;
  send: (content: string) => Promise<void>;
  stop: () => Promise<void>;
  reload: () => Promise<void>;
}

function nowIso(): string {
  return new Date().toISOString();
}

export function useChatStream(conversationId: string): UseChatStream {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [activeTools, setActiveTools] = useState<ToolCall[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamingIdRef = useRef<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const d = await getConversation(conversationId);
      setMessages(d.messages);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [conversationId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const send = useCallback(
    async (content: string) => {
      if (streaming || !content.trim()) return;
      setError(null);
      setStreaming(true);
      setActiveTools([]);

      const tempUser: Message = {
        message_id: `temp-u-${Date.now()}`,
        conversation_id: conversationId,
        sequence_number: 0,
        role: 'user',
        content,
        status: 'complete',
        created_at: nowIso(),
      };
      const asstId = `temp-a-${Date.now()}`;
      const tempAsst: Message = {
        message_id: asstId,
        conversation_id: conversationId,
        sequence_number: 0,
        role: 'assistant',
        content: '',
        status: 'streaming',
        created_at: nowIso(),
      };
      streamingIdRef.current = asstId;
      setMessages((m) => [...m, tempUser, tempAsst]);

      let acc = '';
      const ac = new AbortController();
      abortRef.current = ac;

      const patchAsst = (patch: Partial<Message>) =>
        setMessages((m) =>
          m.map((msg) =>
            msg.message_id === streamingIdRef.current ? { ...msg, ...patch } : msg,
          ),
        );

      const onEvent = (ev: ChatStreamEvent) => {
        const d = ev.data || {};
        switch (ev.event) {
          case 'token':
            acc += (d.delta as string) || '';
            patchAsst({ content: acc });
            break;
          case 'tool_call_started':
            setActiveTools((t) => [
              ...t,
              {
                tool_name: d.tool_name,
                subagent: d.subagent,
                input_summary: d.input_summary,
              },
            ]);
            break;
          case 'tool_call_completed':
            setActiveTools((t) => t.filter((x) => x.tool_name !== d.tool_name));
            break;
          case 'assistant_message_completed':
            if (d.message_id) streamingIdRef.current = d.message_id;
            patchAsst({
              message_id: d.message_id || asstId,
              content: acc,
              content_chunks: d.content_chunks,
              citations: d.citations,
              confidence_overall: d.confidence_overall,
              status: 'complete',
            });
            break;
          case 'error':
            setError((d.message as string) || (d.code as string) || 'Something went wrong');
            patchAsst({ status: 'failed', error_message: d.message || d.code });
            break;
          case 'done':
            setStreaming(false);
            setActiveTools([]);
            break;
          default:
            break;
        }
      };

      try {
        await streamMessage(conversationId, content, onEvent, ac.signal);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setStreaming(false);
        setActiveTools([]);
        // Reconcile with the server (real ids + persisted content).
        reload();
      }
    },
    [conversationId, streaming, reload],
  );

  const stop = useCallback(async () => {
    abortRef.current?.abort();
    try {
      await stopStream(conversationId);
    } catch {
      /* best effort */
    }
    setStreaming(false);
    setMessages((m) =>
      m.map((msg) =>
        msg.message_id === streamingIdRef.current ? { ...msg, status: 'stopped' } : msg,
      ),
    );
  }, [conversationId]);

  return { messages, streaming, activeTools, error, send, stop, reload };
}
