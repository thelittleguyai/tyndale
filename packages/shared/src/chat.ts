// Chat surface shared types (Phase CO-10).
//
// Note: `ChatCitation` (not `Citation`) — apps/mobile/lib/api-client already has a
// finding-shaped `Citation` (authority/section/src_id/marker); the chat citation is
// a different shape, so it gets its own name to avoid an import collision.

export type ChatMode = 'per_case' | 'freeform';
export type VoiceTier = 'A' | 'B' | 'C';
export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'failed';

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
