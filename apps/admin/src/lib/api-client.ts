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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${RUNTIME}${path}`, { credentials: 'include' });
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
