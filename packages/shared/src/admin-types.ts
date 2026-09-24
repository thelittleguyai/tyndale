// CO-9 admin console — shared API contract types.

export type UserStatus = 'active' | 'blocked' | 'soft_deleted';

export interface AdminUserSummary {
  user_id: string;
  email: string;
  user_type: string;
  status: UserStatus;
  created_at: string | null;
  last_admin_action_at: string | null;
  case_file_count: number;
  /** Absent on an older runtime. */
  intake_mode?: AdminIntakeModeView;
}

/** Which front door a user gets, and why (doc 40 §D): admin override → cohort → env default. */
export interface AdminIntakeModeView {
  override: 'guided' | 'chat_first' | null;
  cohort: 'guided' | 'default' | null;
  resolved: 'guided' | 'chat_first';
  source: 'override' | 'cohort' | 'default';
}

export interface AdminUserDetail extends AdminUserSummary {
  is_blocked: boolean;
  blocked_at: string | null;
  blocked_by: string | null;
  blocked_reason: string | null;
  soft_deleted_at: string | null;
  soft_deleted_by: string | null;
  jwt_version: number;
  service_consent: boolean;
  improvement_consent: boolean;
  updated_at: string | null;
  last_activity_at: string | null;
  recent_case_files: Array<{
    case_file_id: string;
    status: string;
    intake_status: string | null;
    created_at: string | null;
  }>;
  active_provider_sanctions: unknown[];
}

export interface QdrantCollectionInfo {
  name: string;
  exists: boolean;
  total: number;
  live: number;
  staging: number;
  sources: Array<{ source: string; last_seen: string | null }>;
}

/**
 * Admin › Knowledge — the payer-instructions corpus behind "Where to find it" (portal guide
 * 2026-07-02, guided Phase 2 item G) and its quarterly re-verify clock. A verified entry carries
 * the steps exactly as a member sees them; an unverified one only what the hands-on pass must fill.
 */
export interface PayerCorpusEntry {
  document_type: string;
  screen_id: string | null;
  verified: boolean;
  verified_on: string | null;
  due_on: string | null;
  overdue: boolean;
  source: string;
  claim: string;
  steps: string[];
  origin: 'portal_guide' | 'receiving_dock';
}

export interface PayerCorpusView {
  source: string;
  reverify_every_months: number;
  today: string;
  next_due: string | null;
  overdue: number;
  verified: number;
  unverified: number;
  payers: Array<{ payer_id: string; name: string; entries: PayerCorpusEntry[] }>;
}

export interface QdrantChunkResult {
  id: string;
  score: number;
  partition_status: string;
  payload: Record<string, unknown>;
}

export interface AuditLogEntry {
  event_id: string;
  timestamp: string | null;
  event_type: string;
  actor: string;
  action: string | null;
  outcome: string;
}

export interface CronRunSummary {
  cron_name: string;
  schedule: string;
  last_run_at: string | null;
  last_status: string | null;
  next_scheduled_at: string | null;
  currently_running: boolean;
}

export interface KnowledgeGapEntry {
  gap_id: string;
  agent_name: string;
  gap_type: 'no_data' | 'low_confidence' | 'self_reported';
  query: string;
  confidence_score: number | null;
  logged_at: string | null;
  resolved_at: string | null;
}
