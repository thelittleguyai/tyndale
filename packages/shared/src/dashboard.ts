/**
 * Tyndale dashboard / cases / coverage API contracts.
 *
 * Mirrors runtime/app/schemas/dashboard.py one-for-one. When you change a
 * field here, change it there. The runtime is the contract owner; this
 * file is the typed mirror for the frontend.
 */

export type CoverageExtractionStatus = 'extracted' | 'pending' | 'missing';

export interface UserBrief {
  id: string;
  first_name: string;
}

export interface CoverageMeter {
  total: number;
  met: number;
  remaining: number;
}

export interface CopayAmount {
  amount: number;
}

export interface CoverageCopays {
  pcp_visit: CopayAmount;
  er_visit: CopayAmount;
  specialist: CopayAmount;
}

export interface CoverageSummary {
  deductible: CoverageMeter | null;
  oop_max: CoverageMeter | null;
  copays: CoverageCopays | null;
  extraction_status: CoverageExtractionStatus;
  deductible_source?: string | null;
  oop_max_source?: string | null;
}

export interface OpenCase {
  case_file_id: string;
  headline: string;
  days_open: number;
  next_deadline_date: string | null; // ISO YYYY-MM-DD
  next_deadline_label: string | null;
}

/** A resumable case for the status-aware Open Cases card. `resume` picks the screen: the
 *  encounter-verification screen (pre-audit) or the audit results/progress screen. */
export interface ActiveCase {
  case_file_id: string;
  status: string;
  label: string;
  /** 'intake' = a case still on the guided route (doc 40) — resumes at /intake?case=<id>. */
  resume: 'encounter' | 'results' | 'intake';
  days_open: number;
  next_deadline_date: string | null; // ISO YYYY-MM-DD
  next_deadline_label: string | null;
}

export interface OutcomePromptInline {
  case_file_id: string;
  days_since_recommendation: number;
  finding_summary: string;
}

export interface DashboardPayload {
  user: UserBrief;
  coverage: CoverageSummary;
  banner?: { title: string; subline: string } | null;
  amount_saved_ytd: number;
  recovered_to_date?: number;
  coverage_connection_enabled?: boolean;
  open_count?: number;
  needs_you_count?: number;
  /** Phase CO-1A — drives the intake gate. 'complete' → dashboard; else wizard. */
  intake_status: string;
  intake_current_step: string | null;
  /** Whether the user has any case file — the gate only forces brand-new users into the
   *  wizard, so anyone with case history is never hard-redirected (2026-07-06 fix). */
  has_cases: boolean;
  open_cases: OpenCase[];
  /** Status-aware, full-lifecycle resumable cases for the Open Cases card (2026-07-06). */
  active_cases: ActiveCase[];
  /** Phase 2J — cases eligible for an outcome follow-up prompt. */
  outcome_prompts: OutcomePromptInline[];
  status_forward_greeting: string | null;
  /** DL-91 D5: when true, show the Tyndale Record view in place of the ad-hoc Open Cases list. */
  record_enabled?: boolean;
  /**
   * Guided intake (doc 40 §D): which front door THIS user gets. 'guided' sends "Check a bill"
   * into /intake; 'chat_first' leaves every entry point as it was. Absent on an older server.
   */
  intake_mode?: IntakeMode;
  /** Why: an admin override, the one-time cohort decision, or the env default. */
  intake_mode_source?: 'override' | 'cohort' | 'default';
  /**
   * Entry points the client must leave OUT for this user — absent, never disabled. A closed
   * list (HideableSurface); empty for chat-first users.
   */
  hidden_surfaces?: HideableSurface[];
  /** The guided case this user left unfinished, if any — "pick up where you left off". */
  guided_resume_case_id?: string | null;
}

export interface CaseSummary {
  case_file_id: string;
  headline: string;
  status: string;
  last_updated: string; // ISO-8601
}

export interface CasesListPayload {
  cases: CaseSummary[];
}

export interface CoverageDetailPayload {
  coverage: CoverageSummary;
  source_document_ids: string[];
  confidence: Record<string, unknown>;
}

export type IntakeMode = 'guided' | 'chat_first';

/** Mirrors runtime app/intake/mode.py HIDEABLE_SURFACES. */
export type HideableSurface = 'freeform_chat_entry' | 'quick_actions_grid' | 'connect_plan_tile';
