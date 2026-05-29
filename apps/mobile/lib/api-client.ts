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
  // @ts-expect-error process.env.EXPO_PUBLIC_* is injected by Metro
  process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:4000';

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
  const res = await fetch(`${BASE_URL}/v1/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as UploadResponse;
}

/** POST /v1/audit — kick off the audit. */
export async function postAudit(case_file_id: string): Promise<AuditResult> {
  const res = await fetch(`${BASE_URL}/v1/audit`, {
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
  const res = await fetch(`${BASE_URL}/v1/dashboard`);
  if (!res.ok) {
    throw new Error(`dashboard fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as DashboardPayload;
}

/** GET /v1/cases — list of the user's case files. */
export async function getCases(): Promise<CasesListPayload> {
  const res = await fetch(`${BASE_URL}/v1/cases`);
  if (!res.ok) {
    throw new Error(`cases fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as CasesListPayload;
}

/** GET /v1/coverage — full coverage detail (case-detail screens consume; the
 * dashboard uses the summary embedded inside getDashboard). */
export async function getCoverage(): Promise<CoverageDetailPayload> {
  const res = await fetch(`${BASE_URL}/v1/coverage`);
  if (!res.ok) {
    throw new Error(`coverage fetch failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as CoverageDetailPayload;
}
