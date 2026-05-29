/**
 * Feedback capture API contracts (Phase 2J / L05).
 * Mirrors runtime/app/schemas/feedback.py.
 *
 * NOTE (DL-38): this module MUST be re-exported from src/index.ts. Phase 2H
 * silently dropped the dashboard re-export; Phase 2I caught it only because
 * typecheck was run locally. Keep the barrel export in sync.
 */

export type FeedbackType =
  | 'thumbs'
  | 'structured_correction'
  | 'outcome_report'
  | 'value_confirmation'
  | 'implicit_signal';

export type StructuredReason =
  | 'wrong_number'
  | 'missed_an_error'
  | 'false_error'
  | 'bad_recommendation'
  | 'confusing'
  | 'wrong_citation'
  | 'wrong_coverage_reading'
  | 'other';

export type ThumbsValue = 'up' | 'down';
export type ResolvedValue = 'yes' | 'no' | 'partial' | 'pending' | 'unknown';

/** Human-readable labels for the structured-reason chips (UI order matters). */
export const STRUCTURED_REASON_LABELS: { value: StructuredReason; label: string }[] = [
  { value: 'wrong_number', label: 'Wrong number' },
  { value: 'missed_an_error', label: 'Missed an error' },
  { value: 'false_error', label: "Flagged something that wasn't actually wrong" },
  { value: 'bad_recommendation', label: 'Bad recommendation' },
  { value: 'confusing', label: 'Confusing' },
  { value: 'wrong_citation', label: 'Wrong citation' },
  { value: 'wrong_coverage_reading', label: 'Misread my coverage' },
  { value: 'other', label: 'Something else' },
];

export interface FeedbackOutcome {
  acted_on_recommendation?: boolean | null;
  resolved?: ResolvedValue | null;
  amount_saved?: number | null;
  outcome_notes?: string | null;
}

export interface ValueConfirmation {
  confirmation_kind?: 'extracted_value' | 'encounter_lineitem' | null;
  field?: string | null;
  tyndale_extracted?: string | null;
  user_corrected?: string | null;
  was_correct?: boolean | null;
}

/** The POST /v1/feedback request body (matches FeedbackEventIn). */
export interface FeedbackEvent {
  event_id: string;
  timestamp: string; // ISO-8601
  case_file_id: string;
  feedback_type: FeedbackType;
  response_id?: string | null;
  thumbs?: ThumbsValue | null;
  structured_reason?: StructuredReason[] | null;
  free_text?: string | null;
  outcome?: FeedbackOutcome | null;
  value_confirmation?: ValueConfirmation | null;
}

export interface FeedbackAck {
  event_id: string;
  feedback_event_id: string;
  queued_for_deid: boolean;
}

export interface FeedbackEventOut {
  feedback_event_id: string;
  feedback_type: string;
  response_id: string | null;
  thumbs: ThumbsValue | null;
  structured_reason: string[] | null;
  created_at: string;
}

export interface CaseFeedbackPayload {
  case_file_id: string;
  events: FeedbackEventOut[];
}

export interface OutcomePrompt {
  case_file_id: string;
  days_since_recommendation: number;
  finding_summary: string;
}

export interface OutcomePromptsPayload {
  prompts: OutcomePrompt[];
}

export interface UserProfile {
  id: string;
  first_name: string;
  email: string;
  user_type: 'user' | 'admin';
  improvement_consent: boolean;
  created_at: string;
}

export interface ConsentHistoryEntry {
  changed_at: string;
  from_consent: boolean;
  to_consent: boolean;
}

export interface ConsentHistoryPayload {
  user_id: string;
  history: ConsentHistoryEntry[];
}
