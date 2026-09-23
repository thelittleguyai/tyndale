/**
 * Typed wrappers around the runtime's /v1/admin/* routes (Phase CO-6A).
 *
 * Calls go directly to the runtime (NEXT_PUBLIC_RUNTIME_URL = api.tyndaleapp.net)
 * with credentials:'include' — the session cookie is .tyndaleapp.net-scoped, so it
 * carries from admin. to api., and the runtime CORS allow-list includes the admin
 * origin. The runtime is the source of truth for admin authorization: a non-admin
 * (or unauthenticated) caller gets a 404 from every /v1/admin/* route (DL-60).
 */

import type {
  AdminUserDetail,
  AdminUserSummary,
  QdrantChunkResult,
  QdrantCollectionInfo,
} from '@tyndale/shared';

function resolveRuntimeUrl(): string {
  const url = process.env.NEXT_PUBLIC_RUNTIME_URL;
  if (url) return url.replace(/\/+$/, '');
  // A production build with this unset would silently point admin at localhost — fail loudly.
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'NEXT_PUBLIC_RUNTIME_URL is not set. Set it to the runtime API origin, e.g. https://api.tyndaleapp.net.',
    );
  }
  return 'http://localhost:4000';
}

const RUNTIME = resolveRuntimeUrl();

export class AdminApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${RUNTIME}${path}`, { credentials: 'include', signal });
  if (!res.ok) throw new AdminApiError(res.status, `${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${RUNTIME}${path}`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new AdminApiError(res.status, `${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function post<T = { ok: boolean }>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${RUNTIME}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new AdminApiError(res.status, `${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export interface AdminCaseSummary {
  case_file_id: string;
  user_email: string | null;
  status: string;
  intake_status: string | null;
  created_at: string | null;
  last_activity_at: string | null;
  verdict_status: 'captured' | 'pending';
  summary: string;
}

export interface AdminFinding {
  finding_id: string;
  finding_type: string;
  category: string;
  subagent_source: string;
  voice_tier: 'A' | 'B' | 'C';
  facts: Record<string, unknown>;
  legal_claim: Record<string, unknown> | null;
  recommendation: Record<string, unknown> | null;
  status: string;
}

export interface AdminCaseDetail {
  case_file_id: string;
  user: { user_id: string; email: string | null; user_type: string | null };
  status: string;
  created_at: string | null;
  updated_at: string | null;
  intake_status: string | null;
  visit_context: string | null;
  coverage: Record<string, unknown>;
  documents: Array<Record<string, unknown>>;
  eobs: Array<Record<string, unknown>>;
  findings: AdminFinding[];
  deadlines: Array<Record<string, unknown>>;
  research_log: Array<Record<string, unknown>>;
  plan_versions: { current: unknown; history: unknown[] };
  conversation_history: Array<{ role: string; content: string; timestamp?: string }>;
  last_audit_result: unknown;
}

export interface AdminProvenance {
  case_file_id: string;
  documents: Array<Record<string, unknown>>;
  skills_loaded: string[];
  tools_called: Array<Record<string, unknown>>;
  qdrant_chunks_retrieved: Array<Record<string, unknown>>;
  subagent_calls: Array<Record<string, unknown>>;
  findings_written: AdminFinding[];
  llm_calls: Array<Record<string, unknown>>;
}

// CO-9 verdict v2 (5 options). Legacy rows may still carry 'partially_correct'/'wrong'.
export type VerdictValue =
  | 'correct'
  | 'missed_finding'
  | 'hallucinated'
  | 'partial'
  | 'unable_to_verify';

export interface AdminVerdict {
  verdict_id: string;
  verdict: VerdictValue;
  notes: string | null;
  target_findings: string[] | null;
  target_response: string | null;
  admin_user_id: string;
  captured_at: string | null;
}

export interface AdminDashboard {
  open_cases_count: number;
  pending_verdict_count: number;
  recent_verdicts: Array<{
    verdict_id: string;
    case_file_id: string;
    verdict: VerdictValue;
    captured_at: string | null;
  }>;
  shadow_appeals_pending: number;
}

export const adminGetDashboard = () => get<AdminDashboard>('/v1/admin/dashboard');

export function adminListCases(params: Record<string, string | number | boolean> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();
  return get<{ cases: AdminCaseSummary[]; count: number }>(
    `/v1/admin/cases${qs ? `?${qs}` : ''}`,
  );
}

export const adminGetCase = (id: string) =>
  get<AdminCaseDetail>(`/v1/admin/cases/${encodeURIComponent(id)}`);

export const adminGetProvenance = (id: string) =>
  get<AdminProvenance>(`/v1/admin/cases/${encodeURIComponent(id)}/provenance`);

export const adminGetVerdicts = (id: string) =>
  get<{ case_file_id: string; verdicts: AdminVerdict[] }>(
    `/v1/admin/cases/${encodeURIComponent(id)}/verdicts`,
  );

export async function adminSubmitVerdict(
  id: string,
  body: {
    verdict: VerdictValue;
    notes?: string | null;
    missed_findings?: string[] | null;
    hallucinated_claims?: string[] | null;
    target_findings?: string[] | null;
    target_response?: string | null;
  },
): Promise<{ verdict_id: string; stored: boolean }> {
  return post<{ verdict_id: string; stored: boolean }>(
    `/v1/admin/cases/${encodeURIComponent(id)}/verdict`,
    body,
  );
}

export const adminExportCase = (id: string) =>
  get<Record<string, unknown>>(`/v1/admin/cases/${encodeURIComponent(id)}/export`);

// --- Module 1: users -------------------------------------------------------
export function adminListUsers(params: Record<string, string | number> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();
  return get<{ users: AdminUserSummary[]; count: number }>(
    `/v1/admin/users${qs ? `?${qs}` : ''}`,
  );
}

export const adminGetUser = (id: string) =>
  get<AdminUserDetail>(`/v1/admin/users/${encodeURIComponent(id)}`);

export interface AdminUserAuditEntry {
  event_id: string;
  timestamp: string | null;
  event_type: string;
  actor: string;
  action: string | null;
  outcome: string;
}

export const adminGetUserAudit = (id: string) =>
  get<{ user_id: string; entries: AdminUserAuditEntry[]; count: number }>(
    `/v1/admin/users/${encodeURIComponent(id)}/audit-log`,
  );

export const adminBlockUser = (id: string, reason: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/block`, { reason });
export const adminUnblockUser = (id: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/unblock`);
export const adminResetOnboarding = (id: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/reset-onboarding`);
export const adminForceLogout = (id: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/force-logout`);
export const adminSendMagicLink = (id: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/send-magic-link`);
export const adminSoftDeleteUser = (id: string) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/soft-delete`);
export const adminSetRole = (id: string, role: 'admin' | 'user') =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/set-role`, { role });
/** doc 40 §D: the per-user front-door override. `null` clears it (back to cohort → default). Audited. */
export const adminSetIntakeMode = (id: string, intake_mode: 'guided' | 'chat_first' | null) =>
  post(`/v1/admin/users/${encodeURIComponent(id)}/set-intake-mode`, { intake_mode });

// --- Module 2: knowledge / qdrant ------------------------------------------
export const adminListCollections = () =>
  get<{ collections: QdrantCollectionInfo[] }>('/v1/admin/qdrant/collections');

export const adminSearchCollection = (
  name: string,
  body: {
    query: string;
    filters?: Record<string, unknown>;
    limit?: number;
    include_staging?: boolean;
  },
) =>
  post<{ collection: string; results: QdrantChunkResult[] }>(
    `/v1/admin/qdrant/collections/${encodeURIComponent(name)}/search`,
    body,
  );

export const adminGetChunk = (name: string, chunkId: string) =>
  get<Record<string, unknown>>(
    `/v1/admin/qdrant/collections/${encodeURIComponent(name)}/chunk/${encodeURIComponent(chunkId)}`,
  );

export const adminPromoteChunk = (name: string, chunkId: string) =>
  post(
    `/v1/admin/qdrant/collections/${encodeURIComponent(name)}/promote/${encodeURIComponent(chunkId)}`,
  );

export const adminPromoteBatch = (name: string, chunkIds: string[]) =>
  post(`/v1/admin/qdrant/collections/${encodeURIComponent(name)}/promote-batch`, {
    chunk_ids: chunkIds,
  });

// --- Module 4: audit log ---------------------------------------------------
export interface AdminAuditEntry {
  event_id: string;
  timestamp: string | null;
  event_type: string;
  actor: string;
  target_user_id: string | null;
  case_file_id: string | null;
  action: string | null;
  tools_invoked: string[] | null;
  outcome: string;
  payload: Record<string, unknown>;
}

function qstr(params: Record<string, string | number>): string {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();
  return qs ? `?${qs}` : '';
}

export const adminGetAuditLog = (params: Record<string, string | number> = {}) =>
  get<{ entries: AdminAuditEntry[]; count: number; total_matched: number; capped: boolean }>(
    `/v1/admin/audit-log${qstr(params)}`,
  );

export const adminExportAuditLog = (params: Record<string, string | number> = {}) =>
  get<{ exported_at: string | null; filters: Record<string, unknown>; count: number; entries: AdminAuditEntry[] }>(
    `/v1/admin/audit-log/export${qstr(params)}`,
  );

// --- Module 5: system + crons ----------------------------------------------
export interface AdminSystemHealth {
  deploy_sha: string | null;
  deploy_timestamp: string | null;
  db_pool: { size: number | null; checked_out: number | null; overflow: number | null };
  qdrant_status: string;
  anthropic_status: string;
  last_claude_call: {
    status: string;
    at: string | null;
    path: string | null;
    detail: string | null;
  };
  // Item 1/2 — last real-agent audit run + rolling p50/p95 wall-clock (per-replica).
  last_audit_run: {
    at: string | null;
    duration_seconds: number | null;
    reason: string | null;
    regens: number | null;
    path: string | null;
    stage_ms: Record<string, number> | null;
  };
  audit_duration_percentiles: {
    count: number;
    p50_seconds: number | null;
    p95_seconds: number | null;
  };
  // e2e 2026-09-23 B1 — retrieval_degraded: the live per-process ledger + the durable
  // last-N knowledge-tool outcomes. Absent on an older runtime.
  retrieval?: {
    status: 'healthy' | 'degraded' | 'unknown';
    live: {
      status: string;
      window_calls: number;
      window_errors: number;
      error_rate: number;
      voyage: Record<string, { last_status: number | null; last_error: string | null; last_error_at: string | null; errors: number }>;
      last_alert_at: string | null;
    };
    durable: { window: number; calls: number; errors: number; error_rate: number; last_error_at: string | null; last_error: string | null };
  };
  // readiness B2 — failed crons (last 7 days) and the one alert list a pager reads.
  failed_crons?: Array<{ cron_name: string; status: string; started_at: string | null; finished_at: string | null; error: string | null }>;
  alerts?: Array<{ kind: string; severity: 'high' | 'medium' | 'low'; detail: string; action: string; at: string | null }>;
  /** e2e re-test 2026-09-23 item 3 — open system_error audits, read from the cases. */
  system_errors?: {
    open: number;
    auto_recovery: boolean;
    recovering: number;
    needs_a_person: number;
    needs_a_person_cases: string[];
    last_at: string | null;
  };
  recent_errors: Array<{
    event_id: string;
    timestamp: string | null;
    event_type: string;
    actor: string;
    outcome: string;
    error: string | null;
  }>;
  runtime_version: string;
  node_env: string;
}

export interface AdminCronSummary {
  cron_name: string;
  schedule: string;
  last_run_at: string | null;
  last_status: string | null;
  currently_running: boolean;
}

export interface AdminCronRun {
  run_id: string;
  cron_name: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  triggered_source: string;
  triggered_by: string | null;
  summary_json: Record<string, unknown> | null;
  error_message: string | null;
}

export const adminSystemHealth = () => get<AdminSystemHealth>('/v1/admin/system/health');
export const adminListCrons = () => get<{ crons: AdminCronSummary[] }>('/v1/admin/crons');
export const adminTriggerCron = (name: string) =>
  post<{ run_id: string; status: string }>(`/v1/admin/crons/${encodeURIComponent(name)}/trigger`);
export const adminCronRuns = (name: string) =>
  get<{ cron_name: string; runs: AdminCronRun[]; count: number }>(
    `/v1/admin/crons/${encodeURIComponent(name)}/runs`,
  );

// --- Module 6: knowledge gaps ----------------------------------------------
export interface AdminGap {
  gap_id: string;
  case_id: string | null;
  agent_name: string;
  gap_type: string;
  query: string;
  context_summary: string | null;
  confidence_score: number | null;
  logged_at: string | null;
  resolved_at: string | null;
  resolved_by_source: string | null;
}

export const adminListGaps = (params: Record<string, string | number> = {}) =>
  get<{ gaps: AdminGap[]; count: number }>(`/v1/admin/knowledge-gaps${qstr(params)}`);

export const adminAggregateGaps = (params: Record<string, string | number> = {}) =>
  get<{
    group_by: string;
    groups?: Array<{ key: string; count: number }>;
    clusters?: Array<{ cluster: string; representative_query: string; count: number }>;
  }>(`/v1/admin/knowledge-gaps/aggregate${qstr(params)}`);

export const adminResolveGap = (gapId: string, resolvedBySource: string) =>
  post(`/v1/admin/knowledge-gaps/${encodeURIComponent(gapId)}/resolve`, {
    resolved_by_source: resolvedBySource,
  });

// --- Internal analytics (P0) ------------------------------------------------
export interface AdminMetric {
  key: string;
  definition: string; // Rule 1 — always present, rendered beside the value
  kind: 'ratio' | 'count';
  numerator: number;
  denominator: number | null;
  value: number | null;
  backfilled: boolean;
}
export interface AdminAnalyticsPanel {
  key: string;
  title: string;
  metrics: AdminMetric[];
}
export interface AdminStatusBoard {
  flags: Record<string, boolean>;
  crons: string[];
  drop_counts: Record<string, number>;
  not_yet_live_events: string[];
}
export interface AdminAnalytics {
  window_days: number;
  panels: AdminAnalyticsPanel[];
  status: AdminStatusBoard;
}
export const adminGetAnalytics = (days = 30) =>
  get<AdminAnalytics>(`/v1/admin/analytics?days=${days}`);

// ── Human Review Phase 1 (doc 39 §7, 2026-09-18) ─────────────────────────────────────────

export type ReviewState =
  | 'unreviewed'
  | 'in_review'
  | 'approved'
  | 'disapproved'
  | 'cant_verify'
  | 're_review';
export type ConfidenceBand = 'high' | 'medium' | 'low' | 'unknown';
export type DisapprovalCause = 'content_gap' | 'reasoning_error' | 'bad_input' | 'stale_data_source';
export type DisapprovalType = 'partially_correct' | 'wrong' | 'missed_finding' | 'hallucinated' | 'partial';

export type IntakeMode = 'guided' | 'chat_first';

export interface ReviewQueueItem {
  review_id: string;
  case_file_id: string;
  user_masked: string | null;
  /** The user's own Record-row title (plausibility-gated server-side) — null renders neutral. */
  provider: string | null;
  service_date: string | null;
  /** Distinct classified document types on the case, e.g. ['Itemized bill', 'EOB']. */
  document_set: string[];
  /** The front door that opened the case (doc 40 §D) — both routes share this queue. */
  intake_mode: IntakeMode | null;
  run_seq: number;
  state: ReviewState;
  terminal_status: string;
  incomplete_reason: string | null;
  confidence_band: ConfidenceBand;
  findings_count: number;
  net_finding_usd: number | null;
  sampled: boolean;
  triggers: string[];
  flags: { first_case: boolean; system_error: boolean; canary: boolean; guard_drop?: boolean; material_disagreement: boolean };
  enqueued_at: string | null;
  age_hours: number | null;
  in_review_at: string | null;
  decided_at: string | null;
  reviewer_masked: string | null;
  prior_review_id: string | null;
  verdict: { verdict_id: string; verdict: string; cause: string | null } | null;
}

export interface ReviewHealth {
  unreviewed: number;
  in_review: number;
  median_age_hours: number | null;
  approved_7d: number;
  disapproved_7d: number;
  approval_rate_7d: number | null;
  approved_30d: number;
  disapproved_30d: number;
  approval_rate_30d: number | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  count: number;
  limit: number;
  offset: number;
  /** Rows per state under every active filter EXCEPT state — all six keys always present. */
  state_counts: Record<ReviewState, number>;
  health: ReviewHealth;
}

export interface ReviewSettings {
  review_sample_pct: number;
  env_default_pct: number;
  triggers: Record<string, boolean>;
}

export interface ReviewWhyLine {
  key: string;
  label: string;
  value: string | number | Record<string, number> | null;
}

/** What a citation chip opens — resolved server-side from the run's own retrieval + the case's
 *  documents; `unresolved` is said plainly (nothing is fetched or guessed client-side). */
export type ReviewCitationSource =
  | { kind: 'document'; doc_index: number; document_id: string; page: number | null }
  | {
      kind: 'chunk';
      collection: string | null;
      title: string | null;
      effective_date: string | null;
      last_verified: string | null;
      text: string | null;
      truncated: boolean;
    }
  | { kind: 'unresolved' };

export interface ReviewCitation {
  authority: string;
  section: string | null;
  src_id: string;
  marker: string;
  source: ReviewCitationSource;
}

export interface ReviewFinding extends AdminFinding {
  responsible_party: string;
  amount_usd: number | null;
  basis_codes: string[];
  citations: ReviewCitation[];
  confidence: number | string | null;
  /** The AGENT'S internal reasoning. Null = none recorded. Never a reviewer's verdict note. */
  analyst_notes: string | null;
  why: ReviewWhyLine[];
  created_at: string | null;
}

export interface ReviewDocumentCard {
  /** Unique across documents AND eobs — `index` is only the position within its own list. */
  doc_index: number;
  kind: 'document' | 'eob';
  index: number;
  document_id: string | null;
  has_text: boolean;
  document_type: string | null;
  filename: string | null;
  uploaded_at: string | null;
  page_count: number | null;
  text_chars: number;
  claim_number: string | null;
  account_number: string | null;
  extraction_status: string | null;
}

export interface ReviewVerdictRecord {
  verdict_id: string;
  verdict: string;
  notes: string | null;
  cause: DisapprovalCause | null;
  structured_note: { concluded: string; should_have_concluded: string; input_or_rule: string } | null;
  target_findings: string[] | null;
  reviewer_masked: string | null;
  captured_at: string | null;
}

export interface ReviewWorkspace {
  /** Who is looking — masked, for "Reviewing as …" and to tell my claim from someone else's. */
  viewer: { masked: string | null };
  case: {
    case_file_id: string;
    user_masked: string | null;
    provider: string | null;
    service_date: string | null;
    document_set: string[];
    intake_mode: IntakeMode | null;
    status: string;
    incomplete_reason: string | null;
    intake_status: string | null;
    created_at: string | null;
    updated_at: string | null;
  };
  review: ReviewQueueItem | null;
  review_chain: ReviewQueueItem[];
  left: {
    documents: ReviewDocumentCard[];
    eobs: ReviewDocumentCard[];
    extraction: {
      line_items: Record<string, unknown>[];
      coverage: Record<string, unknown>;
      encounter_confirmations: unknown[];
    };
    journey: { event: string; at: string | null; properties: Record<string, unknown> }[];
  };
  tabs: {
    analysis: {
      three_numbers: Record<string, unknown> | null;
      disclosure: { tier: number; label: string; missing_inputs: string[]; chase_inputs: string[] } | null;
      summary: string;
      /** e2e re-test 2026-09-23 item 1 — the audit completed but its summary is still owed. */
      summary_pending?: boolean;
      summary_retry_attempts?: number;
      summary_retry_after?: string | null;
      result_status: string | null;
      documents_needed: { key: string; label: string; have: boolean }[];
      findings: ReviewFinding[];
    };
    conversation: Record<string, unknown>[];
    results: {
      gameplan: Record<string, unknown>[];
      identifiers: Record<string, string | null>;
      tiers: {
        finding_id: string;
        voice_tier: string;
        tier_a_facts: Record<string, unknown>;
        tier_b_claim: Record<string, unknown> | null;
        tier_c_recommendation: Record<string, unknown> | null;
      }[];
      deadlines: Record<string, unknown>[];
      outcomes: Record<string, unknown>[];
    };
    provenance: {
      case_file_id: string;
      documents: Record<string, unknown>[];
      skills_loaded: string[];
      tools_called: { tools_invoked: string[] | null; args: unknown; result: unknown; outcome: string | null; timestamp: string | null }[];
      qdrant_chunks_retrieved: unknown[];
      subagent_calls: { actor: string | null; outcome: string | null; timestamp: string | null; detail: unknown }[];
      findings_written: AdminFinding[];
      llm_calls: { model: string | null; outcome: string | null; timestamp: string | null; usage: unknown }[];
      user_answers: {
        kind: 'encounter_confirmation' | 'coverage_input' | 'attestation';
        label: string;
        code: string | null;
        value: string | number | null;
        note: string | null;
        at: string | null;
      }[];
      priors_applied: {
        input: string;
        low: number;
        base: number;
        high: number;
        unit: string;
        source: string;
        as_of: string | null;
        placeholder: boolean;
        tier: number | null;
        resulting_range: { low: number; high: number } | null;
      }[];
      pricing_reference: { tool: string; outcome: string | null; at: string | null; source: string | null; as_of: string | null }[];
      tripwires: Record<string, unknown>[];
      research_log: unknown[];
      api_pulls: { status: string; label: string };
      live_lookups: { status: string; label: string };
      missing_data: { status: string; label: string };
      retrieval_misses: { status: string; label: string };
    };
  };
  verdicts: ReviewVerdictRecord[];
}

export interface ReviewVerdictBody {
  action: 'approve' | 'disapprove' | 'cant_verify';
  note?: string;
  verdict_type?: DisapprovalType;
  scope?: 'whole_case' | 'findings';
  target_findings?: string[];
  cause?: DisapprovalCause;
  structured_note?: { concluded: string; should_have_concluded: string; input_or_rule: string };
}

export function adminReviewQueue(
  params: Record<string, string | number | boolean> = {},
  signal?: AbortSignal,
) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v !== undefined && v !== null) q.set(k, String(v));
  }
  const s = q.toString();
  return get<ReviewQueueResponse>(`/v1/admin/review/queue${s ? `?${s}` : ''}`, signal);
}

