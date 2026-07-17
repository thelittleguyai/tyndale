/** Thrown when a 1up endpoint returns a non-2xx response. */
export class OneUpApiError extends Error {
  readonly status: number;
  readonly url: string;
  readonly body: string;

  constructor(status: number, url: string, body: string) {
    super(`1up API ${status} for ${url}: ${body.slice(0, 500)}`);
    this.name = "OneUpApiError";
    this.status = status;
    this.url = url;
    this.body = body;
  }
}

/** Thrown when we need tokens for a user but none are stored / connected. */
export class MissingTokensError extends Error {
  constructor(appUserId: string, kind: "oneUp" | "payer") {
    super(
      `No ${kind} tokens stored for user "${appUserId}". ` +
        (kind === "payer"
          ? "The patient must complete the payer OAuth flow first."
          : "Register the user (Setup Calls 1-2) first."),
    );
    this.name = "MissingTokensError";
  }
}
