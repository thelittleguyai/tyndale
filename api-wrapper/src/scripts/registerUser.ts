import { loadConfig } from "../config.js";
import { OneUpClient } from "../oneup/client.js";
import { InMemoryTokenStore } from "../store/tokenStore.js";

/**
 * Runs Setup Calls 1-2 for a given app user id and prints the stored tokens.
 *
 *   npm run register-user -- usr_abc123
 *
 * Uses an in-memory store, so tokens are printed but not persisted across runs.
 */
async function main(): Promise<void> {
  const appUserId = process.argv[2];
  if (!appUserId) {
    console.error("Usage: npm run register-user -- <app_user_id>");
    process.exit(1);
  }

  const config = loadConfig();
  const client = new OneUpClient({ config, store: new InMemoryTokenStore() });

  console.log(`[${config.environment}] registering user ${appUserId}...`);
  const record = await client.registerUser(appUserId);

  console.log("oneUpUserId:", record.oneUpUserId);
  console.log(
    "access token (truncated):",
    record.oneUp?.accessToken.slice(0, 8) + "...",
  );
  console.log("expires at:", new Date(record.oneUp?.expiresAt ?? 0).toISOString());
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
