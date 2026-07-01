# LiteLLM proxy (Phase 1C skeleton)

`config.yaml` here is a **local-dev skeleton only**. It defines the Claude routes
(lead_planner, bill_detective, math_person, legal_researcher, strategist,
code_validator, judge), points them at the appropriate Claude models, and enables
prompt caching at the proxy level.

## The primary Claude path is now Azure AI Foundry (CO-18 / DL-79)

As of CO-18 the runtime calls Claude **directly through Azure AI Foundry** (the
Anthropic Messages API at `{endpoint}/anthropic`) using the runtime's **managed
identity** — no API key — so Azure's BAA covers Claude. That path is selected in
`app/agents/runner._client()` when `USE_FOUNDRY` + `FOUNDRY_ENDPOINT` are set, and
is the intended production path (`assert_production_safety()` requires it in prod).

This LiteLLM proxy is now a **config-gated fallback**, not the default: the factory
uses it only when `LITELLM_PROXY_URL` is set AND Foundry is off. Anthropic-direct
(raw `ANTHROPIC_API_KEY`) is the last-resort dev/emergency path. Client precedence in
`_client()`: **Foundry → LiteLLM proxy → Anthropic-direct.** The Foundry account,
Claude deployments, and runtime RBAC live in `infra/envs/dev/ai_foundry.tf`.

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
