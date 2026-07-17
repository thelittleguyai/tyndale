import type { OneUpConfig } from "../config.js";
import type { TokenStore } from "../store/tokenStore.js";
import { MissingTokensError, OneUpApiError } from "./errors.js";
import {
  toTokenSet,
  type CreateUserResponse,
  type Payer,
  type PayerConnection,
  type StoredUserTokens,
  type TokenResponse,
  type TokenSet,
} from "./types.js";

/** Refresh a token this many ms before it actually expires. */
const EXPIRY_SKEW_MS = 60_000;

export interface OneUpClientOptions {
  config: OneUpConfig;
  store: TokenStore;
  /** Injectable for tests. Defaults to global fetch. */
  fetchImpl?: typeof fetch;
  /** Injectable for tests. Defaults to Date.now. */
  now?: () => number;
}

/**
 * Typed client for the 1upHealth setup chain (Setup Calls 1-5) plus token
 * refresh. FHIR resource reads (EOB/Coverage/Patient) build on `fhirGet` and
 * live in a separate module.
 */
export class OneUpClient {
  private readonly config: OneUpConfig;
  private readonly store: TokenStore;
  private readonly fetchImpl: typeof fetch;
  private readonly now: () => number;

  constructor({ config, store, fetchImpl, now }: OneUpClientOptions) {
    this.config = config;
    this.store = store;
    this.fetchImpl = fetchImpl ?? fetch;
    this.now = now ?? Date.now;
  }

  // --- Setup Call 1: create the 1up user -----------------------------------

  /** POST /user-management/v1/user. Returns a one-time `code`, not a token. */
  async createUser(appUserId: string): Promise<CreateUserResponse> {
    return this.postForm<CreateUserResponse>(
      `${this.config.baseUrls.userManagement}/user-management/v1/user`,
      {
        app_user_id: appUserId,
        client_id: this.config.clientId,
        client_secret: this.config.clientSecret,
      },
    );
  }

  // --- Setup Call 2: exchange code for 1up tokens --------------------------

  async exchangeCodeForTokens(code: string): Promise<TokenResponse> {
    return this.postForm<TokenResponse>(
      `${this.config.baseUrls.auth}/oauth2/token`,
      {
        code,
        grant_type: "authorization_code",
        client_id: this.config.clientId,
        client_secret: this.config.clientSecret,
      },
    );
  }

  /**
   * Convenience: run Setup Calls 1 + 2 and persist the 1up-platform tokens.
   * Safe to call once per user at registration.
   */
  async registerUser(appUserId: string): Promise<StoredUserTokens> {
    const created = await this.createUser(appUserId);
    const tokens = await this.exchangeCodeForTokens(created.code);

    const record: StoredUserTokens = {
      appUserId,
      oneUpUserId: created.oneup_user_id,
      oneUp: toTokenSet(tokens, this.now()),
    };
    await this.store.save(record);
    return record;
  }

  // --- Setup Call 3: search for the patient's payer ------------------------

  /**
   * POST /api/search filtered to patient-access payer endpoints. Requires a
   * valid 1up-platform access token (from Setup Call 2).
   */
  async searchPayers(
    query: string,
    accessToken: string,
    offset = 0,
  ): Promise<Payer[]> {
    return this.postForm<Payer[]>(
      `${this.config.baseUrls.systemSearch}/api/search`,
      {
        query,
        system_type: "PayerPatientAccess",
        offset: String(offset),
      },
      { Authorization: `Bearer ${accessToken}` },
    );
  }

  // --- Setup Call 4: build the payer OAuth redirect URL --------------------

  /**
   * Build the browser redirect that sends the patient to their payer's login.
   * `payerAuthBaseUrl` varies per payer (derived from the payer's resourceUrl
   * or 1up docs). `state` should be a per-session CSRF token you generate.
   */
  buildPayerAuthorizeUrl(args: {
    payerAuthBaseUrl: string;
    systemId: number;
    state: string;
  }): string {
    const params = new URLSearchParams({
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      scope: this.config.scope,
      state: args.state,
    });
    return `${args.payerAuthBaseUrl}/oauth2/authorize/${args.systemId}?${params.toString()}`;
  }

  // --- Setup Call 5: exchange payer auth code for payer tokens -------------

