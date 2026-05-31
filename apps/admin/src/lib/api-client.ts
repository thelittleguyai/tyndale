/**
 * Typed wrappers around the runtime's /v1/admin/* routes (Phase CO-6A).
 *
 * Calls go directly to the runtime (NEXT_PUBLIC_RUNTIME_URL = api.tyndaleapp.net)
 * with credentials:'include' — the session cookie is .tyndaleapp.net-scoped, so it
 * carries from admin. to api., and the runtime CORS allow-list includes the admin
 * origin. The runtime is the source of truth for admin authorization: a non-admin
 * (or unauthenticated) caller gets a 404 from every /v1/admin/* route (DL-60).
 */

const RUNTIME = process.env.NEXT_PUBLIC_RUNTIME_URL || 'http://localhost:4000';

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

export type VerdictValue = 'correct' | 'partially_correct' | 'wrong';

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
    target_findings?: string[] | null;
    target_response?: string | null;
  },
): Promise<{ verdict_id: string; stored: boolean }> {
  const res = await fetch(`${RUNTIME}/v1/admin/cases/${encodeURIComponent(id)}/verdict`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new AdminApiError(res.status, `verdict -> ${res.status}`);
  return (await res.json()) as { verdict_id: string; stored: boolean };
}
