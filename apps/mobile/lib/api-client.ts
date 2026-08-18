/**
 * Tyndale runtime API client (walking skeleton).
 *
 * Base URL comes from EXPO_PUBLIC_API_BASE_URL — set this to
 *   http://localhost:4000  for `expo start --web` against a local runtime
 *   https://<runtime-fqdn>/  for the dev Container App
 *
 * Phase 4 wires real auth headers (JWT bearer from NextAuth → mobile session).
 */

function resolveBaseUrl(): string {
  const url = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (url) return url.replace(/\/+$/, '');
  // A production/preview build with this unset would silently point every call at
  // localhost — fail loudly instead. Local dev (`expo start`, __DEV__) keeps the default.
  if (!__DEV__) {
    throw new Error(
      'EXPO_PUBLIC_API_BASE_URL is not set. Set it in the build profile (eas.json / env) to the ' +
        'runtime API origin, e.g. https://api.tyndaleapp.net.',
    );
  }
  return 'http://localhost:4000';
}

const BASE_URL = resolveBaseUrl();

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

/** A file to upload — a Blob (web) or expo-document-picker's native shape. */
export type UploadFilePart = Blob | { uri: string; name: string; mimeType?: string };

export interface UploadedDoc {
  document_id: string;
  filename: string;
  document_type: string;
  classification_confidence: number;
  size_bytes: number;
}

export interface MultiUploadResponse {
  case_file_id: string;
  uploads: UploadedDoc[];
  /** Chat-first routing (DL-91): true for a new case when the flag is on; route to the thread. */
  chat_first?: boolean;
  conversation_id?: string | null;
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
  /**
   * Grounding line (conformance E4/H3). ALWAYS populated by the server: either the resolved
   * "source: …" line or the explicit no-source state — never empty. `has_source` says which,
   * so the UI can style a real source as a citation chip and an unsourced claim as the honest
   * admission it is. A card must render one of the two; never a bare claim.
   */
  source_line: string;
  has_source: boolean;
}

/** Deterministic disclosure tier (DL-85): 0 grounded · 1 note · 2 disclose · 3 chase. */
export interface Disclosure {
  tier: number;
  label: string;
  missing_inputs: string[];
  chase_inputs: string[];
}

/** Coverage-regime context the audit ran under (DL-82). */
export interface AuditProvenance {
  coverage_regime: string | null;
  regime_verified: boolean;
  assumptions: string[];
}

/** One checklist item to finish a needs_documents audit (PHI-free: type + how-to-get). */
export interface DocumentNeed {
  key: string; // eob | itemized_bill | sbc
  label: string;
  how_to_get: string;
  /** True once the case already has this document — drives the checked/unchecked UI state. */
  have: boolean;
}

export interface AuditResult {
  case_file_id: string;
  status: string; // 'complete' | 'audit_incomplete' | case status
  /** Null on an audit_incomplete result with no three-number finding. */
  audit: ThreeNumberAudit | null;
  findings: FindingOut[];
  summary: string;
  audit_provenance?: AuditProvenance | null;
  disclosure?: Disclosure | null;
  /**
   * Why an audit_incomplete result stopped:
   *  'needs_documents' — user-actionable; render the positive "here's what we found; to finish
   *                      we need…" screen with documents_needed, NO failure language.
   *  'system_error'    — not user-actionable; render the apology ("our team has been notified").
   */
  incomplete_reason?: string | null;
  /** Populated only when incomplete_reason === 'needs_documents'. */
  documents_needed?: DocumentNeed[];
}

/**
 * POST /v1/upload — multipart upload of N files in one request (Phase 2L).
 * Accepts Blobs (web) or expo-document-picker shapes (native). Optionally
 * attaches to an existing case via caseFileId. All files land on one case file.
 */
