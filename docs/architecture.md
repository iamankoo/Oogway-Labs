# Architecture

**Status:** Phase 1 + Phase 2. Documents what is actually built plus the boundaries left for later phases to plug into. Update this document as each phase lands - it should never describe unimplemented behavior as if it exists.

## System overview

```
Frontend (React/Vite)
    |  HTTP (fetch), CORS-restricted to VITE_API_BASE_URL
    v
FastAPI API  (backend/app/main.py, backend/app/api/)
    |
    v
Application / Agent Orchestration Layer   <- Phase 3 (backend/app/domain/, currently empty)
    |
    +-- Skills + Tools                    <- Phase 4/5
    |     +-- Grounded QA
    |     +-- Ship30
    |     +-- Artifact generation
    |
    v
Retrieval / Knowledge Layer               <- Phase 4 (not yet built)
    |
    v
PostgreSQL (persistence)  +  vector-capable index (later)
    |
    v
LLM Provider                              <- Phase 3 (backend/app/services/, currently empty)
    +-- Ollama (running today, not yet called)
    +-- Cloud provider (not yet built)
```

Phase 1 implemented everything above the "Application / Agent Orchestration Layer" line, plus the raw infrastructure (PostgreSQL, Ollama) below it. Phase 2 fills in the PostgreSQL box with a real schema and connects the API to it through `app/db/models.py` and `app/services/conversations.py` - but the orchestration/skills/retrieval layers are still deliberate placeholders: no model is called, no answer is generated, only conversation state is persisted.

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
    │   ├── health.py       GET /health, GET /health/ready
    │   ├── sessions.py     Session + message endpoints (Phase 2).
    │   └── schemas.py      Pydantic request/response models for the API.
    ├── core/
    │   ├── errors.py     AppError hierarchy + centralized exception handlers.
    │   └── responses.py  Shared Pydantic response models.
    ├── db/
    │   ├── session.py    Async SQLAlchemy engine/sessionmaker, the
    │   │                 `/health/ready` check, and the `get_db` FastAPI
    │   │                 dependency.
    │   ├── models.py     ORM models: User, ChatSession, Message, Artifact.
    │   └── types.py      `GUID` - a portable UUID column type (native
    │                     `UUID` on PostgreSQL, `CHAR(36)` elsewhere) so the
    │                     same models run against SQLite in tests.
    ├── services/
    │   └── conversations.py  Data-access layer: create/list/get sessions,
    │                         list/create messages. Owns session isolation
    │                         and the deterministic title-derivation logic.
    └── domain/           Placeholder for agent orchestration and skill
                          dispatch (Phase 3/4).
```

**Why this split:** `api/` never talks to the database or a model provider directly - it depends on `domain/` (once populated) or, for Phase 1, directly on the narrow `db/session.check_database_connection()` helper for the readiness check. This keeps HTTP concerns (status codes, request/response shapes) separate from business logic, so Phase 3 can introduce agent orchestration under `domain/` without touching `api/health.py` at all.

### Configuration

`app/config.py` defines a single `Settings` (pydantic-settings) class. Every other module imports `get_settings()` rather than calling `os.getenv` - this is enforced by convention now and should stay that way as new settings are added in later phases. `Settings` validates types and enum-like fields (`app_env`, `log_level`) at startup, so a typo'd environment variable fails fast with a clear error instead of silently misbehaving at runtime.

### Error handling

`app/core/errors.py` defines `AppError` (and subclasses like `NotFoundError`) that carry a `code`, HTTP `status_code`, and a safe user-facing `message`. `register_exception_handlers` attaches handlers for `AppError`, FastAPI's `RequestValidationError`, Starlette's `HTTPException`, and a catch-all `Exception` handler - the last of which logs the real exception server-side but returns a generic `internal_error` message to the client, so stack traces never leak to the frontend. Later phases (model errors, retrieval errors, artifact errors) should subclass `AppError` rather than inventing a new response shape.

### Health vs. readiness

`/health` never touches a dependency - it exists purely to answer "is the process alive," and must stay that way so it can be used as a fast liveness probe. `/health/ready` is where dependency checks belong; Phase 1 checks PostgreSQL only (via a real `SELECT 1`, not a hard-coded "ok"), and returns HTTP 503 with `status: "degraded"` if it fails. Adding an Ollama or retrieval-index check later means appending to the `dependencies` list in `api/health.py` - the response shape already supports multiple dependencies.

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

### Conversation API

All endpoints live under `/api/sessions` (`app/api/sessions.py`), return the shapes defined in `app/api/schemas.py` (never raw ORM objects), and use the Phase 1 error envelope for failures:

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/sessions` | Creates a session titled `"New conversation"` for the demo user. `201`. |
| `GET` | `/api/sessions` | Lists the demo user's sessions, most recently active first. `200`. |
| `GET` | `/api/sessions/{id}` | Returns one session. `404` (`session_not_found`) if missing or not owned. |
| `GET` | `/api/sessions/{id}/messages` | Lists messages in creation order. `404` under the same rule. |
| `POST` | `/api/sessions/{id}/messages` | Creates a **user** message (the request schema only accepts `role: "user"` - a client cannot post a fake assistant/system message). `201`, returns both the created message and the (possibly retitled) session. |

