// Sub-case summary view shapes (D5, Phase C §2 — DL-91). Mirrors runtime/app/schemas/case_summary.py.
import type { NeedsDocumentsItem } from './chat';
import type { DeadlineInfo, ThreeNumberBrief } from './record';

export interface StatusBanner {
  status: string;
  label: string;
  response_deadline: DeadlineInfo | null; // persisted rows only; shadow-mode OK to display
}

export interface FindingBrief {
  finding_id: string;
  finding_type: string; // payer_side | provider_side | encounter_mismatch
  category: string;
  title: string;
  claim: string | null; // Tier-B claim (agent-authored)
  dollar_impact: number | null; // facts['gap'] — an ESTIMATE, labeled in the view
  recommendation: string | null; // Tier-C action (agent-authored)
  responsible_party?: string;
}

/** One phone call's four beats. pick_up/in_writing/push_back are connective copy (D1); the
 *  problem/ask are the finding's own claim/action. */
export interface CallScript {
  when_they_pick_up: string;
  the_problem: string;
  the_ask: string;
  get_it_in_writing: string;
  if_they_push_back: string[];
}

export interface GameplanStep {
  index: number; // 1-based, biggest-dollar-first
  finding_id: string;
  title: string;
  party: 'payer' | 'provider';
  party_label: string;
  dollar_impact: number | null; // ESTIMATE for this item
  script: CallScript;
  // What this call needs on hand (B4), chosen by WHO is being called: a payer call quotes the
  // claim number, a provider call the account number. `reference_kind` is a typed
  // discriminator, not a label — the client owns the words. Null when the uploaded documents
  // didn't carry it, and the strip/dial button then don't render.
  reference_kind: 'claim' | 'account' | null;
  reference_number: string | null;
  phone: string | null; // as printed on that party's document — never guessed or looked up
  responsible_party?: string;
}

export interface CaseSummaryPayload {
  case_file_id: string;
  status_banner: StatusBanner;
  provider: string | null;
  service_date: string | null;
  // The case's primary typed call identifiers (B4); per-step values live on GameplanStep.
  claim_number: string | null;
  account_number: string | null;
  three_number: ThreeNumberBrief | null; // null → needs-documents, never {0,0,0}
  identified_estimate: number; // audit ESTIMATE — labeled separately, never "recovered"
  recovered_so_far: number; // CONFIRMED outcome data only
  findings: FindingBrief[];
  open_items: NeedsDocumentsItem[]; // needs-documents have/need checklist
  next_check_in_date: string | null;
  gameplan: GameplanStep[];
  call_mode_intro: string;
  call_mode_outro: string;
}
