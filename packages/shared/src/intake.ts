/**
 * Guided intake wizard API contracts (Phase CO-1A).
 *
 * Mirrors runtime/app/schemas/intake.py one-for-one. The runtime is the contract
 * owner; this is the typed mirror for the Expo wizard.
 */

export const INTAKE_STEPS = [
  'welcome',
  'insurance-card',
  'coverage-regime-confirm',
  'coverage-details',
  'benefits',
  'deductible',
  'oop-max',
  'bills',
  'eobs',
  'visit-context',
  'complete',
] as const;

export type IntakeStep = (typeof INTAKE_STEPS)[number];
export type IntakeStatus = 'not_started' | 'in_progress' | 'complete';

/** The seven coverage regimes (DL-82). Mirrors runtime app/sources/regime_detection.py. */
export const COVERAGE_REGIMES = [
  'commercial',
  'medicare_traditional',
  'medicare_advantage',
  'medicaid',
  'dual_qmb',
  'self_pay',
  'tricare_va',
] as const;

export type CoverageRegime = (typeof COVERAGE_REGIMES)[number];

/** Steps the user may skip (graceful degradation — equal-weight in the UI). */
export const SKIPPABLE_STEPS: ReadonlySet<IntakeStep> = new Set<IntakeStep>([
  'insurance-card',
  'coverage-regime-confirm',
  'coverage-details',
  'benefits',
  'deductible',
  'oop-max',
  'eobs',
  'visit-context',
]);

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
  case_file_id: string;
  intake_status: IntakeStatus;
  current_step: IntakeStep;
  completed_steps: IntakeStep[];
  captured_data: IntakeCapturedData;
  missing_items: string[];
  /** CO-12C: a pending PlanLibrary proposal to confirm before prompting for an SBC. */
  plan_proposal?: PlanProposal | null;
}

export interface IntakeStepAck {
  case_file_id: string;
  intake_status: IntakeStatus;
  current_step: IntakeStep;
  completed_steps: IntakeStep[];
  confirmations: ConfirmationPrompt[];
}

export interface IntakeCompletionSummary {
  case_file_id: string;
  intake_status: IntakeStatus;
  captured: string[];
  missing_items: string[];
  summary: string;
}
