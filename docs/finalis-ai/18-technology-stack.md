# Finalis AI — Recommended Technology Stack

> Principle: **buy/adopt the boring, proven layers; build the differentiators** (Case Graph,
> Completion Loop, scoring, playbooks). Everything model- or vendor-specific sits behind an
> interface (MCP tool or adapter) so it can be swapped as the frontier moves. Licenses are
> called out because several key tools are AGPL/RAIL and affect the deployment model.

## 1. Stack at a glance

| Layer | Recommendation | Alt / notes | License |
|---|---|---|---|
| Web/dashboard | **Next.js + React + TypeScript** (this repo is an OpenAI+Next.js starter → reuse as the Command Center foundation) | — | MIT |
| Backend API | **Python + FastAPI** (best AI/ML ecosystem) | Node/NestJS if team is JS-only | MIT |
| System of record | **PostgreSQL** | managed (RDS/Cloud SQL/Neon) | OSS |
| Case Graph | **Postgres `graph_edges` + recursive CTEs** at MVP | migrate to **Neo4j** only if deep traversals demand it | — |
| Vector search | **pgvector** (same Postgres) | dedicated (Qdrant/Weaviate) at scale | OSS |
| Object storage | **S3-compatible** (docs/audio/photos), encrypted | MinIO self-host | — |
| Queue/schedule/durable | **Temporal** (durable follow-ups/loops) | Celery+Redis / APScheduler for lighter MVP | MIT/OSS |
| Agent orchestration | **LangGraph** (durable, HITL) + optional **OpenAI Agents SDK** patterns | see §3 | MIT |
| Tooling protocol | **Model Context Protocol (MCP)** for all integrations | — | open spec |
| Voice/real-time | **LiveKit Agents** or **Pipecat** | see `06` | Apache-2.0 / BSD-2 |
| Documents/OCR | **Docling + olmOCR + PaddleOCR-VL + Qwen-VL + Surya** (routed) | see `07` | mixed (MIT/Apache/RAIL) |
| Web research | **Playwright MCP + Firecrawl** (+ browser-use/Skyvern sparingly) | see `08` | Apache/AGPL/MIT |
| LLMs | latest frontier models per worker (reasoning vs. fast) | model-agnostic | — |
| Secrets | dedicated secrets manager (Vault/cloud KMS) | never in DB | — |
| Observability | OpenTelemetry + LangGraph/Agents-SDK tracing + logs/metrics | — | OSS |

## 2. Data layer rationale (relational + graph + vector)

- **PostgreSQL as system of record**: strong consistency, transactions, easy audit — right for
  cases, money, approvals, and an append-only `AuditEvent` log (`04`).
