# @tyndale/mobile

Tyndale's Expo React Native universal app (web + iOS + Android) — **the product**.
Served on web at app.tyndaleapp.net. Routing is expo-router (file-based, a Stack — no
tab bar). NativeWind/Tailwind for styling against the shared design tokens.

## Routes (`app/(app)/`)
| Route | Screen |
|---|---|
| `/` | Dashboard |
| `/upload` | Document upload → opens a case |
| `/audit/[case_file_id]` | Audit results (Overview \| **Chat** tab strip) |
| `/audit/[case_file_id]/encounter` | Encounter verification |
| `/audit/[case_file_id]/chat` | **Per-case chat (CO-10)** |
| `/chat` | **Freeform "Ask Tyndale" list (CO-10)** |
| `/chat/[conversationId]` | **Freeform conversation (CO-10)** |
| `/settings`, `/privacy`, `/terms` | — |

The dashboard "Chat with AI Assistant" CTA opens `/chat`.

## Chat (Phase CO-10)
SSE streaming chat — see [`docs/chat.md`](../../docs/chat.md) for the event schema + modes.

- **Components** (`components/chat/`): `ChatThread` (composite used by both surfaces),
  `ChatMessage` (tiered A/B/C render + citation chips + confidence + error/stopped states),
  `ChatComposer` (input → stop while streaming), `ChatStream` (the `useChatStream` SSE
  state machine), `CitationChip`, `CitationDetailModal`, `ToolCallIndicator`, `CreateCaseCta`.
- **Streaming client**: `lib/api-client.ts::streamMessage` POSTs + parses SSE over the fetch
  `ReadableStream` (EventSource is GET-only); native falls back to a full-read replay.
- **Citation modal**: tapping a `CitationChip` opens `CitationDetailModal` — title, excerpt,
  effective date, payer, external-link button. A CPT citation shows the code with a generic
  placeholder, never the AMA descriptor (DL-54).

## Commands
```bash
npm run dev -w @tyndale/mobile         # expo start --web
npm run typecheck -w @tyndale/mobile   # tsc --noEmit — the CI gate
npm run test -w @tyndale/mobile        # jest (jest-expo/ios preset)
```

> Jest note: uses the single-platform `jest-expo/ios` preset (the default multi-project
> preset loads `expo-modules-core`'s untransformed `.web.ts` source). `babel.config.js`
> drops NativeWind under `NODE_ENV=test` so components render without the css-interop
> runtime, and `jest.config.js` pins a single React instance. There is no `lint` script
> (matching the repo) — typecheck is the gate.
