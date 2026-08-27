# Product Requirements Document: Lenny Growth Assistant

**Status:** Foundational draft, written during Phase 1, updated after Phase 2 (persistence + conversation UI), Phase 3 (real agent/model layer), and Phase 4 (real grounded retrieval over Lenny's actual source material). Scope, flows, and metrics will be refined as later phases (Ship 30 for 30, artifacts) are implemented.

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

- The free official "Lenny's Data" starter pack (50 podcast transcripts + 10 newsletter posts, from `github.com/LennysNewsletter/lennys-newsletterpodcastdata`) is acceptable source material for this assignment's demo; the full paid archive (349+/289+) would work identically if an evaluator has access to it, but that was not what was actually ingested/verified here.
- A single-user, local-first deployment model is acceptable for this assignment; multi-tenant auth is out of scope.
- Ollama running locally is an acceptable default model provider for development and demonstration; a cloud provider is a pluggable alternative, not a requirement.
- Lexical (BM25) retrieval, not semantic/vector search, is an acceptable grounding mechanism at this corpus size - see `docs/architecture.md` "Retrieval strategy" for the explicit tradeoff this accepted.

## Scope (by phase)

| Phase | Scope |
|-------|-------|
| 1 (done) | Architecture, FastAPI + React foundation, Docker Compose, health/readiness, design system, docs |
| 2 (done) | PostgreSQL schema for users/conversations/messages, Alembic migrations, conversation API, real session/message persistence wired into a redesigned conversation UI |
| 3 (done) | Real agent layer, built on the required **Pi Coding Agent** framework (`pi-coding-agent`, see `docs/architecture.md` "Agent framework choice"), + model provider abstraction (Ollama mandatory local, Anthropic Claude cloud), assistant reply generation and persistence, retry semantics, Markdown-rendered assistant messages, provider visibility in the UI |
| 4 (this phase) | Real Lenny knowledge base (ingestion of the official free source repository), BM25 retrieval service, grounded answers with structured per-message citations rendered via `SourceCard`, honest "no support found" behavior for unsupported questions |
| 5 | Ship 30 for 30 skill, artifact generation, and a sanitized artifact viewer |
| 6 | Resilience hardening (timeouts, retries, degraded-mode behavior) |
| 7 | Comprehensive tests and final demo readiness |

## Non-goals (for the assignment as a whole, unless stated otherwise later)

- Multi-user accounts, authentication, or authorization.
- Billing or usage metering.
- Mobile native apps (the web frontend is responsive, not a separate mobile app).
- Support for arbitrary third-party knowledge sources beyond Lenny's content.

## Core user flows

1. **Start and persist a conversation** (Phase 2, implemented): user starts a new conversation, sends a message, refreshes the browser, and finds both the conversation and the message exactly as they left them.
2. **Ask and get a real answer** (Phase 3, implemented): user asks a product/growth question → the configured model (Ollama locally, or Anthropic Claude if configured for cloud) generates a genuine response → the reply persists and survives a refresh; a follow-up question is answered with the prior turn in context.
3. **Grounded Q&A** (Phase 4, implemented): the assistant retrieves relevant transcript/newsletter passages from the real ingested Lenny corpus before answering, and cites them as structured `SourceCard`s (episode title, guest, publication date, and a link when the source repository actually provides one) - never fabricated. When retrieval finds no adequate support, the assistant is instructed to say so rather than silently answer as if it were grounded.
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

## Acceptance criteria (Phase 4)

- Ingestion (`python -m app.knowledge.ingest --source <path>`) against the real official Lenny's Data starter pack succeeds with zero failures and produces a verifiable, non-zero document/chunk count (`GET /api/knowledge/status`).
- Running ingestion twice never creates duplicate documents or chunks (idempotency, verified by an automated test and by a real repeat run against the ingested corpus).
- A supported product/growth question produces a grounded answer with one or more `SourceCard`s, each citing a real ingested document with real (never fabricated) title/guest/date/URL fields.
- An unsupported/out-of-domain question never produces a fabricated citation - `sources` is empty and `grounded` is `false` at the API level, regardless of what the model's prose says.
- A follow-up question's retrieval incorporates enough conversational context to resolve short references like "how about for B2B?" without embedding the entire conversation history into the query.
- Sources persist across a browser refresh exactly like the message they're attached to.
- No transcript content is ever executed or treated as an instruction - retrieved excerpts are explicitly labeled as untrusted reference data in the prompt sent to the model.

## Risks and trade-offs

- **Local-only LLM quality**: Ollama-hosted open models may give weaker answers than a cloud frontier model. Mitigated by keeping the model-provider abstraction pluggable (implemented in Phase 3) rather than hard-coding Ollama everywhere.
- **Cloud path verification gap**: no real Anthropic API key was available in the development environment, so the cloud provider's happy path (an actual generated reply) is unit-tested with a mocked SDK but was not exercised against the live Anthropic API - only its configuration and error-handling paths were verified live. See `docs/architecture.md` for exactly what was and wasn't exercised, and the README for how a engineer with credentials can complete that verification.
- **Lexical retrieval, not semantic**: BM25 over exact vocabulary means a paraphrase that shares no words with the source material won't be found even if the topic is covered. Accepted deliberately at this corpus size and stack - see `docs/architecture.md` "Retrieval strategy" for the full reasoning and the stated upgrade path (Postgres FTS or pgvector) if the corpus grows substantially.
- **Free starter-pack corpus, not the full archive**: retrieval quality and topic coverage are bounded by the 50 podcasts + 10 newsletters actually ingested and verified; the full paid archive was not available in this environment.
- **Small local model's instruction-following**: `llama3.2:1b` doesn't always verbally hedge "no Lenny support for this" as consistently as instructed, even though the underlying citation data is never fabricated regardless of the model's wording - observed directly during real-data verification, documented in `docs/architecture.md` "Grounding prompt and empty retrieval".
- **Scope discipline across 7 phases**: the biggest execution risk is scope creep - implementing later-phase functionality early creates rework. This is why each phase stopped at its stated scope, even though each would have been easy to keep going.

## Success metric (knowledge quality, Phase 4)

For a curated evaluation set of 5 representative questions (2 clearly-supported product/growth topics, 1 nuanced product question, 1 follow-up, 1 out-of-domain question), **grounded answers should contain at least one genuinely supporting, non-fabricated source, and unsupported questions should never receive a fabricated one.**

**Measured result** (see `docs/architecture.md` "Retrieval strategy" and the Phase 4 completion report for the exact questions/scores): against the real ingested corpus, all clearly-supported and nuanced questions tested returned genuinely relevant sources (real episode titles/guests, BM25 scores in the 8-15 range); the out-of-domain and previously-problematic edge-case queries ("what's the best way to cook a lasagna", "tell me about the weather in Paris", "what is the airspeed velocity of an unladen swallow") returned **zero** sources after a real retrieval-precision bug (a single rare-word coincidental match outscoring genuine matches) was found and fixed during verification - **0 fabricated sources observed across all tested questions.**

## Initial success metrics (directional, to be made concrete once Phase 5 ships)

- Time-to-relevant-answer for a product/growth question, compared to manually searching the newsletter/podcast.
- Whether a generated artifact (e.g. a Ship 30 for 30 plan) is usable without heavy editing.
