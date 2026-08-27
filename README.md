# Lenny Growth Assistant

An AI growth advisor grounded in Lenny Rachitsky's product and growth interviews, essays, and podcast transcripts. This repository is being built in seven phases; **this README reflects Phase 1 only** - the foundation. Later phases add retrieval-grounded answers, the Ship 30 for 30 skill, artifact generation, and resilience/testing hardening. Claims below are scoped to what actually exists today.

## What exists today (Phase 1)

- A FastAPI backend with typed configuration, structured logging, centralized error handling, and `/health` / `/health/ready` endpoints.
- A React + TypeScript + Tailwind frontend with a polished three-pane product shell (navigation, chat workspace, artifact panel) and a reusable design-system component library. No chat or artifact functionality is wired up yet - by design.
- Docker Compose orchestrating the backend, frontend, PostgreSQL, and Ollama for local development.
- A PostgreSQL connection foundation (no application schema yet - that is Phase 2).
- An Ollama service wired for future model calls (no model-provider abstraction yet - that is Phase 3).

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

The `ollama` container starts empty - it does **not** auto-download a model on `docker compose up` so that every developer isn't forced into a multi-gigabyte download just to boot the stack. Pull a model once the container is running:

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

Change `OLLAMA_MODEL` in `.env` if you pull a different model. Model calls themselves are not implemented until Phase 3 - Phase 1 only establishes the configuration and the running service.

## Verifying the stack

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

`/health` returns `{"status": "ok", ...}` as soon as the API process is up. `/health/ready` checks PostgreSQL connectivity and returns HTTP 503 with `"status": "degraded"` if the database isn't reachable yet - useful while the `postgres` container is still starting.

Open http://localhost:5173 to see the frontend shell.

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
├── backend/              FastAPI application (app/, tests/)
├── frontend/             React + TypeScript + Tailwind application (src/)
├── docs/                 PRD, design, and architecture documentation
├── tests/                Reserved for cross-cutting/integration tests (Phase 2+)
├── scripts/              Reserved for operational scripts (Phase 2+)
├── agent_transcripts/    Development history/transcripts for later phases
├── docker-compose.yml    Local orchestration: backend, frontend, postgres, ollama
└── .env.example          Documented environment variables
```

See `docs/architecture.md` for the system design and module boundaries, `docs/design.md` for the UI/UX approach, and `docs/PRD.md` for product scope.

## Known limitations (intentionally deferred)

These are not bugs - they are out of scope for Phase 1 by design:

- No chat, agent orchestration, or model calls are wired up yet (Phase 3).
- No conversation, message, or artifact persistence schema exists yet (Phase 2).
- No retrieval/RAG over Lenny's transcripts yet (Phase 4).
- No Ship 30 for 30 skill yet (Phase 4).
- No artifact generation or sanitized artifact viewer yet (Phase 5).
- `npm audit` reports vulnerabilities in `esbuild`/`vite` as transitively pulled in by `vitest`'s dev tooling; these affect only the local Vite dev server's request handling, not the production build output, and are tracked for a future dependency bump rather than a breaking `vitest@4` upgrade mid-phase.

## Troubleshooting

- **`docker compose up` fails to bind a port**: something else on your machine is using 5173, 8000, 5432, or 11434. Stop that process or change the port mapping in `docker-compose.yml`.
- **`/health/ready` stays degraded**: the `postgres` container may still be starting. Check `docker compose logs postgres`.
- **Frontend can't reach the backend**: confirm `VITE_API_BASE_URL` in `frontend/.env` matches where the backend is actually listening, and check CORS_ALLOW_ORIGINS on the backend includes the frontend's origin.
- **Ollama calls fail**: Phase 1 does not call Ollama yet, so this is expected - confirm the container is running and a model is pulled (see above) in preparation for Phase 3.
