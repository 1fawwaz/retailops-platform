# ADR 007: A provider-layer fallback chain, entirely below `agents/`, with the served provider pinned for the rest of a conversation

## Status

Accepted — Stage 6 Task 6.4.

## Context

`docs/BUILD-SPEC.md`'s Task 6.4 asks for a second LLM provider (Groq) behind
the same `LLMProvider` interface Gemini already implements
(`llm/providers/gemini.py`, Task 6.3), with failover invisible to every
caller above the provider layer — `agents/base.py` keeps calling
`generate()`/`generate_structured()`/`stream()` exactly as it did before this
task, unaware two providers or a fallback chain exist at all. Two constraints
came from Task 6.3, not invented here: failover must trigger only on
`ProviderUnavailableError` (a 429/quota, or a timeout/connection/5xx that
exhausted its own in-provider retries) — never on a citation-validator
rejection or a model failing to follow structured-output instructions,
neither of which a different provider would fix, and representing one as
"provider unavailable" would be dishonest. A 429 specifically fails over
immediately, with no in-provider retry first — a deliberate *reversal* of
Task 6.3's own retry-on-429 policy, since a quota error is deterministic
within its window and retrying the same provider wastes the caller's whole
timeout budget on a call that cannot succeed.

Two real bugs surfaced during this task's own live verification, both fixed
before the TRUST GATE could pass, and both worth recording here since
neither was anticipated by the spec text:

1. **Tool-choice reliability, not a config mistake.** Groq's
   `openai/gpt-oss-20b` and `-safeguard-20b` intermittently attempted a
   phantom tool call — rejected by Groq's own backend as a 400 — when given
   this codebase's *real* `prompts/planner/v1.md` text specifically (never
   reproduced against a paraphrased test prompt), even with `tool_choice`
   left at Groq's own default for a tool-less call. `openai/gpt-oss-120b`
   never reproduced it across repeated live attempts. Fixed two ways:
   `llm/providers/groq.py` now sets `tool_choice` explicitly
   (`"none"`/`"auto"`) on every call rather than trusting the SDK default,
   and `config/models.yaml`'s `fallback.model` is pinned to the 120b variant
   — both documented in that module's and that config file's own comments.
