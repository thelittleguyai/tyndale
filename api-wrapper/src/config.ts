export type OneUpEnvironment = "sandbox" | "production";

export interface OneUpConfig {
  environment: OneUpEnvironment;
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  scope: string;
  baseUrls: {
    /** Setup Call 1 — user-management. */
    userManagement: string;
    /** Setup Calls 2 & refresh — 1up OAuth token endpoint. */
    auth: string;
    /** Setup Call 3 — payer/system search. */
    systemSearch: string;
  };
}

const DEFAULT_BASE_URLS = {
  userManagement: "https://api.1up.health",
  auth: "https://auth.1up.health",
  systemSearch: "https://system-search.1up.health",
} as const;

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. See .env.example.`,
    );
  }
  return value;
}

/**
 * Build config from environment variables. Base URLs fall back to 1up's
 * documented defaults; override them only when 1up hands you a different host.
 */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): OneUpConfig {
  const environment: OneUpEnvironment =
    env.ONEUP_ENVIRONMENT === "production" ? "production" : "sandbox";

  return {
    environment,
    clientId: required("ONEUP_CLIENT_ID"),
    clientSecret: required("ONEUP_CLIENT_SECRET"),
    redirectUri: required("ONEUP_REDIRECT_URI"),
    scope: env.ONEUP_SCOPE ?? "user/*.read",
    baseUrls: {
      userManagement:
        env.ONEUP_BASE_USER_MANAGEMENT ?? DEFAULT_BASE_URLS.userManagement,
      auth: env.ONEUP_BASE_AUTH ?? DEFAULT_BASE_URLS.auth,
      systemSearch:
        env.ONEUP_BASE_SYSTEM_SEARCH ?? DEFAULT_BASE_URLS.systemSearch,
    },
  };
}
