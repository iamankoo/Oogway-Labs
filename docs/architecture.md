# Architecture

**Status:** Phase 1. Documents what is actually built plus the boundaries left for later phases to plug into. Update this document as each phase lands - it should never describe unimplemented behavior as if it exists.

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

Phase 1 implements everything above the "Application / Agent Orchestration Layer" line, plus the raw infrastructure (PostgreSQL, Ollama) below it. Everything from that line down is a deliberate placeholder: the module/package exists so later phases have an obvious home, but no logic lives there yet.

## Why a modular monolith

The assignment architecture has several conceptual layers (orchestration, skills, retrieval, persistence, model provider), but standing these up as separate services on day one would add deployment and networking complexity with no corresponding benefit at this stage - there's a single consumer (the frontend) and a single team (one engineer building all seven phases). A modular monolith - one FastAPI process with clearly separated packages - gets the same separation of concerns without the operational overhead, and can be split into services later if a real scaling reason appears.

## Backend structure

```
backend/app/
├── main.py           Application factory: builds the FastAPI app, wires
│                     middleware, exception handlers, and routers. No
│                     module-level side effects beyond constructing `app`.
├── config.py         Settings (pydantic-settings). The only place that
│                     reads environment variables.
├── logging_config.py Structlog setup shared by the whole process.
├── api/              HTTP-facing routers (currently: health.py).
│   └── health.py     GET /health, GET /health/ready
├── core/
│   ├── errors.py     AppError hierarchy + centralized exception handlers.
│   └── responses.py  Shared Pydantic response models.
├── db/
│   └── session.py    Async SQLAlchemy engine/session factory and a
│                     readiness check. No ORM models yet (Phase 2).
├── domain/           Placeholder for agent orchestration and skill
│                     dispatch (Phase 3/4).
└── services/         Placeholder for the model-provider abstraction and
                      retrieval client (Phase 3/4).
```

**Why this split:** `api/` never talks to the database or a model provider directly - it depends on `domain/` (once populated) or, for Phase 1, directly on the narrow `db/session.check_database_connection()` helper for the readiness check. This keeps HTTP concerns (status codes, request/response shapes) separate from business logic, so Phase 3 can introduce agent orchestration under `domain/` without touching `api/health.py` at all.

### Configuration

`app/config.py` defines a single `Settings` (pydantic-settings) class. Every other module imports `get_settings()` rather than calling `os.getenv` - this is enforced by convention now and should stay that way as new settings are added in later phases. `Settings` validates types and enum-like fields (`app_env`, `log_level`) at startup, so a typo'd environment variable fails fast with a clear error instead of silently misbehaving at runtime.

### Error handling

`app/core/errors.py` defines `AppError` (and subclasses like `NotFoundError`) that carry a `code`, HTTP `status_code`, and a safe user-facing `message`. `register_exception_handlers` attaches handlers for `AppError`, FastAPI's `RequestValidationError`, Starlette's `HTTPException`, and a catch-all `Exception` handler - the last of which logs the real exception server-side but returns a generic `internal_error` message to the client, so stack traces never leak to the frontend. Later phases (model errors, retrieval errors, artifact errors) should subclass `AppError` rather than inventing a new response shape.

### Health vs. readiness

`/health` never touches a dependency - it exists purely to answer "is the process alive," and must stay that way so it can be used as a fast liveness probe. `/health/ready` is where dependency checks belong; Phase 1 checks PostgreSQL only (via a real `SELECT 1`, not a hard-coded "ok"), and returns HTTP 503 with `status: "degraded"` if it fails. Adding an Ollama or retrieval-index check later means appending to the `dependencies` list in `api/health.py` - the response shape already supports multiple dependencies.

### Database

`app/db/session.py` creates one process-wide async SQLAlchemy engine on startup (via the FastAPI `lifespan` context in `main.py`) and disposes it on shutdown. Phase 1 deliberately does not define ORM models or a schema - that's Phase 2's job, once the actual conversation/message/artifact shape is designed. The engine and a `get_session()` context manager already exist so Phase 2 can start writing repositories immediately.

## Frontend structure

```
frontend/src/
├── main.tsx, App.tsx        Entry point and top-level providers.
├── index.css                 Design tokens (CSS custom properties) + Tailwind v4 theme mapping.
├── lib/
│   ├── utils.ts               `cn()` class-merging helper.
│   └── config.ts              The only place that reads `import.meta.env`.
├── components/
│   ├── ui/                    Design-system primitives (Button, Input, Textarea,
│   │                          Card, Badge, Tooltip, Dialog, Spinner, EmptyState).
│   └── layout/                App shell composition (AppShell, Sidebar, TopBar,
│                              ArtifactPanel, NavItem, ThemeToggle).
└── features/
    └── chat/                  WelcomeState, Composer, ChatWorkspace - the
                               chat-specific composition, kept separate from
                               generic layout so a future `features/artifacts/`
                               can sit alongside it without entangling the two.
```

**Why `components/ui` vs `components/layout` vs `features/`:** `ui/` has zero product knowledge - a `Button` doesn't know it's used in a chat app. `layout/` knows about the app's shell (sidebar, panels) but not about chat-specific concepts. `features/chat/` is the one place that knows about conversations, drafts, and prompts. This means Phase 2+'s `features/artifacts/` (or a real chat message list) can be added without reaching into `components/`.

## Local development architecture

`docker-compose.yml` runs four services on one bridge network (`lenny_network`): `postgres`, `ollama`, `backend`, `frontend`. The backend's `POSTGRES_HOST` and `OLLAMA_BASE_URL` are overridden inside Compose to the service names (`postgres`, `ollama`) so container-to-container DNS resolves correctly, while the same `.env` file's `localhost`-based defaults work for running the backend outside Docker. The frontend talks to the backend over `http://localhost:8000` from the browser (not container-to-container), since it's the user's browser - not another container - making the request.

## Integration points for later phases

- **Phase 2 (persistence)**: add ORM models under a new `app/db/models/` (or similar) and repositories under `app/services/`; `db/session.py`'s engine is already available.
- **Phase 3 (agent orchestration + model provider)**: implement routing/dispatch under `app/domain/`, and an Ollama/cloud client under `app/services/`, both importing `get_settings()` for `ollama_base_url`/`ollama_model`.
- **Phase 4 (retrieval + Ship 30 for 30)**: add a retrieval client under `app/services/` and skills under `app/domain/`; the frontend's `features/chat/` already has a place to render citations once answers carry them.
- **Phase 5 (artifacts)**: `components/layout/artifact-panel.tsx` and its API route are the integration points - the panel already exists, it just renders an empty state until there's something to show.