export async function uploadDocuments(
  files: UploadFilePart[],
  caseFileId?: string,
): Promise<MultiUploadResponse> {
  const form = new FormData();
  for (const f of files) {
    if (f instanceof Blob) {
      form.append('files', f, (f as any).name ?? 'upload');
    } else {
      form.append('files', {
        uri: f.uri,
        name: f.name,
        type: f.mimeType ?? 'application/octet-stream',
      } as any);
    }
  }
  if (caseFileId) form.append('case_file_id', caseFileId);
  const res = await cfetch(`${BASE_URL}/v1/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as MultiUploadResponse;
}

/** Backwards-compat single-file helper — wraps uploadDocuments. */
export async function uploadDocument(
  file: UploadFilePart,
  caseFileId?: string,
): Promise<MultiUploadResponse> {
  return uploadDocuments([file], caseFileId);
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
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}`,
  );
  if (!res.ok) {
    throw new Error(`audit fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as AuditResult;
}

/** EOB-completeness confirmation (DL-86). `confirmed` is null until the user answers. */
export interface EobCompleteness {
  eob_count: number;
  plan_year: number | null;
  date_start: string | null;
  date_end: string | null;
  dated_count: number;
  undated_count: number;
  patient_names: string[];
  covers_family: boolean;
  confirmed: boolean | null;
  question: string;
}

/** GET /v1/audit/{id}/eob-completeness — "does that look like all of them?" summary. */
export async function getEobCompleteness(case_file_id: string): Promise<EobCompleteness> {
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/eob-completeness`,
  );
  if (!res.ok) throw new Error(`eob-completeness failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as EobCompleteness;
}

/** POST /v1/audit/{id}/eob-completeness/confirm — the user's yes/no answer. */
export async function confirmEobCompleteness(
  case_file_id: string,
  all_uploaded: boolean,
): Promise<EobCompleteness> {
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/eob-completeness/confirm`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all_uploaded }),
    },
  );
  if (!res.ok) throw new Error(`eob-confirm failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as EobCompleteness;
}

// --- Dashboard ---------------------------------------------------------------

import type {
  CaseSummaryPayload,
  CasesListPayload,
  CoverageDetailPayload,
  DashboardPayload,
  RecordPayload,
} from '@tyndale/shared';

export type {
  CaseSummaryPayload,
  CasesListPayload,
  CoverageDetailPayload,
  CoverageMeter,
  CoverageSummary,
  DashboardPayload,
  GameplanStep,
  OpenCase,
  RecordPayload,
  SubCaseRow,
} from '@tyndale/shared';

/** GET /v1/record — the Tyndale Record (D5). 404 when the flag is off. */
export async function getRecord(windowMonths = 12): Promise<RecordPayload> {
  const res = await cfetch(`${BASE_URL}/v1/record?window_months=${windowMonths}`);
  if (!res.ok) throw new Error(`getRecord ${res.status}`);
  return (await res.json()) as RecordPayload;
}

/** GET /v1/case/{id}/summary — the permanent sub-case summary (D5 §2). 404 when the flag is off. */
export async function getCaseSummary(caseFileId: string): Promise<CaseSummaryPayload> {
  const res = await cfetch(`${BASE_URL}/v1/case/${caseFileId}/summary`);
  if (!res.ok) throw new Error(`getCaseSummary ${res.status}`);
  return (await res.json()) as CaseSummaryPayload;
}

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
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/extract`,
    { method: 'POST' },
  );
  if (!res.ok) throw new Error(`extract failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ExtractResult;
}

/** GET /v1/audit/{id}/line-items — idempotent fetch for the verification UI. */
export async function getLineItems(case_file_id: string): Promise<ExtractResult> {
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(case_file_id)}/line-items`,
  );
  if (!res.ok) throw new Error(`line-items fetch failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ExtractResult;
}

export interface VerifyTextResult {
  result: 'mapped' | 'fallback' | 'partial_fallback' | 'crisis' | 'blocked';
  method: string;
  conversation_id?: string | null;
}

/**
 * POST /v1/audit/{id}/verify-text — chat-first D4b. Maps a free-text verification reply to a
 * pre-selectable suggestion (rendered from the thread). NEVER commits — the confirming tap does.
 */
export async function verifyText(caseFileId: string, utterance: string): Promise<VerifyTextResult> {
  const res = await cfetch(
    `${BASE_URL}/v1/audit/${encodeURIComponent(caseFileId)}/verify-text`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ utterance }),
    },
  );
  if (!res.ok) throw new Error(`verifyText ${res.status}`);
  return res.json();
}

/** POST /v1/audit/{id}/confirmations — submit the full set; kicks finalize. */
export async function submitConfirmations(
  case_file_id: string,
  confirmations: LineItemConfirmation[],
): Promise<ConfirmationsAccepted> {
  const res = await cfetch(
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
  const res = await cfetch(
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
  const res = await cfetch(
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

/** Record what happened on ONE call, from call mode's "How did it go?" routes (H6).
 *
 *  This is the outcome-capture denominator: how many people who got a gameplan actually made
 *  the call. It is NOT a case outcome — none of the three routes resolves anything, so it
 *  carries no money and never retires the dashboard's "did it work?" follow-up permanently.
 *  Idempotent server-side per (case, step), so a double tap can't inflate the count. */
export async function recordCallOutcome(
  caseFileId: string,
  findingId: string,
  outcome: 'fixing_it' | 'pushed_back' | 'left_message',
): Promise<void> {
  const res = await cfetch(`${BASE_URL}/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event_id: `call-${caseFileId}-${findingId}-${outcome}`,
      timestamp: new Date().toISOString(),
      case_file_id: caseFileId,
      response_id: findingId,
      feedback_type: 'implicit_signal',
      call_outcome: outcome,
    }),
  });
  if (!res.ok) throw new Error(`call outcome failed: ${res.status}`);
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

