/**
 * Guided intake wizard API contracts (Phase CO-1A).
 *
 * Mirrors runtime/app/schemas/intake.py one-for-one. The runtime is the contract
 * owner; this is the typed mirror for the Expo wizard.
 */

// There is NO step list any more (doc 40 §A4). CO-1A's INTAKE_STEPS / IntakeStep /
// SKIPPABLE_STEPS are gone: the server's Intake Planner picks the next screen after every
// capture, and the client draws the `screen` it is handed. `current_step` is that pick — a
// screen id from the runtime's SCREEN_REGISTRY, or 'READY'.
export type IntakeStatus = 'not_started' | 'in_progress' | 'complete';

/** The renderer the client uses for a screen. A closed set — an unknown kind renders the
 *  generic info layout, so a server ahead of the app degrades instead of crashing. */
export type IntakeScreenKind =
  | 'info'
  | 'handoff'
  | 'capture'
  | 'coach'
  | 'summary'
  | 'choice'
  | 'fields'
  | 'plan_confirm'
  | 'timeline'
  | 'attest'
  | 'progress'
  | 'confirmations'
  | 'readiness'
  | 'ready';

export type IntakeProgressGroup =
  | 'bill'
  | 'card'
  | 'plan_rules'
  | 'eob'
  | 'timeline'
  | 'about_you'
  | 'confirmations';

export interface IntakeExample {
  ask: string;
  title: string | null;
  /**
   * doc 41 (Brock 2026-09-21, decision 8): the drawn illustration bundled with the app
   * (apps/mobile/assets/examples/<slot>@2x.png) and Brock's legend — one line per numbered badge,
   * rendered by the app, never baked into the image. Absent/null → the federal sample path.
   */
  illustration?: { slot: string; aspect: 'portrait' | 'landscape' } | null;
  legend?: string[];
  /**
   * The federal sample's "look for this" callouts (SBC, MSN) — sent whenever a sample exists, even
   * once it is illustrated: the app shows them (with source_line) when its build lacks the image.
   */
  callouts: string[];
  asset: { kind: 'external_pdf'; url: string; publisher: string } | null;
  source_line: string | null;
  glosses: Record<string, string>;
}

export interface IntakeHelp {
  document_type: string;
  scope: 'payer' | 'generic';
  payer_name: string | null;
  title: string | null;
  note: string | null;
  steps: string[];
  verified: boolean;
  can_email: boolean;
}

/** One screen, as the planner hands it over. `copy` is registry text keyed by slot — the app
 *  holds no intake copy. `example` / `help` are PRESENT only when there is something behind them. */
export interface IntakeScreen {
  id: string;
  kind: IntakeScreenKind;
  progress_group: IntakeProgressGroup | null;
  copy: Record<string, string>;
  data: Record<string, unknown>;
  skippable: boolean;
  example?: IntakeExample;
  help?: IntakeHelp;
}

export interface IntakeProgress {
  segments: { group: IntakeProgressGroup; filled: boolean; label: string | null }[];
  filled: number;
  total: number;
  /** "1 of 7 — nice start". Null before anything lands; never a bare "Step N of M". */
  line: string | null;
  /** Set when a segment is held by the high-water mark alone (a document was reclassified). */
  note: string | null;
  glosses: Record<string, string | null>;
  high_water: string[];
}

export interface IntakeResume {
  case_file_id: string;
  title: string | null;
  body: string | null;
  primary: string | null;
  new: string | null;
  /** States the REAL sign-in link lifetime. */
  link_expiry: string | null;
}

/**
 * The 14 canonical coverage regimes (Brock 2026-07-06). Mirrors runtime app/plan_types.py
 * PLAN_TYPES exactly — kept in sync by tests/test_plan_types_canonical.py.
 */
export const COVERAGE_REGIMES = [
  'state_regulated_commercial',
  'erisa_self_funded',
  'medicare_traditional',
  'medicare_advantage',
  'medicaid_ffs',
  'medicaid_mco',
  'dual_eligible',
  'self_pay',
  'tricare',
  'va_champva',
  'fehb_pshb',
  'nonfederal_governmental',
  'stldi',
  'excepted_coverage',
] as const;

export type CoverageRegime = (typeof COVERAGE_REGIMES)[number];

/** Typed coverage attributes (Brock 2026-07-06) — validated against the regime in the runtime. */
export interface CoverageAttributes {
  qmb_status?: boolean | null;
  ihs_prc_eligible?: boolean | null;
  grandfathered?: boolean | null;
  market_segment?: string | null;
  church_plan?: boolean | null;
  medigap?: boolean | null;
  dsnp?: boolean | null;
  governmental_fully_insured?: boolean | null;
}

export interface ConfirmationPrompt {
  field: string;
  read_value: string;
  prompt: string;
  confidence: number;
}

/** Detection metadata surfaced to the confirm screen + settings (DL-82). */
export interface RegimeDetection {
  regime: CoverageRegime | null;
  candidate: CoverageRegime | null;
  confidence: 'high' | 'medium' | 'low';
  method:
    | 'document_format'
    | 'card_branding'
    | 'member_id_pattern'
    | 'user_declared'
    | 'backfill'
    | 'ambiguous';
  evidence: string[];
  verified: boolean;
}

export interface IntakeCapturedData {
  coverage: Record<string, unknown>;
  bills_count: number;
  eobs_count: number;
  visit_context: string | null;
  /** The case's detected/confirmed coverage regime (DL-82); null until settled. */
  coverage_regime: CoverageRegime | null;
  regime_detection: RegimeDetection | null;
}

/** A stored plan-level benefit design proposed for one-tap confirmation (CO-12C). */
export interface PlanProposal {
  plan_library_id: string;
  payer: string;
  plan_name: string | null;
  plan_year: number;
  benefit_design: Record<string, unknown>;
  confidence: number;
  summary: string;
}

export interface IntakeStateResponse {
  /** Null until POST /v1/intake/start — opening the landing creates nothing. */
  case_file_id: string | null;
  intake_status: IntakeStatus;
  intake_mode: 'guided' | 'chat_first';
  /** The planner's pick: a screen id, or 'READY'. */
  current_step: string;
  /** The filled progress groups. */
  completed_steps: string[];
  screen: IntakeScreen;
  progress: IntakeProgress;
  /** intake.chrome.* — save & exit, see an example, help me find it, errors. */
  chrome: Record<string, string>;
  /** "Pick up where you left off" — only when the user returns with an unfinished case. */
  resume?: IntakeResume | null;
  captured_data: IntakeCapturedData;
  missing_items: string[];
  plan_proposal?: PlanProposal | null;
}

/** Every intake write returns the NEXT state — the client never decides where to go. */
export interface IntakeStepAck extends IntakeStateResponse {
  confirmations: ConfirmationPrompt[];
}

export interface IntakeRunResponse {
  case_file_id: string;
  status: string;
  /** The existing reveal/thread — the guided route builds no results UI. */
  next_route: string;
  conversation_id: string | null;
}

export interface IntakeCompletionSummary {
  case_file_id: string;
  intake_status: IntakeStatus;
  captured: string[];
  missing_items: string[];
  summary: string;
}
