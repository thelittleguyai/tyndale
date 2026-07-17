import { loadConfig } from "../config.js";
import { OneUpClient } from "../oneup/client.js";
import { InMemoryTokenStore } from "../store/tokenStore.js";

/**
 * Registers a throwaway user, then runs Setup Call 3 to search payers.
 *
 *   npm run search-payers -- "Blue Cross Blue Shield"
 *
 * Prints each payer's system id + FHIR resourceUrl, plus the OAuth redirect URL
 * you'd send the patient to (Setup Call 4). Note the payer OAuth base URL varies
 * per payer; here we derive it from the resourceUrl origin as a starting guess.
 */
async function main(): Promise<void> {
  const query = process.argv[2];
  if (!query) {
    console.error('Usage: npm run search-payers -- "<carrier name>"');
    process.exit(1);
  }

  const config = loadConfig();
  const client = new OneUpClient({ config, store: new InMemoryTokenStore() });

  const record = await client.registerUser(`probe_${Date.now()}`);
  const accessToken = record.oneUp!.accessToken;

  const payers = await client.searchPayers(query, accessToken);
  if (payers.length === 0) {
    console.log("No payers matched:", query);
    return;
  }

  for (const payer of payers) {
    const authBaseUrl = new URL(payer.resourceUrl).origin;
    console.log("—".repeat(40));
    console.log("name:       ", payer.name);
    console.log("system_id:  ", payer.id);
    console.log("resourceUrl:", payer.resourceUrl);
    console.log(
      "authorize:  ",
      client.buildPayerAuthorizeUrl({
        payerAuthBaseUrl: authBaseUrl,
        systemId: payer.id,
        state: "REPLACE_WITH_CSRF_TOKEN",
      }),
    );
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
