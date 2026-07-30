# RetailOps AI — frontend

The only UI in this project (CLAUDE.md section 1) — a Next.js (App Router,
TypeScript, Tailwind) app that owns authentication and the chat interface
over `retailops-ai`'s own HTTP API. Lives inside `retailops-ai/` rather than
as a top-level sibling service, since it's a client of this one service, not
a third service of its own.

## Authentication

There is no user system here, or in `retailops-ai` — both trust
`stockpilot-core`'s own JWTs (CLAUDE.md: "no second user system"). The login
form posts to `app/api/auth/login/route.ts`, a Route Handler that proxies to
`stockpilot-core`'s `POST /auth/login`, then stores the returned JWT in an
**httpOnly** cookie — never readable by client-side JS. Every subsequent
call to `retailops-ai` goes through a Route Handler (e.g.
`app/api/agent/query/route.ts`) that reads the cookie server-side and
attaches `Authorization: Bearer <token>`, the scheme
`retailops-ai/api/deps.py::get_current_subject` expects. `proxy.ts` (Next.js
16's renamed `middleware.ts`) redirects unauthenticated requests to
`/login` — a cheap, cookie-presence UX gate only; the real authorization
boundary is `retailops-ai` verifying the JWT signature on every request.

## Chat

`app/chat/page.tsx` calls the SSE path of `POST /agent/query`
(`Accept: text/event-stream`) via `app/api/agent/query/route.ts`, which
forwards whichever `Accept` header the client sent and, for a streaming
response, pipes the upstream `ReadableStream` straight through rather than
buffering it. `lib/sse.ts` parses the `event: <type>\ndata: <json>\n\n`
wire format by hand (the browser's native `EventSource` only supports GET
with no custom headers/body, and this call needs a POST body plus a
server-attached `Authorization` header) into the typed events documented on
`orchestration/executor.py::run_execution_streaming()`: `token` (appended
live to the in-progress answer), `agent_completed` (rendered as progress
pills), `replan_judgement` (a note plus dropping retried agents' pills, so a
second retrieval round doesn't show a stale checkmark for evidence being
redone), `citation_check` (a failed check discards the streamed-so-far text,
per that function's own documented "treat this as a fresh draft" contract),
`error`, and `done` (finalizes the message and advances `conversation_id`).

`conversation_id` is kept in React state across turns so a follow-up
question continues the same conversation server-side
(`orchestration/memory.py`); it does not persist across a page reload —
`retailops-ai`'s own DB-backed conversation history is the source of truth,
not client storage.

## Running locally

Requires `stockpilot-core` and `retailops-ai` both running (see the repo
root `README.md` / `Makefile`), then:

```bash
cp .env.example .env.local   # defaults already match `make run-core`/`run-agents`
npm install
npm run dev
```

Open http://localhost:3000 — you'll land on `/login`.

## Environment variables

| Variable | Meaning |
|---|---|
| `STOCKPILOT_BASE_URL` | Where `app/api/auth/login` proxies the login form to. |
| `RETAILOPS_BASE_URL` | Where `app/api/agent/query` proxies chat requests to. |

Both are read only in Route Handlers (server-side), never exposed to the
browser — no `NEXT_PUBLIC_` prefix, by design.
