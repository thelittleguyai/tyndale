# LiteLLM proxy (Phase 1C skeleton)

`config.yaml` here is a **local-dev skeleton only**. It defines the Claude routes
(lead_planner, bill_detective, math_person, legal_researcher, strategist,
code_validator, judge), points them at the appropriate Claude models, and enables
prompt caching at the proxy level.

## What this skeleton does NOT do (Phase 4, with the security/HIPAA contact)

- Weekly API-key rotation (the proxy is the single credential broker — see
  discipline rule D16).
- Per-route allow-lists.
- Request-level audit logging into the encrypted audit stream.
- Real Bedrock / Azure Foundry fallback deployments (only Anthropic-direct works
  here; the fallback entries are placeholders).

## Local dev

`docker compose up` starts the proxy on `:4001` (mapped from the container's 4000)
using this config. Set `ANTHROPIC_API_KEY` in `.env.local` to exercise it; left
blank in Phase 1C since the runtime uses stubs (`USE_REAL_CLAUDE=false`).

The production proxy configuration is owned by the security/HIPAA contact in Phase 4.
