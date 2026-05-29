/**
 * Encounter-verification API contracts (Phase 2I).
 * Mirrors runtime/app/schemas/encounter.py one-for-one.
 */

export type LineItemResponse = 'yes' | 'no' | 'not_sure';

export interface LineItem {
  line_item_id: string;
  code: string;
  code_system: string; // CPT | HCPCS | ICD-10
  raw_description: string;
  /** Plain English describing WHAT HAPPENED — a fact, never a clinical judgment. */
  plain_language_translation: string;
  /** Informational, non-leading context. May be empty. */
  plain_language_context: string;
  /** E/M levels, time-based codes — where upcoding/phantom risk concentrates. */
  high_risk: boolean;
  billed_amount: number | null;
  units: number | null;
}

export interface LineItemConfirmation {
  line_item_id: string;
  response: LineItemResponse;
  user_note: string | null;
}

export interface ExtractResult {
  case_file_id: string;
  status: 'encounter_verification_pending';
  line_items: LineItem[];
  intro_message: string;
}

export interface ConfirmationsAccepted {
  case_file_id: string;
  status: string;
  confirmations_recorded: number;
  mismatches: number;
}

export interface AuditStatusResponse {
  case_file_id: string;
  status: string;
}
