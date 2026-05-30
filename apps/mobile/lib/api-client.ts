/**
 * Tyndale runtime API client (walking skeleton).
 *
 * Base URL comes from EXPO_PUBLIC_API_BASE_URL — set this to
 *   http://localhost:4000  for `expo start --web` against a local runtime
 *   https://<runtime-fqdn>/  for the dev Container App
 *
 * Phase 4 wires real auth headers (JWT bearer from NextAuth → mobile session).
 */

const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:4000';

// Every runtime call must send the session cookie. The runtime enforces real
// auth, and the app + API live on different .tyndaleapp.net subdomains (cross-
// origin), so without credentials:'include' the cookie isn't sent and the call
// 401s ("not authenticated"). Routing all calls through this wrapper guarantees
// it — a missing include is exactly why the dashboard fetch returned 401.
function cfetch(input: string, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { credentials: 'include', ...init });
}

export interface UploadResponse {
  case_file_id: string;
  document_id: string;
  filename: string;
  received_bytes: number;
  note?: string;
}

export interface Citation {
  authority: string;
  section?: string | null;
  src_id: string;
  marker: string;
}

export interface ThreeNumberAudit {
  provider_billed: number;
  eob_member_responsibility: number;
  tyndale_computed: number;
  currency: string;
}

export interface FindingOut {
  finding_id: string;
  finding_type: 'payer_side' | 'provider_side' | 'encounter_mismatch';
  category: string;
  subagent_source: string;
  voice_tier: 'A' | 'B' | 'C';
  facts: Record<string, unknown>;
  legal_claim?: Record<string, unknown> | null;
  recommendation?: Record<string, unknown> | null;
  citations: Citation[];
}

export interface AuditResult {
  case_file_id: string;
  status: 'open' | 'in_progress' | 'complete' | 'resolved' | 'archived';
  audit: ThreeNumberAudit;
  findings: FindingOut[];
  summary: string;
}

/**
 * POST /v1/upload — multipart upload. Accepts a Blob (web) or a
 * { uri, name, mimeType } shape (native expo-document-picker output).
 */
export async function upload(
  file: Blob | { uri: string; name: string; mimeType?: string },
): Promise<UploadResponse> {
  const form = new FormData();
  if (file instanceof Blob) {
    form.append('file', file, (file as any).name ?? 'upload');
  } else {
    // React Native FormData accepts this shape
    form.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.mimeType ?? 'application/octet-stream',
    } as any);
  }
  const res = await cfetch(`${BASE_URL}/v1/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as UploadResponse;
}

/** POST /v1/audit — kick off the audit. */
export async function postAudit(case_file_id: string): Promise<AuditResult> {
  const res = await cfetch(`${BASE_URL}/v1/audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_file_id }),
  });
  if (!res.ok) {
    throw new Error(`audit failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as AuditResult;
}

/** GET /v1/audit/{id} — fetch current state (used for the polling pattern). */
export async function getAudit(case_file_id: string): Promise<AuditResult> {
  const res = await fetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}`,
  );
  if (!res.ok) {
    throw new Error(`audit fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as AuditResult;
}

// --- Dashboard ---------------------------------------------------------------

import type {
  CasesListPayload,
  CoverageDetailPayload,
  DashboardPayload,
} from '@tyndale/shared';

export type {
  CasesListPayload,
  CoverageDetailPayload,
  CoverageMeter,
  CoverageSummary,
  DashboardPayload,
  OpenCase,
} from '@tyndale/shared';

/** GET /v1/dashboard — the composite payload for the signed-in dashboard. */
export async function getDashboard(): Promise<DashboardPayload> {
  const res = await cfetch(`${BASE_URL}/v1/dashboard`);
  if (!res.ok) {
    throw new Error(`dashboard fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as DashboardPayload;
}

/** GET /v1/cases — list of the user's case files. */
export async function getCases(): Promise<CasesListPayload> {
  const res = await cfetch(`${BASE_URL}/v1/cases`);
  if (!res.ok) {
    throw new Error(`cases fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as CasesListPayload;
}

/** GET /v1/coverage — full coverage detail (case-detail screens consume; the
 * dashboard uses the summary embedded inside getDashboard). */
export async function getCoverage(): Promise<CoverageDetailPayload> {
  const res = await cfetch(`${BASE_URL}/v1/coverage`);
  if (!res.ok) {
    throw new Error(`coverage fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as CoverageDetailPayload;
}

// --- Encounter verification (Phase 2I) --------------------------------------

import type {
  AuditStatusResponse,
  ConfirmationsAccepted,
  ExtractResult,
  LineItemConfirmation,
} from '@tyndale/shared';

export type {
  AuditStatusResponse,
  ConfirmationsAccepted,
  ExtractResult,
  LineItem,
  LineItemConfirmation,
  LineItemResponse,
} from '@tyndale/shared';

/** POST /v1/audit/{id}/extract — Bill Detective translates line items. */
export async function extractLineItems(case_file_id: string): Promise<ExtractResult> {
  const res = await fetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/extract`,
    { method: 'POST' },
  );
  if (!res.ok) throw new Error(`extract failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ExtractResult;
}

/** GET /v1/audit/{id}/line-items — idempotent fetch for the verification UI. */
export async function getLineItems(case_file_id: string): Promise<ExtractResult> {
  const res = await fetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/line-items`,
  );
  if (!res.ok) throw new Error(`line-items fetch failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ExtractResult;
}

/** POST /v1/audit/{id}/confirmations — submit the full set; kicks finalize. */
export async function submitConfirmations(
  case_file_id: string,
  confirmations: LineItemConfirmation[],
): Promise<ConfirmationsAccepted> {
  const res = await fetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/confirmations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmations }),
    },
  );
  if (!res.ok) throw new Error(`confirmations failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ConfirmationsAccepted;
}

/** GET /v1/audit/{id}/status — poll the case status. */
export async function getAuditStatus(case_file_id: string): Promise<AuditStatusResponse> {
  const res = await fetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/status`,
  );
  if (!res.ok) throw new Error(`status fetch failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as AuditStatusResponse;
}

// --- Feedback + consent (Phase 2J) ------------------------------------------

import type {
  CaseFeedbackPayload,
  ConsentHistoryPayload,
  FeedbackAck,
  FeedbackEvent,
  OutcomePromptsPayload,
  UserProfile,
} from '@tyndale/shared';

export type {
  CaseFeedbackPayload,
  ConsentHistoryPayload,
  FeedbackAck,
  FeedbackEvent,
  FeedbackType,
  OutcomePrompt,
  OutcomePromptsPayload,
  ResolvedValue,
  StructuredReason,
  ThumbsValue,
  UserProfile,
} from '@tyndale/shared';

/** POST /v1/feedback — store a feedback event (consent read server-side). */
export async function submitFeedback(event: FeedbackEvent): Promise<FeedbackAck> {
  const res = await cfetch(`${BASE_URL}/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event),
  });
  if (!res.ok) throw new Error(`feedback failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as FeedbackAck;
}

/** GET /v1/feedback/case/{id} — restore per-target rating state. */
export async function getCaseFeedback(case_file_id: string): Promise<CaseFeedbackPayload> {
  const res = await fetch(
    `${BASE_URL}/v1/feedback/case/${encodeURIComponent(case_file_id)}`,
  );
  if (!res.ok) throw new Error(`case feedback failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as CaseFeedbackPayload;
}

