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
  /**
   * Phase 2L — 3-5 factual, second-person past-tense scenarios of what a typical
   * patient would have experienced for this category of service. Aids recall;
   * never a clinical judgment.
   */
  example_scenarios: string[];
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

/** Per-document extraction provenance — which uploads were read vs failed. */
export interface DocumentExtraction {
  filename: string;
  document_type: string | null;
  extraction_status: string; // 'extracted' | 'error' | 'unreadable' | ...
  ocr_text_chars: number;
}

export interface ExtractResult {
  case_file_id: string;
  /**
   * 'extraction_failed' — real OCR/translate produced nothing (unreadable docs). 'not_a_bill' —
   * the doc(s) read fine but none is a bill/EOB, so there's nothing to audit. Either way the UI
   * shows an honest message + re-upload CTA (never fabricated line items, never a 0-item screen).
   */
  // 'needs_documents' (2026-08-18): the doc read fine WITH a real amount but no line-item
  // detail — the ask is for more paper (itemized bill / EOB), never a re-photograph.
  status: 'encounter_verification_pending' | 'extraction_failed' | 'not_a_bill' | 'needs_documents';
  line_items: LineItem[];
  intro_message: string;
  /** Set when status is a failure state: the honest, user-facing reason (names the file for not_a_bill). */
  extraction_message?: string | null;
  /** Per-document extraction provenance. */
  documents?: DocumentExtraction[];
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