/** Self-service account deletion: scrubs identity + insurance PHI, invalidates the session.
 *  The caller should sign out immediately after (the server also clears the cookie). */
export async function requestAccountDeletion(): Promise<void> {
  const res = await cfetch(`${BASE_URL}/v1/user/me/delete-request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`account deletion failed: ${res.status} ${await res.text()}`);
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

// --- Intake wizard (Phase CO-1A) --------------------------------------------

import type {
  CoverageRegime,
  IntakeCompletionSummary,
  IntakeStateResponse,
  IntakeStepAck,
} from '@tyndale/shared';

export type {
  ConfirmationPrompt,
  IntakeCapturedData,
  IntakeCompletionSummary,
  IntakeStatus,
  IntakeStateResponse,
  IntakeStep,
  IntakeStepAck,
} from '@tyndale/shared';

async function intakeJson<T>(path: string, body: unknown): Promise<T> {
  const res = await cfetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

/** GET /v1/intake/state — resume point + captured/missing (creates the user's
 * first case file if they have none — the new-user entry point). */
export async function getIntakeState(caseFileId?: string): Promise<IntakeStateResponse> {
  const q = caseFileId ? `?case_file_id=${encodeURIComponent(caseFileId)}` : '';
  const res = await cfetch(`${BASE_URL}/v1/intake/state${q}`);
  if (!res.ok) throw new Error(`intake state failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as IntakeStateResponse;
}

/** POST /v1/intake/step/{step}/manual-entry — persist a step's typed fields. */
export async function intakeManualEntry(
  step: string,
  fields: Record<string, unknown>,
  caseFileId: string,
): Promise<IntakeStepAck> {
  return intakeJson(`/v1/intake/step/${encodeURIComponent(step)}/manual-entry`, {
    case_file_id: caseFileId,
    ...fields,
  });
}

/** POST /v1/intake/step/{step}/skip — advance, persist nothing. */
export async function intakeSkipStep(step: string, caseFileId: string): Promise<IntakeStepAck> {
  return intakeJson(`/v1/intake/step/${encodeURIComponent(step)}/skip`, {
    case_file_id: caseFileId,
  });
}

/** POST /v1/intake/step/insurance-card/extract — OCR a card; returns low-confidence
 * fields as trivial yes/no confirmations. */
export async function intakeExtractInsuranceCard(
  documentId: string,
  caseFileId: string,
): Promise<IntakeStepAck> {
  return intakeJson('/v1/intake/step/insurance-card/extract', {
    case_file_id: caseFileId,
    document_id: documentId,
  });
}

/** POST /v1/intake/plan-proposal/confirm — accept a Plan-Library-proposed design (DL-87).
 * The proposal is presented as "your plan" for confirmation; provenance stays internal. */
export async function confirmPlanProposal(
  planLibraryId: string,
  caseFileId: string,
): Promise<IntakeStateResponse> {
  return intakeJson('/v1/intake/plan-proposal/confirm', {
    case_file_id: caseFileId,
    plan_library_id: planLibraryId,
  });
}

/** POST /v1/intake/plan-proposal/reject — "something's off"; optionally send corrections. */
export async function rejectPlanProposal(
  planLibraryId: string,
  caseFileId: string,
  correctedDesign?: Record<string, unknown>,
): Promise<IntakeStateResponse> {
  return intakeJson('/v1/intake/plan-proposal/reject', {
    case_file_id: caseFileId,
    plan_library_id: planLibraryId,
    corrected_design: correctedDesign ?? {},
  });
}

/** POST /v1/intake/step/coverage-regime-confirm/confirm — the verification-ladder
 * answer to "How are you covered?" (DL-82). Marks the regime verified (user_declared). */
export async function intakeConfirmRegime(
  regime: CoverageRegime,
  caseFileId: string,
): Promise<IntakeStepAck> {
  return intakeJson('/v1/intake/step/coverage-regime-confirm/confirm', {
    case_file_id: caseFileId,
    coverage_regime: regime,
  });
}

/** POST /v1/intake/visit-context — store the free-text "what were you seen for". */
export async function setVisitContext(
  visitContext: string,
  caseFileId: string,
): Promise<IntakeStepAck> {
  return intakeJson('/v1/intake/visit-context', {
    case_file_id: caseFileId,
    visit_context: visitContext,
  });
}

/** POST /v1/intake/complete — validate + mark complete, return the summary. */
export async function completeIntake(caseFileId: string): Promise<IntakeCompletionSummary> {
  return intakeJson('/v1/intake/complete', { case_file_id: caseFileId });
}

// ─── Chat (Phase CO-10) ──────────────────────────────────────────────────────
import type {
  ChatStreamEvent,
  Conversation,
  ConversationDetail,
  ConversationList,
} from '@tyndale/shared';

export async function listConversations(params?: {
  case_id?: string;
  mode?: 'per_case' | 'freeform' | 'all';
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ConversationList> {
  const q = new URLSearchParams();
  if (params?.case_id) q.set('case_id', params.case_id);
  if (params?.mode) q.set('mode', params.mode);
  if (params?.include_archived) q.set('include_archived', 'true');
  if (params?.limit != null) q.set('limit', String(params.limit));
  if (params?.offset != null) q.set('offset', String(params.offset));
  const qs = q.toString();
  const res = await cfetch(`${BASE_URL}/v1/conversations${qs ? `?${qs}` : ''}`);
  if (!res.ok) throw new Error(`listConversations ${res.status}`);
  return res.json();
}

export async function createConversation(caseId?: string): Promise<Conversation> {
  const res = await cfetch(`${BASE_URL}/v1/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(caseId ? { case_id: caseId } : {}),
  });
  if (!res.ok) throw new Error(`createConversation ${res.status}`);
  return res.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const res = await cfetch(`${BASE_URL}/v1/conversations/${id}`);
  if (!res.ok) throw new Error(`getConversation ${res.status}`);
  return res.json();
}

export async function patchConversation(
  id: string,
  body: { title?: string; is_archived?: boolean },
): Promise<Conversation> {
  const res = await cfetch(`${BASE_URL}/v1/conversations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`patchConversation ${res.status}`);
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await cfetch(`${BASE_URL}/v1/conversations/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`deleteConversation ${res.status}`);
}

export async function stopStream(id: string): Promise<void> {
  await cfetch(`${BASE_URL}/v1/conversations/${id}/stop`, { method: 'POST' });
}

/** Soft-delete a junk / mistaken case (no findings, no completed audit). 409 if it has results. */
export async function removeCase(caseFileId: string): Promise<void> {
  const res = await cfetch(`${BASE_URL}/v1/cases/${encodeURIComponent(caseFileId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`removeCase ${res.status}`);
}

export function parseSseBlock(raw: string): ChatStreamEvent | null {
  let event = 'message';
  let data = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event: event as ChatStreamEvent['event'], data: JSON.parse(data) };
  } catch {
    return null;
  }
}

/**
 * POST a message and stream the SSE response, invoking `onEvent` per event.
 * EventSource is GET-only, so this is a POST + manual SSE parse over the fetch
 * ReadableStream (web). On native (no streaming body) it falls back to reading
 * the full response then replaying events — non-incremental but functional.
 */
export async function streamMessage(
  conversationId: string,
  content: string,
  onEvent: (ev: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await cfetch(`${BASE_URL}/v1/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ content }),
      signal,
    });
  } catch (e) {
    onEvent({ event: 'error', data: { code: 'NETWORK', message: String(e) } });
    onEvent({ event: 'done', data: {} });
    return;
  }

  if (res.status === 429) {
    const body = await res.json().catch(() => ({}));
    onEvent({ event: 'error', data: { code: body.code ?? 'RATE_LIMITED', ...body } });
    onEvent({ event: 'done', data: {} });
    return;
  }

  const stream = res.body as ReadableStream<Uint8Array> | null;
  if (!res.ok || !stream || typeof stream.getReader !== 'function') {
    // Native / no-streaming fallback: read it all, replay events.
    const text = await res.text().catch(() => '');
    if (!res.ok && !text) {
      onEvent({ event: 'error', data: { code: `HTTP_${res.status}`, message: '' } });
    }
    for (const block of text.split('\n\n')) {
      const ev = parseSseBlock(block);
      if (ev) onEvent(ev);
    }
    if (!text) onEvent({ event: 'done', data: {} });
    return;
  }

  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseSseBlock(block);
      if (ev) onEvent(ev);
    }
  }
}

// ── CO-17: profile + insurance ──────────────────────────────────────────────

export interface ProfileState {
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
  phone: string | null;
  email: string;
  profile_completed: boolean;
  has_insurance_card: boolean;
  /** Reminders preference (2026-08-19): gates nudge chases + check-ins ONLY — case
   *  updates (audit-ready, recovery, magic links) always arrive. */
  email_notifications_enabled: boolean;
}

export interface ProfilePatch {
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
  phone?: string | null;
  accept_terms?: boolean;
  email_notifications_enabled?: boolean;
}

export interface InsuranceInfo {
  insurer: string | null;
  plan_name: string | null;
  plan_type: string | null;
  member_id: string | null;
  group_number: string | null;
  member_name: string | null;
  effective_date: string | null;
  rx_bin: string | null;
  rx_pcn: string | null;
  copays: unknown;
  extraction_status: string | null;
  has_front: boolean;
  has_back: boolean;
}

export interface CardUploadResult {
  card_type: string;
  extraction_status: string;
  insurance_info: InsuranceInfo;
}

export async function getProfileState(): Promise<ProfileState> {
  const res = await cfetch(`${BASE_URL}/v1/profile/state`);
  if (!res.ok) throw new Error(`profile state failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ProfileState;
}

// --- Billing (Item 4, DL-16). `enabled:false` while the dark scaffold is off → hide the UI. ---
export interface BillingStatus {
  enabled: boolean;
  active?: boolean;
  status?: string;
  plan?: string | null;
  current_period_end?: string | null;
  free_analyses_remaining?: number;
}

export async function getBillingStatus(): Promise<BillingStatus> {
  const res = await cfetch(`${BASE_URL}/v1/billing/status`);
  if (!res.ok) throw new Error(`billing status failed: ${res.status}`);
  return (await res.json()) as BillingStatus;
}

export async function startBillingCheckout(plan: 'monthly' | 'yearly'): Promise<string> {
  const res = await cfetch(`${BASE_URL}/v1/billing/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  });
  if (!res.ok) throw new Error(`checkout failed: ${res.status} ${await res.text()}`);
  return ((await res.json()) as { checkout_url: string }).checkout_url;
}

export async function patchProfile(body: ProfilePatch): Promise<ProfileState> {
  const res = await cfetch(`${BASE_URL}/v1/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`profile update failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as ProfileState;
}

export async function getInsuranceInfo(): Promise<InsuranceInfo> {
  const res = await cfetch(`${BASE_URL}/v1/insurance/info`);
  if (!res.ok) throw new Error(`insurance info failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as InsuranceInfo;
}

export async function uploadInsuranceCard(
  card_type: 'front' | 'back',
  image_base64: string,
  mime_type: string,
  file_size?: number,
): Promise<CardUploadResult> {
  const res = await cfetch(`${BASE_URL}/v1/insurance/card/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_type, image_base64, mime_type, file_size }),
  });
  if (!res.ok) throw new Error(`card upload failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as CardUploadResult;
}

/** URL for a card side's image — the runtime streams it (or 302s to a signed Blob URL). */
export function insuranceCardImageUrl(card_type: 'front' | 'back'): string {
  return `${BASE_URL}/v1/insurance/card/${card_type}/image`;
}

/** Fetch a card image with credentials (follows the signed-URL redirect) and return an
 *  object URL usable as an <Image> source — works cross-origin where a bare <img> can't
 *  send the cookie. Web only; returns null elsewhere or on failure. */
export async function fetchCardImageObjectUrl(
  card_type: 'front' | 'back',
): Promise<string | null> {
  if (typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') return null;
  try {
    const res = await cfetch(insuranceCardImageUrl(card_type));
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  } catch {
    return null;
  }
}


/** Authored copy for a screen with no case thread yet (upload). Registry-sourced so the app
 *  never hardcodes product voice; a field is null when the string is deliberately withheld. */
export type SurfaceCopy = Record<string, string | null>;

export async function getSurfaceCopy(
  surface: 'upload' | 'status' | 'access_request' | 'settings',
): Promise<SurfaceCopy> {
  const res = await cfetch(`${BASE_URL}/v1/copy/${surface}`);
  if (!res.ok) return {};
  return (await res.json()) as SurfaceCopy;
}

/** A statutory access / deletion / correction request (§A2 state 5).
 *
 *  The response is IDENTICAL whether or not the person appears anywhere in Tyndale — it is a
 *  receipt, never a lookup. Nothing about the result may be branched on to imply otherwise. */
export type AccessRequestBody = {
  request_type: 'access' | 'deletion' | 'correction';
  patient_name: string;
  contact: string;
  relationship?: string;
  details?: string;
};

export async function submitAccessRequest(
  body: AccessRequestBody,
): Promise<{ received: boolean; message: string }> {
  const res = await cfetch(`${BASE_URL}/v1/access-request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`access request failed (${res.status})`);
  return (await res.json()) as { received: boolean; message: string };
}