/** GET /v1/feedback/outcome-prompts — eligible outcome follow-ups. */
export async function getOutcomePrompts(): Promise<OutcomePromptsPayload> {
  const res = await cfetch(`${BASE_URL}/v1/feedback/outcome-prompts`);
  if (!res.ok) throw new Error(`outcome prompts failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as OutcomePromptsPayload;
}

/** GET /v1/user/me — current user profile (dev-stub auth until Phase 2K). */
export async function getUserProfile(): Promise<UserProfile> {
  const res = await cfetch(`${BASE_URL}/v1/user/me`);
  if (!res.ok) throw new Error(`profile fetch failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as UserProfile;
}

/** PATCH /v1/user/me — flip improvement consent (immediate). */
export async function updateConsent(improvement_consent: boolean): Promise<UserProfile> {
  const res = await cfetch(`${BASE_URL}/v1/user/me`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ improvement_consent }),
  });
  if (!res.ok) throw new Error(`consent update failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as UserProfile;
}

/** Small helper to build a FeedbackEvent with id + timestamp filled in. */
export function makeFeedbackEvent(
  partial: Omit<FeedbackEvent, 'event_id' | 'timestamp'>,
): FeedbackEvent {
  return {
    event_id:
      (globalThis.crypto?.randomUUID?.() ?? `evt_${Date.now()}_${Math.round(Math.random() * 1e9)}`),
    timestamp: new Date().toISOString(),
    ...partial,
  };
}

// --- Auth (Phase 2K) --------------------------------------------------------

export interface SessionResponse {
  user: UserProfile | null;
}

/** POST /v1/auth/login — returns the Google consent URL to redirect to. */
export async function getGoogleAuthUrl(): Promise<string> {
  const res = await cfetch(`${BASE_URL}/v1/auth/login`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`login init failed: ${res.status} ${await res.text()}`);
  return ((await res.json()) as { authorization_url: string }).authorization_url;
}

/** POST /v1/auth/magic-link-request — always 200 (anti-enumeration); throws
 * on 429 so the UI can surface a rate-limit message. */
export async function requestMagicLink(email: string, return_url?: string): Promise<void> {
  const res = await cfetch(`${BASE_URL}/v1/auth/magic-link-request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, return_url }),
  });
  if (res.status === 429) {
    const retry = res.headers.get('Retry-After');
    throw new Error(`Too many requests — try again in ${retry ?? 'a few'} seconds.`);
  }
  if (!res.ok) throw new Error(`magic link request failed: ${res.status}`);
}

/** GET /v1/auth/session — current session (user: null if not signed in). */
export async function getAuthSession(): Promise<SessionResponse> {
  const res = await cfetch(`${BASE_URL}/v1/auth/session`, { credentials: 'include' });
  if (res.status === 401) return { user: null };
  if (!res.ok) throw new Error(`session fetch failed: ${res.status}`);
  return (await res.json()) as SessionResponse;
}

/** POST /v1/auth/logout — clears the session cookie. */
export async function logout(): Promise<void> {
  await cfetch(`${BASE_URL}/v1/auth/logout`, { method: 'POST', credentials: 'include' });
}