2. **A cross-provider conversation-state bug, not a Gemini bug.** A
   multi-round tool-calling loop where round 1 failed over Gemini→Groq
   (quota) and round 2 independently re-resolved back to Gemini (quota
   window recovered a few seconds later) produced a conversation history
   Gemini's own API rejects with `400 INVALID_ARGUMENT: Function call is
   missing a thought_signature`. Confirmed directly that Gemini's own
   thought-signature capture/replay (`llm/providers/gemini.py`) was already
   correct in every case where Gemini served both rounds — the bug was
   allowing a conversation's provider to change mid-flight at all, addressed
   below.

## Decision

**`llm/providers/fallback.py::FallbackProvider` wraps an ordered
`list[tuple[LLMProvider, str]]` — (provider, that provider's own model) —
and is the only place failover logic lives.** It tries each pair in order,
catching only `ProviderUnavailableError`; any other exception (a `ValueError`
from `generate_structured()` failing to parse, for instance) propagates
immediately, untouched. If every entry in the chain fails, it raises
`LLMUnavailableError` — the same terminal signal Task 3.6/6.3's existing
degradation paths (`orchestration/graph.py`, `api/errors.py`) already catch,
so no downstream code needed to change for this task at all.
`stream()` applies the same catch only to establishing the connection and
its first chunk; once at least one chunk has been yielded, a failure
propagates raw rather than silently restarting a second provider's answer
over a client that may have already received part of the first one.

**`llm/providers/registry.py` resolves which chain to hand `FallbackProvider`,
and does so two different ways depending on whether this is the first call of
a conversation or a later round of an existing one — the load-bearing part of
this ADR.** A fresh conversation (no `AIMessage` yet in `messages`) resolves
the normal primary/fallback pair from `config/models.yaml`, ordered by
`Settings.llm_primary_provider`. A later round (`agents/base.py::Agent.invoke()`'s
own loop, which re-calls `generate()` once per round with the growing message
history) is instead **pinned**: `_pinned_provider()` reads which provider
served the *last* `AIMessage` already in the history
(`response_metadata["provider"]`, set by both `gemini.py` and `groq.py` on
every response) and `_resolve_chain()` builds a **single-entry** chain
containing only that provider. If the pinned provider fails this round, it is
not retried against the other one — the same "never silently restart"
principle `stream()`'s mid-stream handling already uses, applied here to a
whole round rather than a partial stream.

This is what fixes bug 2 above: without the pin, round 2 of the scenario
described in Context is free to re-resolve fresh and land back on Gemini,
producing a conversation Gemini's own API correctly rejects — not because
`thought_signature` handling was wrong on Gemini's side, but because no
version of correct per-provider metadata handling can make a
provider-switched-mid-conversation history valid. Pinning removes the
possibility structurally: once a conversation is served by Groq, it stays
Groq's for the rest of that conversation, so Gemini never sees a history
containing turns it didn't produce itself.

**Boot-time validation (`llm/providers/startup.py::validate_configured_models()`)
checks every configured ID — all three roles plus `fallback` — against its
own provider's live model-list endpoint**, failing fast with the specific
role path, model ID, and provider name if any is missing. Wired into
`api/main.py` as a FastAPI `lifespan` step (the modern replacement for the
deprecated `@app.on_event("startup")`), confirmed live that a bare
`TestClient(app)` — this whole test suite's pattern, everywhere — never
triggers `lifespan` at all, so this makes zero real network calls during an
ordinary `pytest` run without any test-specific skip logic needed.

**`config/models.yaml` gained one `fallback: {provider, model}` block; no
role's own `provider`/`model` changed.** `Settings.llm_primary_provider`
(env var `LLM_PRIMARY_PROVIDER`, default `"gemini"`, matching CLAUDE.md's own
stack pin) controls which end of the fresh chain goes first, independent of
which provider each role is configured for — flipping it to `"groq"` for a
role whose own provider is `"gemini"` tries the fallback pair first, the
role's own pair second. This is a pure ordering switch; it does not change
which two providers exist in the chain, and needed no code change to
support — the mechanism the spec asked for ("primary/fallback order
switchable via env var") falls directly out of `_resolve_fresh_chain()`'s
existing logic.

## Consequences

- **Every LLM call's trace now records the provider and model that actually
  served it**, not just the one configured — `AgentStep.provider`
  (migration `690cc23d7f69`), `/agent/query`'s `serving` field, and the SSE
  `agent_completed` event all carry it, satisfying invariant 2 (full trace)
  for a system where the configured and serving model can now genuinely
  differ.
- **A conversation can never straddle two providers**, by construction, not
  by convention — a future third provider added to the chain inherits this
  for free, since the pin operates on `response_metadata["provider"]`
  generically, not on a hardcoded Gemini/Groq pair.
- **A quota outage on the primary provider is invisible to the end user** as
  long as the fallback succeeds — same latency-budget behavior as a normal
  call, no raw 500, no partial answer, per the spec's explicit ask.
- **The fallback model is now a second point of failure to keep verified.**
  `startup.py` only confirms a configured ID *exists* on its provider's live
  list, not that it supports every call shape this codebase needs (tools,
  `response_format=json_schema`, streaming) — bug 1 above was exactly this
  gap. Both `config/models.yaml`'s and `groq.py`'s own comments now carry
  this warning directly at the point a future change would need to re-check
  it.
- **TRUST GATE, verified live, all three parts:** (1) the Stage 5 eval suite
  passes unchanged with zero real network calls (`python evals/run.py`,
  100%). (2) A full live `/agent/query` request with Groq forced as primary
  (`LLM_PRIMARY_PROVIDER=groq`) — real tool calls, citation validator active,
  every `agent_steps` row `provider="groq"`. (3) A full live failover proof
  with Gemini in a known-failing (quota-exhausted) state — the request
  succeeds via Groq, the failover is logged with the execution ID, every
  `agent_steps` row records the real serving provider, confirmed both
  through the full multi-agent graph and in isolation
  (`Agent.invoke_streaming()`'s pre-first-token path specifically).

## What would have to be true to change this

- **A third provider** would be added the same way Groq was: its own
  `llm/providers/<name>.py` implementing `LLMProvider`, registered in
  `registry.py::_PROVIDERS_BY_NAME`, and added to whichever chain(s)
  `_resolve_fresh_chain()`/`config/models.yaml` should place it in — the pin
  mechanism needs no change, since it already keys off whatever provider name
  a served `AIMessage` actually carries.
- **A provider whose SDK doesn't expose a synchronous model-list call** would
  need `startup.py`'s validation approach reconsidered (it assumes
  `list_model_ids()` is cheap and safe to call at boot for every configured
  provider) — not a blocker encountered with either Gemini or Groq.
- **If Groq ever added a working, load-bearing `response_format=json_schema`
  model smaller/cheaper than `openai/gpt-oss-120b`**, re-verifying finding 1
  live against the real planner prompt (not a paraphrase) before switching
  `config/models.yaml`'s `fallback.model` would still be required — the
  finding was specific to model size and this exact prompt, not a permanent
  property of the `gpt-oss` family.