export const adminReviewSettings = () => get<ReviewSettings>('/v1/admin/review/settings');
export const adminSetReviewSampling = (pct: number) =>
  put<{ review_sample_pct: number }>('/v1/admin/review/settings', { review_sample_pct: pct });
export const adminReviewWorkspace = (caseId: string, signal?: AbortSignal) =>
  get<ReviewWorkspace>(`/v1/admin/review/cases/${encodeURIComponent(caseId)}`, signal);

// ── document viewer ─────────────────────────────────────────────────────────────────────
/** A document's key on a case: its document_id, or `idx-<doc_index>` for entries that predate it. */
export const reviewDocumentKey = (d: { document_id: string | null; doc_index: number }) =>
  d.document_id ?? `idx-${d.doc_index}`;

/** The stored file, fetched WITH the session cookie (an <img src> to another origin would not
 *  carry it). The caller turns it into an object URL and revokes it on close. */
export async function adminReviewDocumentFile(caseId: string, docKey: string, signal?: AbortSignal) {
  const path = `/v1/admin/review/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docKey)}`;
  const res = await fetch(`${RUNTIME}${path}`, { credentials: 'include', signal, cache: 'no-store' });
  if (!res.ok) {
    throw new AdminApiError(res.status, res.status === 404 ? 'The stored file is unavailable.' : `${path} -> ${res.status}`);
  }
  return { blob: await res.blob(), contentType: res.headers.get('content-type') ?? 'application/octet-stream' };
}

