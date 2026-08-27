# Architecture

**Status:** Phase 1 + 2 + 3 + 4. Documents what is actually built plus the boundaries left for later phases to plug into. Update this document as each phase lands - it should never describe unimplemented behavior as if it exists.

## System overview

```
Frontend (React/Vite)
    |  HTTP (fetch), CORS-restricted to VITE_API_BASE_URL
    v
FastAPI API  (backend/app/main.py, backend/app/api/)
    |
    v
Agent layer  (backend/app/agents/)         <- Phase 3 (corrected) + Phase 4
    |  GrowthAssistantAgent:
    |    1. builds a retrieval query from conversation context
    |    2. KnowledgeRetriever.search() -> RetrievedChunk[] (Phase 4)
    |    3. folds retrieved excerpts into this turn's system prompt
    |    4. -> pi_agent.agent.Agent (pi-coding-agent, the required agent framework)
    |
    +-- Skills + Tools                     <- Phase 5 (not yet built)
    |     +-- Ship30
    |     +-- Artifact generation
    |
    v
Knowledge base  (backend/app/knowledge/, app/services/knowledge_retriever.py)   <- Phase 4
    |  Offline ingestion (app.knowledge.ingest) parses + chunks Lenny's Data
    |  into PostgreSQL; online KnowledgeRetriever (BM25, pure Python) reads it.
    |
    v
PostgreSQL (persistence: sessions/messages + knowledge_documents/knowledge_chunks/message_sources)
    |
    v
Model Provider Abstraction (pi_agent.llm, from pi-coding-agent)
    +-- OpenAIProvider(base_url=Ollama's /v1)  -> Ollama container (mandatory demo path)
    +-- AnthropicProvider -> Anthropic Claude API (cloud path)
```

Phase 1 built everything above the "Agent layer" line, plus the raw infrastructure (PostgreSQL, Ollama) below it. Phase 2 filled in the PostgreSQL box with a real schema. Phase 3 built the agent layer and a model provider abstraction and wired them together. A subsequent **Phase 3 compliance correction** (see "Agent framework choice" below) replaced Phase 3's hand-rolled `ModelProvider`/`GrowthAssistantAgent` internals with the assignment's actually-required agent framework, **pi-coding-agent**. **Phase 4** (this update) adds a real knowledge base ingested from Lenny's Podcast/Newsletter source material, a retrieval service the agent queries every turn, and structured per-message citations - see "Knowledge base (Phase 4)" below for the full pipeline.

## Agent framework choice

The assignment requires agent integration via the **Anthropic Claude Agent SDK** or **Pi Coding Agent** - a custom class named "Agent" wrapping a provider does not satisfy this on its own, and Phase 3's original `GrowthAssistantAgent` (a hand-rolled wrapper around a hand-rolled `ModelProvider` ABC) was exactly that: architecturally clean, but not an instance of either required framework. This section documents the correction.

**Claude Agent SDK was evaluated and rejected.** `claude-agent-sdk` (`pip install claude-agent-sdk`, v0.2.145 at evaluation time) is Claude Code packaged as a library: it drives the full Claude Code CLI as a subprocess, and `ClaudeAgentOptions` has no `base_url` or `api_key` override - there is no supported way to point it at anything but Anthropic's own API. Even if there were, Ollama doesn't speak Anthropic's Messages API wire format, so the mandatory local-model demo path would be unreachable. Installing it also pulled in an `mcp` dependency that upgraded `starlette` past the range this project's pinned FastAPI version supports, breaking the app outright. Adopting it would have meant dropping the mandatory Ollama requirement - not acceptable per the assignment - so it was ruled out.

**Pi Coding Agent (`pi-coding-agent` on PyPI, v0.6.0) is what's actually integrated.** It is a real, independently-installable multi-provider coding agent with its own `LLMProvider` protocol (`pi_agent.llm`) and its own agent orchestration loop (`pi_agent.agent.Agent`) - not a class this project invented and named "Agent" to claim compliance. Concretely:

- `app/services/model_providers/factory.py` constructs a real `pi_agent.llm.LLMProvider` instance - `pi_agent.llm.OpenAIProvider` for Ollama, `pi_agent.llm.AnthropicProvider` for cloud (see "Model provider abstraction" below).
- `app/agents/growth_assistant.py`'s `GrowthAssistantAgent` constructs and drives a real `pi_agent.agent.Agent` on every turn: `PiAgent(provider=..., registry=ToolRegistry([]), sandbox=Sandbox(...), config=AgentConfig(...), messages=...)`, then calls its **actual, synchronous `.run(user_input)` method** (bridged into the async request path via `asyncio.to_thread`, with `asyncio.wait_for` enforcing `MODEL_TIMEOUT_SECONDS` around it). This is pi-coding-agent's real ReAct tool-use loop, its real transient-error retry with exponential backoff (`AgentConfig.max_retries`), and its real history-trimming (`AgentConfig.max_history_messages`) - not a reimplementation.
- The tool registry is intentionally **empty** (`ToolRegistry([])`): this is a conversational product/growth advisor, not a coding agent, so it is given zero coding tools. With nothing for the model to call, pi-agent's loop always resolves in exactly one iteration - `AgentConfig(max_iterations=1)` makes that explicit rather than relying on an empty registry alone. Phase 4/5 tool integrations (retrieval, artifacts) add real tools to this same registry without changing `GrowthAssistantAgent`'s shape.
- `Sandbox` is pi-agent's filesystem-confinement guard, required by `Agent`'s constructor but never actually resolved, since no registered tool ever touches a path.

**Ollama support goes through pi-coding-agent's own documented mechanism, not a workaround.** pi-coding-agent ships a first-class `ollama` provider entry (`pi_agent.llm.PROVIDERS["ollama"]`: `kind="openai"`, `base_url="http://localhost:11434/v1"`, `requires_key=False`) precisely because Ollama exposes an OpenAI-compatible `/v1` endpoint. `factory.get_model_provider` reuses that exact mechanism, pointed at this application's own `Settings.ollama_base_url` (so it resolves correctly both on the host and inside Docker Compose, where the hostname is `ollama` rather than `localhost`) rather than pi-agent's own hardcoded local default.

