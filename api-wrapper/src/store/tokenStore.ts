import type { StoredUserTokens } from "../oneup/types.js";

/**
 * Persistence boundary for per-user 1up + payer tokens.
 *
 * The in-memory implementation below is fine for local testing. In production,
 * back this with the PostgreSQL `users` table (tokens stored encrypted, per the
 * runbook) by implementing this same interface.
 */
export interface TokenStore {
  get(appUserId: string): Promise<StoredUserTokens | undefined>;
  save(tokens: StoredUserTokens): Promise<void>;
}

export class InMemoryTokenStore implements TokenStore {
  private readonly rows = new Map<string, StoredUserTokens>();

  async get(appUserId: string): Promise<StoredUserTokens | undefined> {
    return this.rows.get(appUserId);
  }

  async save(tokens: StoredUserTokens): Promise<void> {
    this.rows.set(tokens.appUserId, tokens);
  }
}