export const adminReviewDocumentText = (caseId: string, docKey: string, signal?: AbortSignal) =>
  get<ReviewDocumentCard & { text: string; chars: number }>(
    `/v1/admin/review/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(docKey)}/text`,
    signal,
  );

export interface ReviewClaimResult {
  review_id: string;
  state: ReviewState;
  claimed: boolean;
  held_by_me: boolean;
  reviewer_masked: string | null;
}

/** Take a pending run for review. Explicit + idempotent: opening the workspace never claims. */
export const adminReviewClaim = (caseId: string, takeOver = false) =>
  post<ReviewClaimResult>(`/v1/admin/review/cases/${encodeURIComponent(caseId)}/claim`, {
    take_over: takeOver,
  });

/** Posts a verdict; a 422 surfaces the server's validation list as the error message. */
export async function adminReviewVerdict(caseId: string, body: ReviewVerdictBody) {
  const path = `/v1/admin/review/cases/${encodeURIComponent(caseId)}/verdict`;
  const res = await fetch(`${RUNTIME}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${path} -> ${res.status}`;
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (Array.isArray(j.detail)) detail = j.detail.map(String).join(' · ');
      else if (typeof j.detail === 'string') detail = j.detail;
    } catch {
      /* keep the status message */
    }
    throw new AdminApiError(res.status, detail);
  }
  return (await res.json()) as {
    review_id: string;
    state: ReviewState;
    verdict_id: string;
    verdict: string;
    cause: DisapprovalCause | null;
    phase2_route: string | null;
  };
}
