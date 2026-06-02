# Chat surface (Phase CO-10)

Conversational chat layered on top of the V1-Lite one-shot analysis. The initial
upload→analysis flow is unchanged; chat lets users ask follow-up questions in a
thread, in two modes.

## Modes

| | Per-case | Freeform |
|---|---|---|
| `conversations.case_id` | NOT NULL (→ `case_files`) | NULL |
| Context fed to the agent | case file, encounters, prior analysis, conversation history | conversation history only |
| Tools available | case tools + knowledge base | **knowledge base only** (no case-file access) |
| System prompt | `intelligence-layer/prompts/chat_modes/per_case_mode.md` | `…/freeform_mode.md` |
| Special behavior | cites case line items / encounters | on a **specific situation** ("$4,200 bill, Aetna paid $800…") emits `create_case_cta` instead of speculating |

A chat turn is the Lead Planner posture run multi-turn: `lead_planner.chat_mode_for_case(case_id)`
selects the mode, `app/agents/chat.py` runs the streaming loop, and the mode also
sets the tool allowlist (`tool_names_for`) so freeform genuinely cannot reach case data.

When `use_real_claude=False` (tests + local dev), the turn runs a deterministic
**fixture stream** so the SSE contract is testable without an LLM. With real creds
it uses `client.messages.stream()` + the tool loop.

## API

- `GET /v1/conversations?case_id&mode&include_archived&limit&offset` — list (own conversations)
- `POST /v1/conversations {case_id?}` — create (per-case if `case_id`, else freeform)
- `GET /v1/conversations/{id}` — metadata + ordered messages
- `PATCH /v1/conversations/{id} {title?, is_archived?}` — rename / archive
- `DELETE /v1/conversations/{id}` — soft delete (`is_archived=TRUE`; hard delete only via admin user-soft-delete, CO-9)
- `POST /v1/conversations/{id}/messages {content}` — **SSE stream** (below)
- `POST /v1/conversations/{id}/stop` — set the streaming assistant message to `stopped` (204)

Non-owner access → **403**.

## SSE event schema

`POST /v1/conversations/{id}/messages` responds `text/event-stream`. Events
(`event:` + `data:` JSON), in order:

| event | data |
|---|---|
| `user_message_persisted` | `{ message_id, sequence_number }` |
| `assistant_message_started` | `{ message_id }` |
| `tool_call_started` | `{ tool_name, subagent, input_summary }` |
| `tool_call_completed` | `{ tool_name, output_summary, duration_ms }` |
| `token` | `{ delta, tier? }` — `tier` ∈ A/B/C |
| `citation_added` | `{ source_id, title, url, snippet, … }` |
| `assistant_message_completed` | `{ message_id, content_chunks, citations, confidence_overall, token_usage_input, token_usage_output, estimated_cost_usd }` |
| `error` | `{ code, message }` |
| `done` | `{}` |

EventSource is GET-only, so clients POST + parse the stream over `fetch`'s
`ReadableStream` (web) — see `apps/mobile/lib/api-client.ts::streamMessage`. On
native (no streaming body) it reads the full response and replays events.

## Honest framing

- **Three-tier voice** (CO-002): A facts / B legal-with-citation / C strategic-with-reasoning.
  The UI renders the tiers distinctly (A plain, B with inline citation chips, C italic
  "Recommendation"). Never predicts outcomes.
- **Citation discipline**: every legal/policy claim cites a retrieved source. A CPT
  citation shows the code only, with a generic placeholder — never the AMA descriptor (DL-54).
- **Decline categories** (crisis etc.) use clean declines, no routing.
- **DL-47**: message bodies stay in-app (no PHI through email/push). The conversation
  **title** is `detect_phi`-guarded before it becomes list-visible — any PHI signal
  collapses it to "Untitled conversation".

## Cost + rate limits (per user, DB-derived)

- **Rate limit**: 30 user messages / rolling hour → `429 {code: RATE_LIMIT_REACHED, resets_at}`.
- **Cost cap**: $10 estimated / rolling 24h → `429 {code: COST_CAP_REACHED, resets_at}`.

Both are computed from `messages` (sum/count joined to the user's conversations) so they
survive replica restarts. Every turn writes an audit event (`model_call`) with mode +
token usage + cost + tool calls.

## Knowledge-gap logging

When a chat turn can't ground an answer, the agent calls `log_knowledge_gap`
(`agent_name="chat:<mode>"`) — the same CO-9 Module 6 log the admin /gaps dashboard
reads. The gap carries the user + case id for traceability.

## Schema

Migration `0016_conversations_and_messages` (chains onto 0015):
- `conversations` — one per thread; denormalised `message_count` + `last_message_at`.
- `messages` — one per turn; JSONB `content_chunks` / `tool_calls` / `citations`;
  `status` ∈ streaming/complete/stopped/failed.
