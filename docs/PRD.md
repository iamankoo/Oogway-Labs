# Product Requirements Document: Lenny Growth Assistant

**Status:** Foundational draft, written during Phase 1, updated after Phase 2 (persistence + conversation UI) and Phase 3 (real agent/model layer). Scope, flows, and metrics will be refined as later phases (retrieval, Ship 30 for 30, artifacts) are implemented.

## Problem

Product and growth practitioners have access to an enormous amount of high-quality advice from Lenny Rachitsky's newsletter, podcast interviews, and essays - but that knowledge is locked inside hours of transcripts and hundreds of posts. Finding the specific, relevant advice for a specific situation (e.g. "how do I know if I've found product-market fit?") means manually searching or remembering which episode covered it.

## Target user

Product managers, growth leads, and early-stage founders who already follow Lenny's content and want to consult it conversationally, in the context of their own specific product decisions, instead of re-reading or re-listening to find the relevant part.

## Jobs to be done

- "When I'm about to make a product or growth decision, help me quickly recall what an expert has said about this exact situation, with enough detail that I can act on it."
- "When I want a repeatable framework (e.g. an experiment plan, an onboarding audit), help me generate one grounded in proven practice rather than generic advice."

## Proposed solution

A conversational assistant, backed by retrieval over Lenny's transcripts and essays, that:

1. Answers product/growth questions with advice traceable back to specific source material (interviews, essays).
2. Can produce structured artifacts (frameworks, experiment plans, critiques) when a conversational answer isn't the right format.
3. Runs locally by default (via Ollama) with the option to point at a cloud model provider.

## Assumptions

- The user has, or will be given, a corpus of Lenny transcripts/essays to ingest (Phase 4).
- A single-user, local-first deployment model is acceptable for this assignment; multi-tenant auth is out of scope.
- Ollama running locally is an acceptable default model provider for development and demonstration; a cloud provider is a pluggable alternative, not a requirement.

## Scope (by phase)

| Phase | Scope |
|-------|-------|
| 1 (done) | Architecture, FastAPI + React foundation, Docker Compose, health/readiness, design system, docs |
| 2 (done) | PostgreSQL schema for users/conversations/messages, Alembic migrations, conversation API, real session/message persistence wired into a redesigned conversation UI |
| 3 (this phase) | Real agent layer + model provider abstraction (Ollama mandatory local, Anthropic Claude cloud), assistant reply generation and persistence, retry semantics, Markdown-rendered assistant messages, provider visibility in the UI |
| 4 | Lenny transcript ingestion/RAG (Grounded QA), Ship 30 for 30 skill |
| 5 | Artifact generation and a sanitized artifact viewer |
| 6 | Resilience hardening (timeouts, retries, degraded-mode behavior) |
| 7 | Comprehensive tests and final demo readiness |

## Non-goals (for the assignment as a whole, unless stated otherwise later)

- Multi-user accounts, authentication, or authorization.
- Billing or usage metering.
- Mobile native apps (the web frontend is responsive, not a separate mobile app).
- Support for arbitrary third-party knowledge sources beyond Lenny's content.

## Core user flows

1. **Start and persist a conversation** (Phase 2, implemented): user starts a new conversation, sends a message, refreshes the browser, and finds both the conversation and the message exactly as they left them.
2. **Ask and get a real answer** (Phase 3, implemented): user asks a product/growth question → the configured model (Ollama locally, or Anthropic Claude if configured for cloud) generates a genuine response, reasoning from its own general knowledge, honest that it isn't yet grounded in Lenny's actual content → the reply persists and survives a refresh; a follow-up question is answered with the prior turn in context.
3. **Grounded Q&A** (target end state, Phase 4, not yet implemented): the same flow as above, but the assistant retrieves relevant transcript passages first and answers with citations back to real source material.
4. **Ship 30 for 30** (not yet implemented): user requests a 30-day shipping plan for a stated goal → assistant produces a structured, day-by-day artifact.
5. **Artifact review** (not yet implemented): user asks for a framework or document → assistant generates it as an artifact in the right-hand panel, which the user can review and export.

## Acceptance criteria (Phase 1)

- `docker compose up --build` starts backend, frontend, PostgreSQL, and Ollama without manual intervention beyond copying `.env.example`.
- `/health` and `/health/ready` behave as documented in `README.md`.
- The frontend renders a complete, responsive, accessible application shell with realistic empty/loading/disabled states, without pretending chat or artifacts work yet.
- No secrets are committed; all configuration is environment-driven.

## Acceptance criteria (Phase 2)

- Creating a conversation, sending a message, and refreshing the page all work against real PostgreSQL persistence - no local-only/in-memory state stands in for the backend.
- Two different conversations never leak each other's messages, enforced in the backend's data-access layer (not just by the frontend not asking).
- The schema is versioned with Alembic, applied automatically when the backend container starts - no manual `create_all` step for the evaluator to run.
- No assistant reply is fabricated anywhere in the UI or API - the composer, message list, and API responses are all honest that only the user's own message was saved.
- The conversation UI is judged as a deliberate, premium, product-specific design - not a generic chatbot template - per the design principles in `docs/design.md`.

## Acceptance criteria (Phase 3)

- A real user question, sent through the running app, produces a real model-generated reply - via the mandatory local Ollama provider by default - that persists across a refresh.
- `LLM_PROVIDER=cloud` (with `CLOUD_API_KEY` set) routes the same flow through the real Anthropic API instead, with no code change - only configuration.
- A model/provider failure (unreachable Ollama, model not pulled, missing cloud credentials, timeout) never crashes the request or fabricates a reply - the user's message stays saved, and a clear, actionable, safe error is returned with a working retry path that never duplicates the user's turn.
- A follow-up question is answered using the prior turns in the same session as context; two different sessions never share context or messages.
- The assistant never claims its answers are grounded in Lenny's actual podcast/newsletter content - Phase 4 is what makes that true.
- The UI visibly and honestly shows which provider/model is active, renders assistant Markdown safely (no raw HTML execution), and reads as a deliberate, premium product experience - not a generic AI chat template - per `docs/design.md`.

## Risks and trade-offs

- **Local-only LLM quality**: Ollama-hosted open models may give weaker answers than a cloud frontier model. Mitigated by keeping the model-provider abstraction pluggable (implemented in Phase 3) rather than hard-coding Ollama everywhere.
- **Cloud path verification gap**: no real Anthropic API key was available in the development environment, so the cloud provider's happy path (an actual generated reply) is unit-tested with a mocked SDK but was not exercised against the live Anthropic API - only its configuration and error-handling paths were verified live. See `docs/architecture.md` for exactly what was and wasn't exercised, and the README for how a engineer with credentials can complete that verification.
- **Retrieval quality depends on corpus**: without real transcripts to ingest, Phase 4's RAG quality is bounded by whatever sample corpus is available.
- **Scope discipline across 7 phases**: the biggest execution risk is scope creep - implementing later-phase functionality early creates rework. This is why Phase 1 stopped at architecture and UI shell, Phase 2 stopped at persistence without a model, and Phase 3 stops at a real but ungrounded assistant - deliberately, even though each would have been easy to keep going.

## Initial success metrics (directional, to be made concrete once Phase 4-5 ship)

- Time-to-relevant-answer for a product/growth question, compared to manually searching the newsletter/podcast.
- Fraction of answers with a traceable citation (retrieval grounding rate).
- Whether a generated artifact (e.g. a Ship 30 for 30 plan) is usable without heavy editing.
