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
}

export interface OpenCase {
  case_file_id: string;
  headline: string;
  days_open: number;
  next_deadline_date: string | null; // ISO YYYY-MM-DD
  next_deadline_label: string | null;
}

export interface DashboardPayload {
  user: UserBrief;
  coverage: CoverageSummary;
  amount_saved_ytd: number;
  open_cases: OpenCase[];
  status_forward_greeting: string | null;
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
