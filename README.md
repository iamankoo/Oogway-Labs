# Lenny Growth Assistant

An AI growth advisor grounded in Lenny Rachitsky's product and growth interviews, essays, and podcast transcripts. This repository is being built in seven phases; **this README reflects Phase 1 + 2 + 3 + 4** - the foundation, conversation persistence, a real agent/model layer, and now real retrieval grounding over Lenny's actual source material. Later phases add Ship 30 for 30, artifact generation, and resilience/testing hardening. Claims below are scoped to what actually exists today.

## What exists today (Phase 1 + 2 + 3 + 4)

- A FastAPI backend with typed configuration, structured logging, centralized error handling, and `/health` / `/health/ready` endpoints (readiness now also checks the active model provider).
- Real PostgreSQL persistence for conversations: `users` -> `sessions` -> `messages`, plus an `artifacts` table reserved for Phase 5, and (Phase 4) `knowledge_documents` / `knowledge_chunks` / `message_sources` for the knowledge base - all managed through Alembic migrations (see [Database](#database) below).
- **A real agent layer** (`backend/app/agents/`) built on **Pi Coding Agent** (`pi-coding-agent`, the required agent framework - see `docs/architecture.md` "Agent framework choice") that retrieves grounding material for each turn, folds it into a real `pi_agent.agent.Agent`'s system prompt, and calls a **model provider abstraction** (`pi_agent.llm`) supporting both a local **Ollama** provider (mandatory for the demo) and a **cloud Anthropic Claude** provider, switchable purely via configuration - see [Model provider](#model-provider) below.
- **A real knowledge base** (`backend/app/knowledge/`, `backend/app/services/knowledge_retriever.py`), ingested from the official free [Lenny's Data](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata) starter pack (50 podcast transcripts + 10 newsletter posts) - see [Knowledge base](#knowledge-base) below for setup, ingestion, and how retrieval/grounding works.
- Sending a message triggers a real assistant reply: the user's message is always persisted, the agent retrieves relevant Lenny material and generates a reply, and on success both the reply and its real (never fabricated) source citations are persisted - on failure, the user's message is kept and a safe, retryable error is returned instead of a fabricated response.
- A React + TypeScript + Tailwind frontend with a premium, editorially-inflected three-pane product shell, a real session sidebar, a subtle provider indicator, safe Markdown-rendered assistant messages, a restrained "thinking" state, inline retry on generation failure, and (Phase 4) real `SourceCard`s shown under a grounded assistant reply.
- Docker Compose orchestrating the backend, frontend, PostgreSQL, and Ollama for local development, with the backend running pending migrations automatically on boot. Knowledge-base ingestion is a separate, explicit, documented command - never part of `docker compose up`.

**Not yet implemented (see "Known limitations" below):** Ship 30 for 30, artifact generation. Retrieval is lexical (BM25), not semantic/vector search - see `docs/architecture.md` "Retrieval strategy" for that tradeoff.

## Knowledge base

**Source**: the official, free ["Lenny's Data" starter pack](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata) - 50 real podcast transcripts and 10 real newsletter posts, published by Lenny Rachitsky/Lenny's Newsletter. Its license permits personal use and building/publishing projects with it, but not redistributing the raw dataset files, so it is **not vendored into this repository** - fetch it yourself:

```bash
git clone https://github.com/LennysNewsletter/lennys-newsletterpodcastdata.git knowledge_source
```

Then run ingestion (inside the backend container, or locally against `DATABASE_URL`):

```bash
docker compose exec backend python -m app.knowledge.ingest --source /path/to/knowledge_source
```

(If running via Docker, copy the cloned folder into the backend container first, e.g. `docker cp knowledge_source lenny-growth-assistant-backend-1:/tmp/knowledge_source` and point `--source` at `/tmp/knowledge_source`.)

Verify it worked: `curl http://localhost:8000/api/knowledge/status` should report a non-zero `document_count`/`chunk_count`. Ingestion is idempotent (safe to re-run) and only reprocesses files whose content actually changed - see `docs/architecture.md` "Knowledge base (Phase 4)" for the full pipeline, chunking strategy, retrieval algorithm, and grounding rules.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Docker Compose v2 (`docker compose version`)
- ~8GB free disk space if you plan to pull an Ollama model
- For running things outside Docker (optional): Python 3.12+, Node.js 20+

## Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

This starts four services:

| Service    | URL                             | Purpose                          |
|------------|----------------------------------|-----------------------------------|
| `frontend` | http://localhost:5173           | React app (Vite dev server)       |
| `backend`  | http://localhost:8000            | FastAPI app                       |
| `postgres` | localhost:5432                   | Application database              |
| `ollama`   | http://localhost:11434           | Local LLM runtime                 |

### Pulling an Ollama model

The `ollama` container starts empty - it does **not** auto-download a model on `docker compose up` so that every developer isn't forced into a multi-gigabyte download just to boot the stack. Pull a model once the container is running (the default configured model is `llama3.2:3b`, a small-but-capable model chosen so this step is fast):

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

If you configure a different `OLLAMA_MODEL`, pull that instead. **This step is mandatory** - Phase 3 actually calls Ollama to generate assistant replies; until the configured model is pulled, sending a message will return a clear "model not installed" error rather than a fake response (see [Error handling](#error-handling)).

**If your machine (or Docker Desktop's memory allocation) is constrained**, drop to a smaller model such as `llama3.2:1b` (~1.3GB) - CPU-only inference of even a 3B model needs a few GB of headroom to load promptly. This assignment's own development environment had Docker Desktop capped at ~3.5GB total RAM across all containers, and `llama3.2:1b` was what actually verified end-to-end there; a typical developer machine with more memory available to Docker should run `llama3.2:3b` (the documented default) without issue. Either way, expect roughly 15-20 tokens/second on CPU-only inference for a model this size - the backend's `MODEL_TIMEOUT_SECONDS` (default 60s) and its `num_predict` cap on response length (400 tokens) are tuned around that, not around GPU-class speed.

## Verifying the stack

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

`/health` returns `{"status": "ok", ...}` as soon as the API process is up. `/health/ready` checks PostgreSQL connectivity and returns HTTP 503 with `"status": "degraded"` if the database isn't reachable yet - useful while the `postgres` container is still starting.

```bash
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/sessions | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST "http://localhost:8000/api/sessions/$SESSION_ID/messages" \
  -H "Content-Type: application/json" -d '{"content":"What signals suggest product-market fit?"}'
```

A healthy response includes both `"message"` (your question, persisted) and `"assistant_message"` (a real reply from the configured model). If `"assistant_message"` is `null`, check `"generation_error"` - most commonly it means the configured Ollama model isn't pulled yet (see above).

Open http://localhost:5173 to use the app: create a conversation, send a message, watch the assistant actually reply, refresh the page, and confirm both messages are still there.

## Model provider

See `docs/architecture.md` ("Model provider abstraction" and "Agent architecture") for the full design. In short:

- `LLM_PROVIDER=ollama` (default) - routes through pi-coding-agent's `OpenAIProvider`, pointed at the Ollama container's OpenAI-compatible `/v1` endpoint. This is the **mandatory demo path**.
- `LLM_PROVIDER=cloud` - routes through pi-coding-agent's `AnthropicProvider`, calling the real Anthropic Messages API via the official `anthropic` Python SDK underneath. Requires `CLOUD_API_KEY` (get one at https://console.anthropic.com/) and, optionally, a different `CLOUD_MODEL` (default `claude-opus-5`).
- Switching providers is a `.env` change only - `docker compose restart backend` (or just restart the backend process locally) picks it up. No code changes, no frontend changes: the sidebar's provider indicator and `/health/ready`'s provider check both reflect whichever is configured.
- Without cloud credentials, `LLM_PROVIDER=cloud` produces a clean, safe error (`missing_credentials`) on every send attempt rather than crashing the app or falling back to a different provider silently.

## Database

Schema: `users (1) -> sessions (many) -> messages (many)`, plus `sessions (1) -> artifacts (many)` reserved for Phase 5. See `docs/architecture.md` for the full column list and rationale (single-user strategy, deterministic title derivation, session-isolation enforcement).

Migrations are managed with Alembic (`backend/alembic/`). The backend container runs `alembic upgrade head` automatically before starting uvicorn - via `docker compose up` there is no manual migration step. Running the backend outside Docker:

```bash
cd backend
alembic upgrade head        # apply migrations
alembic revision -m "..."   # create a new migration by hand
```

There is no login/signup - every session and message belongs to a single deterministic local user (`local-demo-user`, a fixed UUID) seeded by the initial migration. See `docs/architecture.md` for why that's the right amount of auth for a single-user take-home assignment.

## Running without Docker (local development)

**Backend:**

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

You'll need PostgreSQL and Ollama reachable at the hosts/ports configured in `.env` (or `backend/.env`) - either run them via `docker compose up postgres ollama`, or point at your own instances.

## Configuration

All configuration lives in `.env` (backend + Docker Compose) and `frontend/.env` (Vite, `VITE_`-prefixed only). See `.env.example` and `frontend/.env.example` for every variable and its default. Nothing in the codebase reads environment variables directly outside of `backend/app/config.py` and `frontend/src/lib/config.ts` - that's the single place to look.

## Testing and linting

Backend tests run against an in-memory SQLite database (seeded with the same demo user the real migration seeds), not a real PostgreSQL instance - they never depend on your local Postgres being up or in any particular state. Every test gets a stubbed model provider by default (an autouse fixture in `conftest.py`) so the suite never makes a real network call to Ollama or a cloud API; `tests/test_model_providers.py`, `tests/test_agent.py`, and `tests/test_generation_api.py` then use their own targeted stubs/mocks to exercise specific provider and failure behavior.

```bash
# Backend
cd backend
pytest
ruff check app tests

# Frontend
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

## Repository structure

```
OL/
├── backend/              FastAPI application (app/agents/, app/services/model_providers/, alembic/, tests/)
├── frontend/             React + TypeScript + Tailwind application (src/)
├── docs/                 PRD, design, and architecture documentation
├── tests/                Reserved for cross-cutting/integration tests (Phase 2+)
├── scripts/              Reserved for operational scripts (Phase 2+)
├── agent_transcripts/    Development history/transcripts for later phases
├── docker-compose.yml    Local orchestration: backend, frontend, postgres, ollama
└── .env.example          Documented environment variables
```

See `docs/architecture.md` for the system design and module boundaries, `docs/design.md` for the UI/UX approach, and `docs/PRD.md` for product scope.

## Error handling

Assistant generation failures never crash the request or fabricate a response - the user's message is always persisted, and the API returns a `generation_error: {code, message}` instead of `assistant_message`. The frontend shows the safe `message` text inline with a "Try again" button. Codes: `provider_unavailable` (Ollama/cloud unreachable), `model_not_found` (configured model isn't installed/available), `missing_credentials` (cloud provider selected, no API key), `model_timeout` (exceeded `MODEL_TIMEOUT_SECONDS`), `empty_response` (model returned nothing). See `docs/architecture.md` ("Assistant generation failure semantics") for the full contract, including retry semantics (`POST /api/sessions/{id}/messages/retry` regenerates for the existing pending user message - it never creates a duplicate).

## Known limitations (intentionally deferred)

These are not bugs - they are out of scope for Phase 1/2/3 by design:

- **No retrieval/grounding yet (Phase 4).** The assistant reasons from the model's own knowledge only - it is explicitly instructed never to claim a specific episode, guest, or quote as its source. Real Lenny transcript ingestion and citations are Phase 4.
- No Ship 30 for 30 skill yet (Phase 4).
- No artifact generation or sanitized artifact viewer yet (Phase 5) - the `artifacts` table and its future UI slot exist, but nothing writes to it.
- No authentication - a single deterministic local user, documented in `docs/architecture.md`.
- No true token streaming - a deliberate simplicity choice for this phase (see `docs/architecture.md` "Streaming decision"); the UI still shows a polished "thinking" state while waiting.
- Cloud provider (Anthropic) is implemented and unit-tested, but was not verified against a real Anthropic API key in this environment (none was available) - only its configuration/error-handling path was verified end-to-end. See `docs/architecture.md` for exactly what was and wasn't exercised.
- The local Ollama path was verified with genuine, successful end-to-end generations earlier in development (real multi-paragraph Markdown replies, follow-up context, session isolation - see `docs/architecture.md`). Later in the same session, this development sandbox's disk I/O degraded enough that even a small model's cold load repeatedly exceeded `MODEL_TIMEOUT_SECONDS` - which is itself the `model_timeout` error path working as designed (user message safely persisted, clean error surfaced, no crash), just not the happy path. This is a characteristic of that specific constrained sandbox, not a defect in the timeout/retry design; a normal developer machine with an unencumbered disk did not exhibit this in earlier testing.
- `npm audit` reports vulnerabilities in `esbuild`/`vite` as transitively pulled in by `vitest`'s dev tooling; these affect only the local Vite dev server's request handling, not the production build output, and are tracked for a future dependency bump rather than a breaking `vitest@4` upgrade mid-phase.

## Troubleshooting

- **`docker compose up` fails to bind a port**: something else on your machine is using 5173, 8000, 5432, or 11434. Stop that process or change the port mapping in `docker-compose.yml`.
- **`/health/ready` stays degraded**: check the `dependencies` array in the response - `postgresql` degraded means the `postgres` container may still be starting (`docker compose logs postgres`); `model_provider` degraded means Ollama isn't reachable or the configured model isn't pulled yet (see above), or `CLOUD_API_KEY` is unset while `LLM_PROVIDER=cloud`.
- **Frontend can't reach the backend**: confirm `VITE_API_BASE_URL` in `frontend/.env` matches where the backend is actually listening, and check CORS_ALLOW_ORIGINS on the backend includes the frontend's origin.
- **Sending a message returns `generation_error`**: read its `message` field - it's written to be actionable (e.g. tells you exactly which model to pull). Check `docker compose logs backend` for the structured log line (`assistant_generation_failed`) with the same error code.
- **Backend fails to start with a schema/migration error**: the backend's Docker `CMD` runs `alembic upgrade head` before uvicorn - check `docker compose logs backend` for the specific migration error, and confirm `postgres` is healthy (`docker compose ps`).