  /**
   * Exchange the code from the OAuth callback for payer-specific tokens and
   * persist them against the user. These tokens authorize FHIR reads.
   */
  async connectPayer(args: {
    appUserId: string;
    payerAuthBaseUrl: string;
    systemId: number;
    resourceUrl: string;
    code: string;
  }): Promise<PayerConnection> {
    const tokens = await this.postForm<TokenResponse>(
      `${args.payerAuthBaseUrl}/oauth2/token`,
      {
        code: args.code,
        grant_type: "authorization_code",
        client_id: this.config.clientId,
        client_secret: this.config.clientSecret,
      },
    );

    const connection: PayerConnection = {
      ...toTokenSet(tokens, this.now()),
      systemId: args.systemId,
      resourceUrl: args.resourceUrl,
      authBaseUrl: args.payerAuthBaseUrl,
    };

    const existing = await this.store.get(args.appUserId);
    await this.store.save({
      appUserId: args.appUserId,
      ...existing,
      payer: connection,
    });
    return connection;
  }

  // --- Token refresh -------------------------------------------------------

  private async refresh(
    authBaseUrl: string,
    refreshToken: string,
  ): Promise<TokenSet> {
    const tokens = await this.postForm<TokenResponse>(
      `${authBaseUrl}/oauth2/token`,
      {
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: this.config.clientId,
        client_secret: this.config.clientSecret,
      },
    );
    return toTokenSet(tokens, this.now());
  }

  /**
   * Return a valid 1up-platform access token, refreshing and persisting if it
   * is expired or about to expire.
   */
  async getValidOneUpToken(appUserId: string): Promise<string> {
    const record = await this.store.get(appUserId);
    if (!record?.oneUp) throw new MissingTokensError(appUserId, "oneUp");

    if (this.isFresh(record.oneUp)) return record.oneUp.accessToken;

    const refreshed = await this.refresh(
      this.config.baseUrls.auth,
      record.oneUp.refreshToken,
    );
    await this.store.save({ ...record, oneUp: refreshed });
    return refreshed.accessToken;
  }

  /**
   * Return a valid payer access token, refreshing against the payer's own
   * OAuth base URL if needed. This is what FHIR reads authenticate with.
   */
  async getValidPayerToken(appUserId: string): Promise<string> {
    const record = await this.store.get(appUserId);
    if (!record?.payer) throw new MissingTokensError(appUserId, "payer");

    if (this.isFresh(record.payer)) return record.payer.accessToken;

    const refreshed = await this.refresh(
      record.payer.authBaseUrl,
      record.payer.refreshToken,
    );
    const payer: PayerConnection = { ...record.payer, ...refreshed };
    await this.store.save({ ...record, payer });
    return payer.accessToken;
  }

  // --- FHIR read foundation ------------------------------------------------

  /**
   * Authenticated GET against the connected payer's FHIR base, using a fresh
   * payer token. `path` is relative to the payer's resourceUrl, e.g.
   * "ExplanationOfBenefit?patient=...". EOB/Coverage/Patient helpers build here.
   */
  async fhirGet<T = unknown>(appUserId: string, path: string): Promise<T> {
    const record = await this.store.get(appUserId);
    if (!record?.payer) throw new MissingTokensError(appUserId, "payer");

    const accessToken = await this.getValidPayerToken(appUserId);
    const base = record.payer.resourceUrl.replace(/\/$/, "");
    const url = `${base}/${path.replace(/^\//, "")}`;

    const res = await this.fetchImpl(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/fhir+json, application/json",
      },
    });
    const body = await res.text();
    if (!res.ok) throw new OneUpApiError(res.status, url, body);
    return JSON.parse(body) as T;
  }

  // --- internals -----------------------------------------------------------

  private isFresh(token: TokenSet): boolean {
    return token.expiresAt - this.now() > EXPIRY_SKEW_MS;
  }

  private async postForm<T>(
    url: string,
    params: Record<string, string>,
    headers: Record<string, string> = {},
  ): Promise<T> {
    const res = await this.fetchImpl(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
        ...headers,
      },
      body: new URLSearchParams(params).toString(),
    });
    const body = await res.text();
    if (!res.ok) throw new OneUpApiError(res.status, url, body);
    return JSON.parse(body) as T;
  }
}
