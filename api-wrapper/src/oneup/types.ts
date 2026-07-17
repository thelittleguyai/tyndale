/** Setup Call 1 response — POST /user-management/v1/user. */
export interface CreateUserResponse {
  success: boolean;
  /** One-time auth code, exchanged for tokens in Setup Call 2. NOT an access token. */
  code: string;
  oneup_user_id: number;
  app_user_id: string;
  active: boolean;
}

/** OAuth token response — Setup Calls 2 & 5, and refresh. */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  /** Seconds until access_token expires (1up returns 7200 = 2h). */
  expires_in: number;
}

/** One entry from Setup Call 3 — system/payer search. */
export interface Payer {
  /** system_id — used in the payer OAuth redirect (Setup Call 4). */
  id: number;
  name: string;
  address?: string;
  fhirVersion?: string;
  ehr?: string;
  /** The payer's FHIR base URL — where EOB/Coverage/Patient reads go. */
  resourceUrl: string;
  logo?: string;
}

/** A normalized OAuth token set with an absolute expiry. */
export interface TokenSet {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  /** Absolute expiry as epoch milliseconds. */
  expiresAt: number;
}

/** Payer connection details captured during the OAuth handshake. */
export interface PayerConnection extends TokenSet {
  systemId: number;
  resourceUrl: string;
  /**
   * The payer's OAuth base URL used for token refresh (Setup Call 5).
   * Per the runbook this "varies per payer" and is derived from the payer's
   * resourceUrl or 1up docs.
   */
  authBaseUrl: string;
}

/** Everything we persist for one user, keyed by your internal app user id. */
export interface StoredUserTokens {
  appUserId: string;
  oneUpUserId?: number;
  /** 1up-platform tokens from Setup Call 2. */
  oneUp?: TokenSet;
  /** Payer-specific tokens from Setup Call 5, used for FHIR reads. */
  payer?: PayerConnection;
}

export function toTokenSet(res: TokenResponse, now = Date.now()): TokenSet {
  return {
    accessToken: res.access_token,
    refreshToken: res.refresh_token,
    tokenType: res.token_type,
    expiresAt: now + res.expires_in * 1000,
  };
}