- **Graph in Postgres first**: the "case is a graph" requirement is satisfied by a typed
  `graph_edges` table + recursive CTEs. MVP traversals ("what blocks this quote?", "which
  overdue promises block a close?") are shallow (≤3–4 hops). **Migrate to Neo4j** only if
  traversal depth/complexity/latency becomes a real bottleneck — avoid the operational cost of
  a second datastore prematurely.
- **pgvector for semantic memory**: embeddings over messages, documents, and past cases (Deal
  Memory) live in the same Postgres, simplifying ops. Move to a dedicated vector DB only at
  scale.
- **Event sourcing**: `AuditEvent` is the source of truth; projections (dashboards, scores) are
  rebuildable. This gives reproducibility and the tamper-evident audit trail (`13`).

## 3. Orchestration rationale

- **LangGraph** is recommended for the long-lived case orchestration + Completion Loop because
  it is built for **durable execution** ("saves progress at checkpoints… pause and later
  resume exactly where it left off"), **persistence** (checkpointer + thread id), **streaming**,
  and **human-in-the-loop** (`interrupt`/breakpoints). A case spans days and many events —
  durability is the deciding requirement. Docs:
  https://docs.langchain.com/oss/python/langgraph/durable-execution
- **OpenAI Agents SDK** primitives (**Agents, Handoffs, Guardrails, Sessions, Tracing**;
  "guardrails run in parallel… fail fast"; built-in "human review") are excellent for the
  *within-turn* agent loop and can be used inside individual workers. Docs:
  https://openai.github.io/openai-agents-python/
- **MCP (spec 2025-06-18)** standardizes tools/resources/prompts, so every integration is a
  swappable, testable server and the system isn't locked to one orchestration framework.
  https://modelcontextprotocol.io/specification/2025-06-18
- **Temporal** (or a Postgres-backed durable queue) handles *time-based* durability — a
  follow-up scheduled 72h out must survive restarts even between orchestrator steps.
- **NVIDIA NeMo Agent Toolkit** is noted as a later *profiling/evaluation* infra reference
  (framework-agnostic, supports MCP), not an MVP dependency.
  https://github.com/NVIDIA/NeMo-Agent-Toolkit

## 4. Voice rationale (see `06`)

Cascaded **STT→LLM→TTS** (reasoning quality > last-200ms latency), on **LiveKit Agents**
(Apache-2.0; built-in WebRTC + SIP/PSTN telephony + semantic turn detection) or **Pipecat**
(BSD-2; vendor-neutral pipeline, Silero VAD barge-in). Keep a realtime speech-to-speech adapter
(e.g. OpenAI Realtime, GA Aug 2025) behind the same interface for simple flows. STT/TTS vendors
chosen per language in `VoiceProfile`.

## 5. Documents rationale (see `07`)

Routed multi-engine: **Docling** (MIT; structure/layout) → **PaddleOCR-VL** (0.9B, 109 langs) /
**Surya** (90+ langs) for clean scans → **olmOCR** (Apache-2.0; ~$190/M pages) / **Qwen-VL** for
hard/handwritten. **License watch**: Surya weights are AI-Pubs Open RAIL-M (free under $5M
funding/revenue — confirm as you grow); PaddleOCR-VL **weights license UNVERIFIED** — confirm
before shipping. Self-hosting keeps sensitive docs in-boundary and is far cheaper at volume.

## 6. Web research rationale (see `08`)

**Playwright MCP** (Apache-2.0; accessibility-tree, deterministic) as primary browser control;
**Firecrawl** (AGPL-3.0 self-host / SDKs MIT; robots-respecting markdown extraction) for
read/extract. **browser-use** (MIT) / **Skyvern** (AGPL-3.0) only for genuine multi-step public
lookups. **License watch**: AGPL (Firecrawl/Skyvern) matters if modified and offered as a
network service — prefer their hosted APIs or keep them as unmodified sidecars; confirm with
counsel.

## 7. Frontend rationale

This repo (OpenAI + Next.js 13 starter, React 18, TS, Tailwind, Prisma/Postgres, NextAuth,
Stripe) is a ready **foundation for the Command Center**: auth, billing, Postgres, and docs
scaffolding already exist. Build the dashboard (`11`) with the App Router (RSC + Server
Actions), a component kit (e.g. shadcn/ui), and real-time case updates (websockets/SSE).

## 8. Deployment & environments

- Containerized services (API, workers, voice, orchestrator) on a managed platform (Vercel for
  the Next.js app; a container host/K8s for Python workers + Temporal).
- **Data residency configurable per tenant** (`BusinessProfile.data_region`) for GDPR.
- Secrets in a manager, not env files in the repo. TLS everywhere; the agent proxy/CA in this
  environment is pre-configured.
- Observability: OpenTelemetry traces across workers + orchestrator; per-tenant metric
  dashboards feed the Evaluation Lab (`15`).

## 9. Open build decisions (pick in Phase 0)

1. **Telephony**: LiveKit SIP vs. Twilio (drives voice framework choice).
2. **OCR hosting**: fully self-hosted vs. managed for the heavy VLMs (cost vs. ops).
3. **Graph store**: stay on Postgres graph_edges vs. adopt Neo4j (defer until proven need).
4. **Durable substrate**: Temporal vs. Celery+Redis for MVP (team familiarity vs. guarantees).
5. **Orchestrator**: LangGraph-only vs. LangGraph + Agents-SDK hybrid.
6. **AGPL posture**: hosted APIs vs. self-hosted sidecars for Firecrawl/Skyvern.

Each is recorded as an ADR; defaults above are the recommended starting points.
