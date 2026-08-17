// Chat surface shared types (Phase CO-10).
//
// Note: `ChatCitation` (not `Citation`) — apps/mobile/lib/api-client already has a
// finding-shaped `Citation` (authority/section/src_id/marker); the chat citation is
// a different shape, so it gets its own name to avoid an import collision.

import type { LineItem } from './encounter';

export type ChatMode = 'per_case' | 'freeform';
export type VoiceTier = 'A' | 'B' | 'C';
export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'failed';

// --- Chat-first typed thread entries (DL-91, Brock 2026-07-10) ---------------
// 'message' = the classic text/chunks turn; the rest are bridge-authored (role='system') cards
// whose structured data rides in `Message.payload`. The mobile renderer dispatches on `kind`.
export type MessageKind =
  | 'message'
  | 'status_card_update'
  | 'system_message'
  | 'moment_card'
  | 'verification_request'
  | 'verification_suggestion';

/**
 * payload for kind='verification_suggestion' (D4b). A free-text reply mapped to cards + intended
 * answers, PRE-SELECTED pending a confirming tap. Nothing is committed until the tap — the mapper
 * never writes to the confirmations endpoint.
 */
export interface VerificationSuggestionPayload {
  text: string; // script-keyed confirm prompt (verification.map_confirm, {{summary}} interpolated)
  summary: string;
  // intended_answer is the LineItemResponse vocabulary (the mapper's 'unsure' → 'not_sure').
  mappings: { line_item_id: string; intended_answer: 'yes' | 'no' | 'not_sure' }[];
}

/** The four FLOW stages the status card renders as labeled bars (each derived from case state). */
export type ThreadStageKey = 'extraction' | 'translate' | 'encounter' | 'audit';
export type ThreadStageState = 'pending' | 'active' | 'done' | 'failed';
export interface ThreadStage {
  key: ThreadStageKey;
  label: string; // script-keyed
  state: ThreadStageState;
}
/** payload for kind='status_card_update' — ONE card updated in place (D2). */
export interface StatusCardPayload {
  stages: ThreadStage[]; // exactly the four flow stages, in order
  terminal: boolean; // true once the audit reached a terminal state
}
/** payload for kind='verification_request' — ≤3 line items per group (D3). */
export interface VerificationRequestPayload {
  intro: string; // script-keyed
  nudge: string; // D4a "tap to confirm" copy
  group_index: number;
  line_items: LineItem[];
}
export interface ThreeNumberMomentPayload {
  variant: 'three_number';
  provider_billed: number;
  eob_member_responsibility: number;
  tyndale_computed: number;
  delta: number; // billed-minus-computed savings
  headline: string; // script-keyed reveal frame, {{delta_dollars}} interpolated
  /** L2 — "provider · payer" from TYPED fields only; omitted when neither is known. */
  context?: string;
  /** E3 — the gap framing; null/absent on a clean bill (never "$0.00 less"). */
  gap_callout?: string | null;
}
export interface UnlockMomentPayload {
  variant: 'first_case_unlock';
  headline: string;
  value_points: string[];
  footnote: string;
}
/** payload for kind='moment_card' — full-width, visually distinct (D0). */
export type MomentCardPayload = ThreeNumberMomentPayload | UnlockMomentPayload;
export interface NeedsDocumentsItem {
  key: string;
  label: string;
  how_to_get: string;
  have: boolean; // TRUE have/need state (per-item API, DL-90)
}
/** payload for kind='system_message' when it carries the needs_documents checklist. */
export interface NeedsDocumentsPayload {
  intro: string;
  items: NeedsDocumentsItem[];
}
/** payload for kind='system_message' — a plain rendered script line. */
export interface SystemMessagePayload {
  text: string;
  tone?: 'neutral' | 'error';
  needs_documents?: NeedsDocumentsPayload; // present on the needs_documents ask
}

export interface ChatCitation {
  source_id?: string | null;
  title?: string | null;
  url?: string | null;
  snippet?: string | null;
  effective_date?: string | null;
  payer?: string | null;
  /** CPT code shown WITHOUT the AMA-copyrighted descriptor (DL-54). */
  cpt_code?: string | null;
  /** Freeform-mode redirect action; the UI renders a "create a case" button. */
  action_type?: 'create_case_cta' | null;
  /**
   * laws_regulations X6 fields (DL-84): let the citation card show whether a legal
   * claim is CATEGORICAL (flat rule) or CONDITIONAL (fact-dependent) and how current
   * the classification is. Null for non-law citations (codes, payer policy).
   */
  as_of?: string | null;
  x6_classification?: 'CATEGORICAL' | 'CONDITIONAL' | null;
}

export interface ContentChunk {
  tier: VoiceTier;
  text: string;
  citations: ChatCitation[];
  confidence?: number | null;
}

export interface ToolCall {
  tool_name: string;
  subagent?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  timestamp?: string | null;
  duration_ms?: number | null;
}

export interface Conversation {
  conversation_id: string;
  user_id: string;
  case_id: string | null;
  mode: ChatMode;
  title: string | null;
  is_archived: boolean;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  message_id: string;
  conversation_id: string;
  sequence_number: number;
  role: MessageRole;
  /** Typed thread-entry discriminator (DL-91). Defaults to 'message' for classic turns. */
  kind?: MessageKind;
  /** Structured card data for non-'message' kinds; cast to the matching *Payload by `kind`. */
  payload?: Record<string, unknown> | null;
  content: string | null;
  content_chunks?: ContentChunk[] | null;
  tool_calls?: ToolCall[] | null;
  citations?: ChatCitation[] | null;
  confidence_overall?: number | null;
  status: MessageStatus;
  error_message?: string | null;
  token_usage_input?: number | null;
  token_usage_output?: number | null;
  estimated_cost_usd?: number | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ConversationList {
  conversations: Conversation[];
  total: number;
  limit: number;
  offset: number;
}

export type ChatStreamEventType =
  | 'user_message_persisted'
  | 'assistant_message_started'
  | 'tool_call_started'
  | 'tool_call_completed'
  | 'token'
  | 'citation_added'
  | 'assistant_message_completed'
  | 'error'
  | 'done';

export interface ChatStreamEvent {
  event: ChatStreamEventType;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
}