Title derivation is deterministic, not AI-generated: the first user message in a session becomes its title (truncated to 60 characters with an ellipsis if longer); later messages never overwrite an already-derived title. See `services.conversations._derive_title_from_content`.

## Frontend structure

```
frontend/src/
├── main.tsx, App.tsx        Entry point and top-level providers.
├── index.css                 Design tokens (CSS custom properties) + Tailwind v4 theme mapping.
├── lib/
│   ├── utils.ts               `cn()` class-merging helper.
│   ├── config.ts              The only place that reads `import.meta.env`.
│   ├── api.ts                 Typed fetch client (`ApiError` + the `api.*` methods)
│   │                          for `/api/sessions`. The only place that calls `fetch`.
│   ├── types.ts                `Session`/`Message` types shared by api.ts and the UI.
│   └── session-grouping.ts     Pure functions: bucket sessions into Today/Yesterday/
│                              Earlier, format a session's sidebar timestamp.
├── components/
│   ├── ui/                    Design-system primitives (Button, Input, Textarea,
│   │                          Card, Badge, Tooltip, Dialog, Spinner, EmptyState,
│   │                          Skeleton, SourceCard, WaveformIcon).
│   └── layout/                App shell composition (AppShell, Sidebar, TopBar,
│                              ArtifactPanel, NavItem, SessionItem, ThemeToggle).
└── features/
    └── chat/                  ConversationsProvider (state), ChatWorkspace,
                               WelcomeState, Composer, MessageList, MessageBubble -
                               the chat-specific composition, kept separate from
                               generic layout so a future `features/artifacts/`
                               can sit alongside it without entangling the two.
```

**Why `components/ui` vs `components/layout` vs `features/`:** `ui/` has zero product knowledge - a `Button` doesn't know it's used in a chat app. `layout/` knows about the app's shell (sidebar, panels) but not about chat-specific concepts (it reads session data from `features/chat`'s context, but doesn't own it). `features/chat/` is the one place that knows about conversations, messages, and drafts. This means Phase 4/5's `features/artifacts/` can be added without reaching into `components/`.

### Frontend state model

`features/chat/conversations-context.tsx` is the single source of truth for conversation state - one React context (`ConversationsProvider`, mounted once in `AppShell`) rather than scattering `fetch` calls and `useState` across components. It owns:

- **Sessions**: fetched once on mount; `sessionsState` is `"loading" | "idle" | "error"` so the sidebar can render a skeleton, the real list, or an error-with-retry without any component juggling booleans itself.
- **Active session id**: persisted to `localStorage` (a per-browser convenience, not authentication) so a page refresh restores the same open conversation - falling back to the most recently active session if the stored id no longer exists.
- **Messages for the active session**: refetched whenever the active session changes; reset to `[]` immediately on switch so a slow request can never flash session A's messages while session B is loading.
- **Sending a message**: `sendMessage()` creates a session first if none is active yet (so typing directly into the empty state and hitting send "just works"), then posts the message and appends the real server response - it never fabricates an optimistic assistant reply. A `skipNextMessagesFetch` ref avoids a subtle race where a freshly created session's (empty) message-list fetch could resolve *after* the first message was appended and wipe it back to `[]`.

No state-management library was added for this - `useState`/`useEffect`/`useContext` are sufficient for one provider with a handful of fields, and pulling in Redux/Zustand/React Query for this would be exactly the kind of unnecessary dependency the project intentionally avoids.

No fake assistant responses are ever rendered: `MessageBubble` supports `user`/`assistant`/`system` roles so Phase 3 can start rendering real assistant messages without a rework, but Phase 2's `ConversationsProvider` only ever appends messages that came back from `POST /api/sessions/{id}/messages`, which itself only accepts `role: "user"`.

## Local development architecture

`docker-compose.yml` runs four services on one bridge network (`lenny_network`): `postgres`, `ollama`, `backend`, `frontend`. The backend's `POSTGRES_HOST` and `OLLAMA_BASE_URL` are overridden inside Compose to the service names (`postgres`, `ollama`) so container-to-container DNS resolves correctly, while the same `.env` file's `localhost`-based defaults work for running the backend outside Docker. The frontend talks to the backend over `http://localhost:8000` from the browser (not container-to-container), since it's the user's browser - not another container - making the request.

## Integration points for later phases

- **Phase 3 (agent orchestration + model provider)**: implement routing/dispatch under `app/domain/`, and an Ollama/cloud client under a new `app/services/model_provider.py`, both importing `get_settings()` for `ollama_base_url`/`ollama_model`. The orchestration layer would call `services.conversations.create_message(..., role=MessageRole.assistant, ...)` to persist the generated reply using the same data-access path user messages already go through - no new isolation logic needed. `MessageCreate` in `api/schemas.py` intentionally only accepts `role: "user"` from clients; an assistant-authored endpoint (or the same endpoint gated differently) is a Phase 3 decision.
- **Phase 4 (retrieval + Ship 30 for 30)**: add a retrieval client under `app/services/` and skills under `app/domain/`. The `metadata`-shaped extension point for citations is the message's future `sources`/citation data - `components/ui/source-card.tsx` already establishes the visual foundation, unused until real retrieval exists.
- **Phase 5 (artifacts)**: the `artifacts` table (`app/db/models.py`) and `components/layout/artifact-panel.tsx` are the integration points - both already exist, one persists nothing yet and the other renders an empty state, until Phase 5 connects them.