The provider abstraction above the framework boundary is preserved: `factory.get_model_provider(settings)` remains the single place that branches on `Settings.llm_provider`, and everything above it (the agent, the API, the frontend's provider indicator) still depends only on an `LLMProvider`-shaped object, never on Ollama's or Anthropic's wire format directly - the abstraction now comes from the required framework itself instead of a hand-rolled ABC, which is a strictly better fit for "have a real agent framework own agent-level behavior."

## Why a modular monolith

The assignment architecture has several conceptual layers (orchestration, skills, retrieval, persistence, model provider), but standing these up as separate services on day one would add deployment and networking complexity with no corresponding benefit at this stage - there's a single consumer (the frontend) and a single team (one engineer building all seven phases). A modular monolith - one FastAPI process with clearly separated packages - gets the same separation of concerns without the operational overhead, and can be split into services later if a real scaling reason appears.

## Backend structure

```
backend/
├── alembic/               Migration environment + versioned migrations.
│   ├── env.py              Points at app.config.Settings and app.db.models.Base
│   │                       so migrations never duplicate connection config.
│   └── versions/           37c02c433bb2_initial_schema.py - the Phase 2 schema.
├── alembic.ini
└── app/
    ├── main.py           Application factory: builds the FastAPI app, wires
    │                     middleware, exception handlers, and routers. No
    │                     module-level side effects beyond constructing `app`.
    ├── config.py         Settings (pydantic-settings). The only place that
    │                     reads environment variables.
    ├── logging_config.py Structlog setup shared by the whole process.
    ├── api/
    │   ├── health.py       GET /health, GET /health/ready (now also checks
    │   │                   the active model provider).
    │   ├── sessions.py     Session + message endpoints, including
    │   │                   assistant-generation orchestration (Phase 3).
    │   ├── system.py       GET /api/provider - real active provider/model.
    │   └── schemas.py      Pydantic request/response models for the API.
    ├── core/
    │   ├── errors.py     AppError hierarchy + centralized exception handlers.
    │   └── responses.py  Shared Pydantic response models.
    ├── agents/
    │   ├── prompts.py       SYSTEM_PROMPT - the assistant's base instruction.
    │   ├── growth_assistant.py  GrowthAssistantAgent: constructs and drives a
    │   │                        real pi_agent.agent.Agent (the required agent
    │   │                        framework) per turn, with a zero-tool registry
    │   │                        + a wall-clock timeout wrapper.
    │   └── errors.py         AgentError taxonomy (see "Assistant generation
    │                         failure semantics" below).
    ├── db/
    │   ├── session.py    Async SQLAlchemy engine/sessionmaker, the
    │   │                 `/health/ready` check, and the `get_db` FastAPI
    │   │                 dependency.
    │   ├── models.py     ORM models: User, ChatSession, Message (now with
    │   │                 an `extra_metadata` JSON column), Artifact.
    │   └── types.py      `GUID` - a portable UUID column type (native
    │                     `UUID` on PostgreSQL, `CHAR(36)` elsewhere) so the
    │                     same models run against SQLite in tests.
    └── services/
        ├── conversations.py       Data-access layer: create/list/get
        │                          sessions, list/create messages. Owns
        │                          session isolation and title derivation.
        └── model_providers/       Selects a pi-coding-agent LLMProvider.
            ├── __init__.py          Documents that the provider types
            │                        themselves come from pi_agent.llm, not
            │                        from a class defined in this package.
            └── factory.py           `get_model_provider(settings)`: the only
                                      place that branches on
                                      `Settings.llm_provider`, returning a
                                      real `pi_agent.llm.OpenAIProvider`
                                      (Ollama) or `AnthropicProvider` (cloud).
```

**Why this split:** `api/` never talks to a model provider directly - it depends on the agent layer (`app/agents/`), which itself depends only on `pi_agent.llm.LLMProvider`, never on Ollama or Anthropic specifics. This keeps HTTP concerns (status codes, request/response shapes) separate from "how do I get an answer out of a model," so adding a third provider or extending the agent (tool-using, multi-step) never touches `api/sessions.py`'s HTTP contract. `app/domain/` from Phase 1's plan was folded into `app/agents/` once the actual shape of "agent orchestration" became concrete - a separate empty `domain/` package alongside a populated `agents/` package would have been redundant.

### Configuration

`app/config.py` defines a single `Settings` (pydantic-settings) class. Every other module imports `get_settings()` rather than calling `os.getenv` - this is enforced by convention now and should stay that way as new settings are added in later phases. `Settings` validates types and enum-like fields (`app_env`, `log_level`) at startup, so a typo'd environment variable fails fast with a clear error instead of silently misbehaving at runtime.

### Error handling

`app/core/errors.py` defines `AppError` (and subclasses like `NotFoundError`) that carry a `code`, HTTP `status_code`, and a safe user-facing `message`. `register_exception_handlers` attaches handlers for `AppError`, FastAPI's `RequestValidationError`, Starlette's `HTTPException`, and a catch-all `Exception` handler - the last of which logs the real exception server-side but returns a generic `internal_error` message to the client, so stack traces never leak to the frontend. Later phases (model errors, retrieval errors, artifact errors) should subclass `AppError` rather than inventing a new response shape.

### Health vs. readiness

`/health` never touches a dependency - it exists purely to answer "is the process alive," and must stay that way so it can be used as a fast liveness probe. `/health/ready` is where dependency checks belong: PostgreSQL (a real `SELECT 1`) and, as of Phase 3, the active model provider. The provider check is deliberately asymmetric - for Ollama it's a live, short-timeout ping to `/api/tags` confirming both that Ollama is reachable *and* that the configured model is actually pulled; for the cloud provider it only confirms `CLOUD_API_KEY` is set, since spending real money on a completion call every time something polls `/health/ready` would be the wrong tradeoff. Either way, HTTP 503 with `status: "degraded"` if any dependency fails - a retrieval-index check in Phase 4 means appending to the same `dependencies` list.

### Database and schema

`app/db/session.py` creates one process-wide async SQLAlchemy engine on startup (via the FastAPI `lifespan` context in `main.py`) and disposes it on shutdown. `get_db` is a FastAPI dependency that yields a request-scoped `AsyncSession` from that engine.

The schema (`app/db/models.py`, migrated by `alembic/versions/37c02c433bb2_initial_schema.py`):

```
users (1) ----< sessions (many) ----< messages (many)
                    |
                    +----< artifacts (many)   -- Phase 5 foundation only
```

| Table | Columns | Notes |
|---|---|---|
| `users` | `id` (UUID pk), `external_key` (unique), `display_name`, `created_at` | One row today - the seeded demo user (see below). |
| `sessions` | `id`, `user_id` (fk, cascade delete), `title`, `created_at`, `updated_at` | Indexed on `(user_id, updated_at)` for the sidebar's "most recent first" query. `updated_at` is touched on every new message so ordering reflects activity, not just edits. |
| `messages` | `id`, `session_id` (fk, cascade delete), `role` (`user`/`assistant`/`system`, CHECK-constrained), `content`, `created_at` | Indexed on `(session_id, created_at)` for ordered retrieval. |
| `artifacts` | `id`, `session_id` (fk, cascade delete), `title`, `kind`, `content`, `created_at`, `updated_at` | No API writes to this table yet - it exists so Phase 5 doesn't need a migration that reshapes `sessions`. |

Every UUID primary/foreign key uses `app.db.types.GUID`, a `TypeDecorator` that renders as a native `UUID` column on PostgreSQL but as `CHAR(36)` on other dialects (SQLite). This is what lets the exact same ORM models run against PostgreSQL in production and against an in-memory SQLite database in tests, without a parallel "test models" definition to keep in sync.

### Migrations

Alembic (`backend/alembic/`) is the migration tool, not `Base.metadata.create_all()` - the latter is used only inside the test fixture (`backend/tests/conftest.py`) for a throwaway SQLite database, never against the real PostgreSQL instance. `alembic/env.py` imports `app.config.get_settings()` for the connection URL and `app.db.models.Base` for the target metadata, so the migration environment can never drift out of sync with the app's own configuration or models. The backend's Docker `CMD` runs `alembic upgrade head` before starting uvicorn, so `docker compose up` always leaves the database at the current schema version with no manual step.

The initial migration also seeds the single demo user (see below) as a data migration, rather than the application creating it lazily at request time - this keeps that user's identity reproducible and independent of request ordering.

### Single-user strategy

This is a single-user take-home application with no login/signup flow. Every session and message belongs to one deterministic local user, `DEMO_USER_ID` (a fixed, well-known UUID constant in `app/db/models.py`, seeded by the initial migration under `external_key = "local-demo-user"`). `app/api/sessions.py` hard-codes this constant rather than accepting a user id from the client - there is no session/cookie/token to forge, so this is not a security shortcut, just the appropriately minimal amount of "user" concept for a single-user product. Adding real authentication later means introducing a user-resolution dependency in `api/sessions.py` and passing its result to `services/conversations.py` instead of the constant - the data-access layer already takes `user_id` as an explicit parameter everywhere, so that swap doesn't touch its internals.

### Session isolation

`app/services/conversations.py` is the only code that queries `sessions`/`messages`, and every function takes an explicit `user_id`. `get_session()` scopes its query to `WHERE id = :session_id AND user_id = :user_id` - a session that exists but belongs to a different user produces the same `SessionNotFoundError` as a session that doesn't exist at all, so the API never reveals whether an id belongs to someone else. `list_messages()` and `create_message()` both call `get_session()` first, so message access is always gated by that same ownership check - isolation is enforced once, in one place, not re-implemented per endpoint. `backend/tests/test_sessions_api.py::test_session_isolation_between_two_sessions` exercises this directly.

### Model provider abstraction

`pi_agent.llm.LLMProvider` (from the `pi-coding-agent` package - the required agent framework) is the protocol everything above this boundary depends on: one method, `complete(system, messages, tools) -> AssistantResponse`. Neither the agent, the API, nor the frontend's provider indicator talks to Ollama's or Anthropic's wire format directly. Two concrete providers are used, both pi-coding-agent's own, not hand-rolled:

- **`pi_agent.llm.OpenAIProvider`**, pointed at Ollama's OpenAI-compatible `/v1` endpoint (`base_url=f"{OLLAMA_BASE_URL}/v1"`) - this is pi-coding-agent's own documented mechanism for reaching Ollama (see "Agent framework choice" above), not a workaround invented for this project. This is the **mandatory demo path** (`LLM_PROVIDER=ollama`, the default).
- **`pi_agent.llm.AnthropicProvider`**, wrapping the official `anthropic` Python SDK's Messages API. Selected via `LLM_PROVIDER=cloud`.

`app/services/model_providers/factory.py::get_model_provider(settings)` is the *only* place that branches on `settings.llm_provider` - adding a third provider means one new branch here, nothing else changes. `GrowthAssistantAgent` catches every `openai.*`/`anthropic.*` SDK exception either provider's `.complete()` call can raise and normalizes it into the same `app.agents.errors.AgentError` subclasses (see below), so the agent and API layers handle "the provider failed" identically regardless of which provider is active.

**Configuration surface** (`.env.example`): `LLM_PROVIDER`, `MODEL_TIMEOUT_SECONDS`, `MAX_CONTEXT_MESSAGES` govern both providers; `OLLAMA_BASE_URL`/`OLLAMA_MODEL` govern the local path; `CLOUD_PROVIDER`/`CLOUD_MODEL`/`CLOUD_API_KEY` govern the cloud path. Switching providers is restarting the backend process with a different `.env` - no code change, and the frontend's provider indicator and `/health/ready` both pick up the new configuration automatically because they read it live from `Settings`, never from anything cached client-side.

### Agent architecture

`app/agents/growth_assistant.py`'s `GrowthAssistantAgent` is constructed with an `LLMProvider` plus `max_context_messages` and `timeout_seconds` (both from `Settings`). Its `respond(history: list[Message])`:

1. Filters `history` down to `user`/`assistant` messages (system messages, if any exist in the future, are never sent back to the model as conversation turns) and splits it into "prior turns" and "the pending user turn" (the last message, always the just-persisted user message).
2. Builds a real `pi_agent.agent.Agent` (`PiAgent`), seeded with the prior turns translated into pi-agent's neutral transcript format, configured with `system_prompt=SYSTEM_PROMPT`, `max_iterations=1`, an **empty tool registry** (`ToolRegistry([])` - this is a conversational advisor, not a coding agent), and `max_history_messages=max_context_messages` so pi-agent's own trimming enforces the context bound (see "Session context" below).
3. Calls the real `PiAgent.run(pending_user_content)` - a **synchronous** method - via `asyncio.to_thread(...)`, wrapped in `asyncio.wait_for(..., timeout=timeout_seconds)` as a provider-independent safety net on top of pi-agent's own transient-error retry.
4. Catches `openai.*`/`anthropic.*` SDK exceptions the underlying provider raised and maps them to the appropriate `AgentError` subclass.
5. Returns an `AgentResult` (content, provider name, model name, latency, input/output token usage from `PiAgent.total_usage`) - the API layer decides what to persist and what to expose; the agent itself never touches the database.

`app/agents/prompts.py`'s `SYSTEM_PROMPT` is the assistant's base instruction. It explicitly tells the model it has **no access to Lenny's transcripts yet** and must never fabricate an episode, guest, or quote - this is the mechanism that keeps Phase 3 honest about not being grounded, and it must be updated (not silently left as-is) once Phase 4 actually wires up retrieval.

### Session context

The agent is never handed conversation history from the frontend - `app/api/sessions.py` fetches it itself via `conversations.list_messages(db, user_id=DEMO_USER_ID, session_id=session_id)` (the same session-isolation-enforcing function everything else uses) immediately before invoking the agent. There is no code path where a client can supply arbitrary "context" for a different session; the isolation guarantee from Phase 2 is untouched by Phase 3. Context length is bounded by a fixed count (`MAX_CONTEXT_MESSAGES`, default 20) rather than a token budget - simple, predictable, and sufficient until a real long-conversation problem shows up in practice.

### Assistant generation failure semantics

This is the contract every "what happens on failure" question in the assignment resolves to, and it's implemented once, in `app/api/sessions._generate_assistant_reply`:

1. The user's message is persisted **first**, unconditionally, via the same `conversations.create_message` Phase 2 already had. A model failure can never lose a user's input.
2. The agent is invoked. `AgentError` (and all its subclasses - `ProviderUnavailableError`, `ModelNotFoundError`, `MissingCredentialsError`, `ModelTimeoutError`, `EmptyResponseError`) is caught, never re-raised as an HTTP error - a generation failure is a *partial* success (the user's turn was saved), not a request failure.
3. On success, the assistant's reply is persisted via `conversations.create_message(..., role=MessageRole.assistant, metadata={...})` - reusing the exact same function and its title/`updated_at` bookkeeping, just with a different role.
4. The HTTP response (`MessageCreateResponse`) always includes `message` (the user's, now-persisted turn) and `session`; `assistant_message` is present only on success, `generation_error: {code, message}` only on failure - never both, never a fabricated placeholder in either field.

**Retry** (`POST /api/sessions/{id}/messages/retry`) regenerates for the session's *pending* user message - the one at the end of history that has no assistant reply after it yet (`conversations.get_message_pending_retry`). If the last message already has a reply, retry is rejected with `409 nothing_to_retry` rather than silently doing nothing or creating a duplicate turn. This is what makes retry safe to call repeatedly: it can never create a second user message for the same question.

### Streaming decision

Phase 3 uses a **single non-streaming response** per turn, not token-by-token streaming. Both Ollama (`stream: false`) and the Anthropic SDK support streaming, so this was a deliberate simplicity choice, not a technical limitation: introducing SSE/websocket plumbing, partial-message persistence semantics, and stream-cancellation-on-session-switch would have added meaningful architectural surface area for one phase, for a benefit (perceived latency) that a well-designed "thinking" state substantially covers already (see `docs/design.md`). The response time is still bounded by `MODEL_TIMEOUT_SECONDS`, so the user is never left waiting indefinitely. Streaming remains a clean addition later: pi-coding-agent's providers already expose a `.stream()` method (used by `AgentConfig.stream=True` when a caller supplies an event callback), so enabling it would mean passing `on_event` into `PiAgent` and adapting its deltas to an SSE/websocket response, without changing the agent's or API's external contract in a way that touches session isolation or persistence semantics.

### Timeouts and retry (provider-level)

The agent's `asyncio.wait_for` wrapper around `PiAgent.run()` (via `asyncio.to_thread`) enforces a hard wall-clock ceiling driven by `MODEL_TIMEOUT_SECONDS` (default **60s**) - a request can never hang past that, regardless of which provider misbehaves, since a synchronous SDK call has no other way to be preempted. Underneath that, pi-coding-agent's own `Agent._with_retry` retries transient errors (rate limits, 5xx, timeouts, dropped connections - identified by HTTP status or exception name, matching both the `openai` and `anthropic` SDKs' hierarchies) with exponential backoff and jitter, up to `AgentConfig.max_retries` (3) attempts, before the error ever reaches `GrowthAssistantAgent`'s exception mapping. On top of that, the user-facing retry endpoint described above remains the explicit, safe recovery path for whatever still fails after those retries, so "how many times did this actually run" is never ambiguous in the logs.

Two numbers here are tuned from real measurement, not guessed: `factory.get_model_provider` caps Ollama's `max_tokens` at 400, and the timeout default is 60s rather than something tighter. Both come directly from live-testing this phase's mandatory demo path: on modest CPU-only hardware, a small model (`llama3.2:1b`/`3b`) generates at roughly **16-17 tokens/second**, and the assistant's own system prompt encourages structured, multi-section answers - an uncapped response could run past 600-800 tokens, i.e. 35-50+ seconds, before a client even finishes reading it. Capping output length is the primary lever (it bounds worst-case latency predictably, the way the cloud path's own `max_tokens` cap already does); the 60s timeout is the backstop for whatever that cap doesn't cover (a cold model load, contended hardware). Both are configurable per deployment - faster hardware or a GPU can lower `MODEL_TIMEOUT_SECONDS`, and the token cap can move to a per-request setting if a future phase needs longer-form answers.

### Observability

Every generation attempt logs through the existing Phase 1 structlog setup: `assistant_generation_succeeded` (session id, provider, model, latency_ms) on success, `assistant_generation_failed` (session id, provider, error code) on failure - both in `app/api/sessions.py`. Message *content* is never logged, on either path - only identifiers and metadata, per the assignment's "avoid dumping complete conversation contents into production logs" requirement. The same provider/model/latency/status triple is also persisted on the assistant `Message` row itself (`extra_metadata` JSON column, never exposed by `MessageOut`/the API) for later inspection without needing to correlate against application logs - never anything resembling hidden reasoning or the raw system prompt.

On success, the logged/persisted `provider` value is the pi-coding-agent provider class's own self-identification (`LLMProvider.name`) - `"openai"` for the Ollama path (since pi-agent implements Ollama support as its `OpenAIProvider` pointed at Ollama's OpenAI-compatible endpoint) or `"anthropic"` for the cloud path - not `Settings.llm_provider`'s `"ollama"`/`"cloud"` labels. This is an intentional, honest reflection of which concrete client actually made the HTTP call, not a mislabeling; the UI's provider badge and `/health/ready` are unaffected, since both read `Settings.llm_provider` directly rather than this log field.

### Concurrency considerations

- **Session switch mid-generation**: the frontend tracks which session a send was issued for and only applies the response if that session is still active when it resolves (`activeSessionIdRef` in `conversations-context.tsx`) - a stale reply can never render under the wrong conversation. The backend has no equivalent problem: `_generate_assistant_reply` is scoped to one `session_id` per call and writes are session-isolated regardless of what the client does afterward.
- **Retry while a request is still in flight**: the composer and retry button are both disabled while `isGenerating` is true, so the same click can't be issued twice from the same browser tab. Two truly concurrent requests to the same session (e.g. two tabs) are not explicitly locked against each other in Phase 3 - both would succeed independently, appending two assistant replies - which is an acceptable, non-corrupting outcome for a single-user local app, not a case that warrants distributed locking at this stage.
- **Browser refresh mid-generation**: the backend keeps processing and persists the assistant reply regardless of whether the client is still connected (the request isn't cancelled on disconnect) - reloading the page and re-fetching messages shows the completed turn once it lands.

## Knowledge base (Phase 4)

### Source

The knowledge base is [Lenny's Data](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata), the official free "starter pack" repository published by Lenny Rachitsky/Lenny's Newsletter: **50 podcast transcripts and 10 newsletter posts**, in plain Markdown with a companion `index.json` carrying structured metadata (title, guest, publication date, post/YouTube URL, word count). This is real, permitted, official source material - not invented, not scraped, not a third-party mirror. Its `LICENSE.md` permits personal, non-commercial use and building/publishing projects with it, but **not redistributing the raw dataset files** - so the raw transcripts are never vendored into this repository; instead they're fetched by the evaluator/operator as a documented, reproducible setup step (`git clone` - see the root `README.md` "Knowledge base setup"), then ingested from wherever that checkout lives.

Each podcast file's own YAML frontmatter (`title`/`date`/`guest`/`channel`/`description`) omits any URL at all - only `index.json` carries `post_url`/`youtube_url` per entry, and 14 of the 50 podcast entries have neither. `app.knowledge.parsing` therefore treats `index.json` as the authoritative metadata source (never the per-file frontmatter) and leaves `source_url`/`guest`/`published_at` as `None` whenever the source repository itself doesn't provide them - nothing is ever guessed or fabricated to fill a gap.

### Ingestion (`app/knowledge/`)

`python -m app.knowledge.ingest --source <path-to-the-cloned-repo>` (see README) does, per file listed in `index.json`:

1. **Validate the path** (`app.knowledge.ingest._resolve_and_validate`): the file must resolve inside the given source directory (no `../` escape even if `index.json` itself were hostile), must end in `.md`, must exist, and must be under `MAX_SOURCE_FILE_BYTES` (5MB - real transcripts run 100-150KB).
2. **Parse** (`app.knowledge.parsing`): split YAML frontmatter from the body; for a podcast, a state-machine parser (not a naive blank-line split - see its docstring for the "two speaker markers back to back with no text between them" edge case this handles correctly) extracts `Turn(speaker, timestamp, text)` from lines like `**Elena Verna** (00:00:06):`; for a newsletter, the body splits into paragraphs.
3. **Hash** the raw file bytes (SHA-256) - this is the *only* signal ingestion uses to decide whether a file changed.
4. **Chunk** (`app.knowledge.chunking`) - see "Chunking strategy" below.
5. **Upsert**: look up an existing `KnowledgeDocument` by its natural key `(source_type, slug)` (`slug` = the source repo's own filename stem, e.g. `elena-verna-40`). If it exists with the same content hash, **skip entirely** (this is what makes re-running ingestion idempotent - verified by `tests/test_knowledge_ingest.py::test_repeat_ingestion_is_idempotent`). If new or changed, replace its chunks and update its metadata inside one transaction per document, so one bad file can never corrupt another's data or half-write a document.
6. A malformed file (missing frontmatter, zero speaker turns, wrong extension, missing from disk) is logged and skipped - the run continues and reports a non-zero exit code, it never aborts partway through the corpus.

**Refresh strategy**: re-running the exact same command against an updated checkout of the source repo (`git pull`, or a fresh clone of a newer snapshot) reprocesses only files whose content hash changed, preserving each unchanged document's row/id; changed documents keep their `id` and natural key but get entirely new chunks. There is no automatic remote polling - refresh is always an explicit, evaluator-run command, never something `docker compose up` triggers.

### Data model

```
knowledge_documents (1) ----< knowledge_chunks (many)
messages (1) ----< message_sources (many) >---- knowledge_chunks (0..1, nullable)
```

- **`knowledge_documents`**: `id`, `source_type` (`podcast`/`newsletter`), `slug` (natural-key half), `title`, `guest` (nullable), `published_at` (nullable date), `source_url` (nullable), `word_count`, `content_hash`, `ingested_at`, `updated_at`. Unique on `(source_type, slug)`.
- **`knowledge_chunks`**: `id`, `document_id` (FK, cascade delete), `chunk_index` (ordering within the document), `text`, `speakers` (comma-joined, podcasts only), `char_count`, `created_at`. Indexed on `(document_id, chunk_index)`.
- **`message_sources`**: one row per citation actually shown for one assistant message - `id`, `message_id` (FK, cascade delete), `document_id`/`chunk_id` (FK, `ON DELETE SET NULL`), `rank`, `relevance`, and a **denormalized copy** of `source_type`/`title`/`guest`/`published_at`/`source_url`/`excerpt`. The denormalization is deliberate: a citation shown to a user must keep displaying exactly what was retrieved at generation time even if the corpus is later re-ingested and that chunk changes or disappears - `SET NULL` (not cascade) on the FK preserves the historical citation's own copied fields regardless. See `app/db/knowledge_models.py` for the full docstrings.

Migration: `backend/alembic/versions/e75557089cdb_knowledge_base.py`.

### Chunking strategy (`app/knowledge/chunking.py`)

Neither transcript type is split every N characters blindly:

- **Podcasts**: turn-aware. A chunk accumulates whole speaker turns (never splitting one turn's text across two chunks) until it reaches a ~1200-character soft target (~200 words - large enough to carry a complete thought, small enough that the default top-k retrieval keeps the grounding context sent to the CPU-bound local model small and predictable). Consecutive chunks overlap by exactly one turn (the last turn of a chunk is repeated as the first turn of the next), so a fact sitting near a chunk boundary still appears whole in at least one chunk. Speaker names for every turn in a chunk are recorded in `KnowledgeChunk.speakers`, never lost.
- **Newsletters**: the same packing algorithm over whole paragraphs instead of turns (essay prose has no speakers to preserve).

Real numbers from the actual ingested corpus: 50 podcasts + 10 newsletters -> **60 documents, ~7,100 chunks** (podcasts average ~17,200 words each, so ~75-100 chunks per episode; newsletters average ~3,700 words, ~15-20 chunks each).

### Retrieval strategy (`app/services/knowledge_retriever.py`)

**Why BM25-in-Python, not pgvector/tsvector.** PostgreSQL already exists in this stack, so the two "use PostgreSQL capabilities" options considered were native full-text search (`tsvector`/`ts_rank`) and `pgvector` with embeddings. Both were rejected in favor of a pure-Python BM25 scorer over chunk rows loaded through the ORM, for two concrete reasons: (1) `to_tsvector`/`ts_rank_cd`/pgvector are Postgres-only - they cannot run against the in-memory SQLite database this project's entire test suite uses for hermetic, network-free tests (Phase 1-3's own established convention), so adopting either would have forced a second, Postgres-only test path; (2) embeddings would mean either a paid API (ruled out - "the evaluator must be able to run the submitted system without unexpectedly requiring a paid external embedding API") or downloading a new local embedding model, which the assignment also explicitly discourages doing automatically. At this corpus size (~7,100 chunks, ~5MB of text), scoring entirely in Python has no measurable latency cost and needs zero new infrastructure. **Tradeoff, stated plainly**: this is lexical, not semantic, search - a paraphrase that shares no vocabulary with the source material won't be found. At meaningfully larger scale, Postgres FTS or pgvector would be the right next step; that migration only touches `KnowledgeRetriever`, not its callers.

**Query flow**: `KnowledgeRetriever.search(query)` first prefilters candidate chunks with a cheap SQL `ILIKE` OR-clause (so a query never has to hydrate every chunk in the corpus - `app.services.knowledge_retriever._candidate_chunks`), then scores the candidates in Python with standard Okapi BM25 (k1=1.5, b=0.75).

**The precision mechanism that actually matters is a minimum-matched-terms gate, not the raw score threshold.** Empirically testing against the real ingested corpus surfaced a real BM25 failure mode: a single rare word coincidentally appearing once in one chunk (e.g. "lasagna", "Paris") gets a very high IDF weight and can outscore a chunk that genuinely matches most of a real product/growth query. Requiring at least `min(2, distinct_query_terms)` of the query's terms to actually appear in a candidate chunk before it can score at all closes this: an off-topic query like *"What is the best way to cook a lasagna?"* or *"Tell me about the weather in Paris"* now returns **zero** candidates (verified against the real corpus, not just the test fixture), while genuine multi-word product/growth questions are unaffected. An extended stopword list (generic filler like "best"/"way"/"tell"/pronouns) prevents those from satisfying the coverage requirement on their own - an earlier version of this fix had exactly that bug (a stray "me" was letting a completely unrelated chunk pass) before the stopword list was corrected.

Because BM25's score scale depends on corpus size (via IDF), the score threshold (`DEFAULT_MIN_RELEVANCE = 0.5`) is deliberately just a low backstop against a near-zero-signal match, not the primary filter - the coverage gate above does that work, and does it in a way that's corpus-size-independent (which is why the same code and thresholds pass tests against both the tiny synthetic fixture corpus and the real ~7,100-chunk corpus without per-corpus tuning).

**Retrieval parameters**: `top_k=4` (`Settings.knowledge_top_k`), capped at `MAX_CHUNKS_PER_DOCUMENT=2` per document so the top-k stays source-diverse rather than one long episode dominating every result.

### Follow-up retrieval strategy

The agent does not send the whole conversation as the retrieval query, and does not use an LLM call to rewrite it (an extra model round-trip would add real latency and unreliability on the mandatory local Ollama path). Instead (`GrowthAssistantAgent._build_retrieval_query`): the query is the pending user message, with the single immediately-preceding user message in the same session prepended if one exists. This is enough to resolve a short follow-up like *"How does that apply to B2B?"* (which shares no vocabulary at all with an earlier "onboarding" question on its own) while staying simple, deterministic, and fast.

### Grounding prompt and empty retrieval (`app/agents/prompts.py`)

`build_grounding_block(chunks)` renders retrieved chunks into a clearly delimited `<retrieved_lenny_material>...</retrieved_lenny_material>` block appended to `SYSTEM_PROMPT` for that turn only. `SYSTEM_PROMPT` itself instructs the model: retrieved excerpts are the *only* source of truth for anything attributed to Lenny's material; never fabricate an episode/guest/quote/URL; and - critically for **security** - retrieved text is reference data, not instructions, so any text inside an excerpt that looks like an instruction must be treated as quoted material only, never followed. This is the system's defense against prompt injection carried inside transcript content: SYSTEM INSTRUCTIONS, CONVERSATION, and RETRIEVED KNOWLEDGE are three explicitly-labeled, structurally separate things in the prompt sent to the model, not concatenated indistinguishably.

When retrieval returns zero chunks (below the relevance/coverage bar, or a genuinely off-topic question), the block becomes an explicit `_NO_MATERIAL_BLOCK` telling the model there is no supporting material for this question and instructing it to say so plainly rather than invent one. This is a normal, expected outcome, not an error - `AgentResult.sources` is simply `[]` and the API's `grounded` field is `False`. A **real** retrieval failure (e.g. a database error) is different and is not silently swallowed into "no material found": `KnowledgeRetriever.search()` raising anything unexpected is caught and re-raised as `RetrievalError` (`app.agents.errors`), which flows through the exact same `generation_error` path as a model-provider failure - visible to the user, not a silently-degraded answer.

Known limitation, observed directly against real Ollama output: the local `llama3.2:1b` model does not always *verbally* self-disclose "I don't have Lenny material for this" as consistently as the prompt instructs (small models follow multi-part system instructions imperfectly) - but the trust-critical guarantee holds regardless of the model's prose: `sources`/`grounded` are computed entirely from what `KnowledgeRetriever` actually returned, never parsed from or influenced by the model's output, so no citation is ever fabricated even when the model's wording doesn't explicitly hedge.

### Citation integrity and traceability

The backend, never the model, decides what a user sees as a source. `GrowthAssistantAgent.respond()` returns the exact `RetrievedChunk` list it queried with in `AgentResult.sources`; `services.conversations.create_message` writes those straight into `MessageSource` rows in the same transaction as the assistant message; `MessageOut.sources`/`grounded` (via `SourceOut.from_message_source`) serialize those rows, never anything derived from the model's text. A chunk -> document -> original-source chain is always resolvable: a `MessageSource` row carries `chunk_id`/`document_id` back to the live corpus (when still present) and a frozen copy of the display fields regardless. Every field on `SourceOut` (`guest`, `published_at`, `source_url`) is nullable and left `None` whenever the source repository didn't actually provide it for that episode - never invented to fill the UI.

### Observability

`assistant_generation_succeeded` (already logged in Phase 3) now also carries `retrieved_count`, `source_ids` (chunk ids, not content), and `relevance_scores` - enough to diagnose why a given answer was or wasn't grounded without ever logging transcript text itself. `GET /api/knowledge/status` (`app/api/knowledge.py`) is an internal diagnostics endpoint - document/chunk counts, per-source-type counts, last ingestion timestamp - for verifying ingestion actually ran, not a user-facing feature.

### Known limitations

- **Lexical, not semantic, retrieval** - a question phrased with entirely different vocabulary than the source material won't be found even if the topic is covered (e.g. "founder-market fit" vs. a transcript that only ever says "founder-product fit"). See "Retrieval strategy" above for the tradeoff this accepted and the stated upgrade path (Postgres FTS/pgvector).
- **Free starter-pack corpus only** - 50 podcasts + 10 newsletters, not Lenny's full archive (349+ newsletters / 289+ podcasts, which sits behind a paid subscription at lennysdata.com); ingestion works identically against the full archive if an evaluator has access to it, but that was not exercised here.
- **Small local model instruction-following** - see the grounding section above; the citation data is always trustworthy, the model's prose occasionally is looser about hedging than instructed.
- **No reranking model** - the coverage-gated BM25 score is used directly as the final ranking; a learned reranker was judged unnecessary complexity at this corpus size, per the assignment's "prefer simple, reliable architecture" guidance.

## Conversation API

All endpoints live under `/api` (`app/api/sessions.py`, `app/api/system.py`), return the shapes defined in `app/api/schemas.py` (never raw ORM objects or provider SDK objects), and use the Phase 1 error envelope for failures:

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/sessions` | Creates a session titled `"New conversation"` for the demo user. `201`. |
| `GET` | `/api/sessions` | Lists the demo user's sessions, most recently active first. `200`. |
| `GET` | `/api/sessions/{id}` | Returns one session. `404` (`session_not_found`) if missing or not owned. |
| `GET` | `/api/sessions/{id}/messages` | Lists messages in creation order. `404` under the same rule. |
| `POST` | `/api/sessions/{id}/messages` | Creates a **user** message (the request schema only accepts `role: "user"`), then attempts assistant generation. `201`. Returns `message`, `assistant_message` (nullable), `session`, `generation_error` (nullable) - see "Assistant generation failure semantics" above. |
| `POST` | `/api/sessions/{id}/messages/retry` | Regenerates a reply for the pending user message. `200`, or `409 nothing_to_retry` if there is none. Returns `assistant_message`, `session`, `generation_error` - never a `message` field, since retry never creates one. |
| `GET` | `/api/provider` | Returns `{provider, model}` reflecting the real active `Settings` - the source of truth for the frontend's provider indicator. |
| `GET` | `/api/knowledge/status` | Internal diagnostics (Phase 4): document/chunk counts, last ingestion timestamp. Not part of the chat product surface. |

`MessageOut` (Phase 4) additionally carries `sources: SourceOut[]` and a computed `grounded: bool` (`len(sources) > 0`) - populated for a grounded assistant message, `[]`/`false` for every other message.

Title derivation is deterministic, not AI-generated: the first user message in a session becomes its title (truncated to 60 characters with an ellipsis if longer); later messages never overwrite an already-derived title. See `services.conversations._derive_title_from_content`.

## Frontend structure

```
frontend/src/
├── main.tsx, App.tsx        Entry point and top-level providers.
├── index.css                 Design tokens (CSS custom properties) + Tailwind v4 theme mapping.
├── lib/
│   ├── utils.ts               `cn()` class-merging helper.
│   ├── config.ts              The only place that reads `import.meta.env`.
│   ├── api.ts                 Typed fetch client (`ApiError` + the `api.*` methods).
│   │                          The only place that calls `fetch`.
│   ├── types.ts                Shared types, including `GenerationError` and
│   │                          `ProviderStatus` (Phase 3).
│   └── session-grouping.ts     Pure functions: bucket sessions into Today/Yesterday/
│                              Earlier, format a session's sidebar timestamp.
├── components/
│   ├── ui/                    Design-system primitives (Button, Input, Textarea,
│   │                          Card, Badge, Tooltip, Dialog, Spinner, EmptyState,
│   │                          Skeleton, SourceCard, WaveformIcon).
│   └── layout/                App shell composition (AppShell, Sidebar, TopBar,
│                              ArtifactPanel, NavItem, SessionItem, ThemeToggle,
│                              ProviderIndicator).
└── features/
    └── chat/                  ConversationsProvider (state), ChatWorkspace,
                               WelcomeState, Composer, MessageList, MessageBubble
                               (Markdown-rendering), ThinkingIndicator,
                               GenerationErrorCard - the chat-specific
                               composition, kept separate from generic layout so
                               a future `features/artifacts/` can sit alongside
                               it without entangling the two.
```

**Why `components/ui` vs `components/layout` vs `features/`:** `ui/` has zero product knowledge - a `Button` doesn't know it's used in a chat app. `layout/` knows about the app's shell (sidebar, panels) but not about chat-specific concepts (it reads session/provider data from `features/chat`'s context, but doesn't own it - `ProviderIndicator` is a small exception living in `layout/` since it's a shell-chrome element, not a conversation element). `features/chat/` is the one place that knows about conversations, messages, and drafts. This means Phase 4/5's `features/artifacts/` can be added without reaching into `components/`.

### Frontend state model

`features/chat/conversations-context.tsx` is the single source of truth for conversation state - one React context (`ConversationsProvider`, mounted once in `AppShell`) rather than scattering `fetch` calls and `useState` across components. It owns:

- **Sessions**: fetched once on mount; `sessionsState` is `"loading" | "idle" | "error"` so the sidebar can render a skeleton, the real list, or an error-with-retry without any component juggling booleans itself.
- **Active session id**: persisted to `localStorage` (a per-browser convenience, not authentication) so a page refresh restores the same open conversation - falling back to the most recently active session if the stored id no longer exists.
- **Messages for the active session**: refetched whenever the active session changes; reset to `[]` immediately on switch so a slow request can never flash session A's messages while session B is loading.
- **Provider status**: fetched once on mount from `GET /api/provider` and rendered as-is by `ProviderIndicator` - never hard-coded, never a UI toggle that changes a label without the backend actually switching.
- **Sending a message**: `sendMessage()` creates a session first if none is active yet (so typing directly into the empty state and hitting send "just works"). The user's own message is rendered **optimistically** the instant send is pressed (a local, temporary-id copy) - CPU-only local inference can take tens of seconds, and without this the transcript looked empty/unresponsive for the entire round trip, which read as broken during manual testing. Once the request resolves, the optimistic copy is replaced by the server's real message and the real assistant message is appended (or, on a generation failure, only a `generationError` is set - never a fabricated assistant reply); if the request itself fails, the optimistic message is removed and the composer restores the draft. A `pendingSessionId` field drives `isGenerating` (true only while the *active* session's request is outstanding) and an `activeSessionIdRef` guards every response handler against applying a stale reply after the user has switched sessions. A `skipNextMessagesFetch` ref avoids a subtle race where a freshly created session's (empty) message-list fetch could resolve *after* the first message was appended and wipe it back to `[]`.
- **Retry**: `retryGeneration()` calls `POST .../messages/retry` and appends only the resulting assistant message (or a new `generationError`) - it never touches the existing user message, matching the backend's retry contract.

No state-management library was added for this - `useState`/`useEffect`/`useContext` are sufficient for one provider with a modest, well-understood set of fields, and pulling in Redux/Zustand/React Query for this would be exactly the kind of unnecessary dependency the project intentionally avoids.

`MessageBubble` renders assistant content through `react-markdown` with a custom `components` map (headings, lists, bold/italic, inline/block code, links) and **no** `rehype-raw` plugin - raw HTML found in a model's response (e.g. an injected `<img onerror=...>`) is displayed as inert text, never executed. This is assistant-text rendering only, deliberately unrelated to the sandboxed artifact renderer Phase 5 will need for untrusted HTML documents - conflating the two would be the wrong security model for either one.

## Local development architecture

`docker-compose.yml` runs four services on one bridge network (`lenny_network`): `postgres`, `ollama`, `backend`, `frontend`. The backend's `POSTGRES_HOST` and `OLLAMA_BASE_URL` are overridden inside Compose to the service names (`postgres`, `ollama`) so container-to-container DNS resolves correctly, while the same `.env` file's `localhost`-based defaults work for running the backend outside Docker. The frontend talks to the backend over `http://localhost:8000` from the browser (not container-to-container), since it's the user's browser - not another container - making the request.

## Integration points for later phases

- **Phase 4 (retrieval + grounding) - done.** See "Knowledge base (Phase 4)" above for the full pipeline.
- **Phase 5 (Ship 30 for 30 + artifacts)**: the `artifacts` table (`app/db/models.py`) and `components/layout/artifact-panel.tsx` are the integration points - both already exist, one persists nothing yet and the other renders an empty state, until Phase 5 connects them. A Ship 30 for 30 skill would naturally reuse the same `KnowledgeRetriever` this phase built.
- **Phase 6 (resilience)**: `MODEL_TIMEOUT_SECONDS`, `AgentError` (now including `RetrievalError`), and `KnowledgeRetriever`'s BM25 approach are the hooks for more sophisticated resilience/scale (circuit breaking, provider fallback, backoff, a move to Postgres FTS/pgvector at a larger corpus size) without touching the API contract.
