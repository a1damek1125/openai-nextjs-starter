# Finalis AI — Multi-Agent Architecture

> Core stance: **not one big agent — a supervised team of narrow workers over a durable case
> process.** This is a deliberate reaction to the evidence that general autonomy is still
> unreliable on long, realistic business tasks (see benchmarks below). Finalis wins by
> constraining scope, encoding the process explicitly, and keeping a human in the loop at the
> right moments — not by hoping a single model "does everything."

## 0. Why narrow + supervised (evidence)

- **TheAgentCompany (CMU et al., arXiv:2412.14161)**: in a simulated software company, the
  best agent at publication completed **~24% of 175 consequential tasks fully autonomously**
  (Claude 3.5 Sonnet; ~34.4% with partial credit); 2025–26 re-runs put the best closed models
  at **~30% full / ~40% partial**. Takeaway: **do not sell "AI does the whole job
  unattended."** Source: https://arxiv.org/abs/2412.14161 *(numbers via search snippets of the
  paper/leaderboard; treat as high-confidence paraphrase).*
- **OSWorld (arXiv:2404.07972)**: on 369 real computer tasks, **humans ≈72.4%** vs. **best
  model at publication ≈12.2%**. By 2026, single-app OSWorld-Verified SOTA reached **~72%**
  (nominal human parity) — but that does **not** transfer to real office work:
  - **WindowsWorld (ACL 2026, arXiv:2604.27776)**: professional **cross-application** Windows
    workflows (181 tasks, 17 apps) — all computer-use agents **<21%**.
  - **OSWorld 2.0 (arXiv:2606.29537)**: **long-horizon** workflows (~1.6h human time, ~318
    tool calls median) — best system **~20.6% end-to-end** (54.8% partial) at a 500-step
    budget.
  - **OSUniverse (arXiv:2505.03570)**: calibrated so SOTA agents score **<50%** on tasks an
    average white-collar worker completes with ~perfect accuracy.
  *(2026 figures via search snippets; re-verify at the leaderboards before quoting.)*

The pattern is consistent: agents are near-human on short single-app tasks but complete only
**~20–40% of cross-application, long-horizon business work unsupervised** — and partial-credit
scores (34–55%) show real per-step competence. That is exactly Finalis's regime (multi-day,
multi-channel, multi-tool cases), and it dictates the design: **explicit state machine + typed
narrow workers + autonomy levels + human review at task boundaries**, letting the AI execute
the routine sub-steps it is demonstrably good at while humans approve/repair at the joints —
rather than open-ended autonomy.

---

## 1. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Channels:  Phone(SIP)  WhatsApp  SMS  Email  Web form  Web chat       │
└───────────────┬──────────────────────────────────────────────────────┘
                │ inbound events / media
┌───────────────▼──────────────────────────────────────────────────────┐
│  ORCHESTRATOR (durable, stateful)                                      │
│  • owns the Case state machine (03) + Completion Loop (09)             │
│  • routes events to workers, enforces autonomy levels (13)             │
│  • recomputes scores (05) on every event + nightly stuck sweep         │
│  • persists AuditEvents; raises HumanApproval when gated               │
└───┬───────┬───────┬────────┬────────┬────────┬────────┬────────┬──────┘
    │       │       │        │        │        │        │        │
 ┌──▼─┐ ┌───▼──┐ ┌──▼───┐ ┌──▼────┐ ┌─▼─────┐ ┌▼──────┐ ┌▼─────┐ ┌▼──────┐
 │Voice│ │Intake│ │Doc   │ │WebScout│ │Offer │ │Follow │ │Decision│ │Quality│
 │Worker│ │Worker│ │Intel │ │Worker │ │Compar│ │-up    │ │Worker  │ │/Eval  │
 └─────┘ └──────┘ └──────┘ └───────┘ └──────┘ └───────┘ └───────┘ └───────┘
                    (+ Promise Tracker, Missing-Info Hunter, Objection
                     Handler, Quote Builder as loop-invoked skills/tools)
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  STATE & MEMORY:  Postgres (system of record) · graph_edges (Case      │
│  Graph) · pgvector (semantic/Deal Memory) · S3 (media) · secrets mgr   │
└───────────────────────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  HUMAN SURFACE:  Case Command Center (11) — approvals, tasks, briefs   │
└───────────────────────────────────────────────────────────────────────┘
```

## 2. The Orchestrator

Responsibilities: case-type recognition, worker selection, state management, next-step
control, escalation, and — above all — **guaranteeing every active case has a next action**.

**Implementation choice (see `18-tech-stack.md` for full trade-off):**
- **LangGraph** is the recommended orchestration substrate because it is explicitly built for
  **durable execution** (checkpoints so a workflow "can pause and later resume exactly where
  it left off"), **streaming**, **persistence** (checkpointer + thread id), and
  **human-in-the-loop** via `interrupt`/breakpoints. A case runs for days across many events —
  durable, resumable execution is exactly the requirement.
  Docs: https://docs.langchain.com/oss/python/langgraph/overview ,
  https://docs.langchain.com/oss/python/langgraph/durable-execution
- **OpenAI Agents SDK** is a strong alternative / complement for the *within-turn* agent loop:
  its primitives are **Agents, Handoffs, Guardrails, Sessions, Tracing**, with built-in
  guardrails ("run input validation and safety checks in parallel… fail fast") and a
  "Guardrails and human review" flow. Docs:
  https://openai.github.io/openai-agents-python/ ,
  https://developers.openai.com/api/docs/guides/agents
- **Recommendation**: use **LangGraph for the long-lived case orchestration + Completion Loop**
  (durability is the deciding factor) and optionally the **Agents-SDK handoff/guardrail
  pattern inside** individual worker turns. Both are compatible with **MCP** for tools.
- For durability of *scheduled* work (follow-ups days out, promise deadlines), pair the
  orchestrator with a durable job runner (**Temporal** or a Postgres-backed queue; Celery/Redis
  for the lighter MVP). See tech stack.

## 3. Tooling via Model Context Protocol (MCP)

All external capabilities (calendar, email, WhatsApp, telephony, browser, OCR services,
CRM) are exposed to workers as **MCP tools/resources/prompts**. MCP is an open protocol that
standardizes how LLM apps integrate external tools and data. Current **stable spec:
2025-11-25** (adds experimental **async tasks** for durable long-running requests, OIDC
discovery + Client-ID-Metadata-Document auth, richer elicitation enums, tool-calling in
sampling — all backward compatible with 2025-06-18; a 2026-07-28 RC is in flight).
Spec: https://modelcontextprotocol.io/specification/2025-11-25 (changelog verified from the
MCP GitHub repo). Async tasks are directly relevant to Finalis's long-running document/web
jobs.

Using MCP means each integration is a swappable server with a typed contract, testable in
isolation, and reusable across workers — and it future-proofs against orchestration-framework
churn.

## 4. The workers (specialists)

Each worker is a narrow agent (LLM + tools + instructions) with a **defined contract**:
inputs from the Case Graph, allowed tools, structured outputs, confidence, and evidence refs.
Workers never mutate case state directly — they return proposals; the Orchestrator applies
transitions under autonomy rules and writes audits.

| Worker | Job | Key inputs | Key outputs | Detail doc |
|---|---|---|---|---|
| **Voice Worker** | Real-time phone conversation | audio stream, case context | transcript, promises, missing items, next actions, handoff signal | `06` |
| **Intake Worker** | Qualify + collect structured info | playbook, conversation | filled fields, `LeadScore` inputs, `MissingItem`s | `01`,`03` |
| **Document Intelligence Worker** | OCR + field extraction + risk | documents/photos | `ExtractedField`+confidence, `DocRisk`, evidence refs | `07` |
| **WebScout Worker** | Ethical public web research | query, case facts | source-backed facts w/ trust score | `08` |
| **Offer Comparator** | Compare offers | offers, playbook weights | `Comparison`, `OfferScore`, hidden-risk flags | `10` |
| **Follow-up Worker** | Cadence, channel, timing | `FollowUpSequence`, scores | scheduled/sent `Action`s | `09` |
| **Decision Worker** | Owner-facing brief | full case | `DecisionBrief` + recommendation | `01`,`11` |
| **Quality/Eval Worker** | Completeness/consistency check | any worker output | pass/fail + gaps, hallucination flags | `15` |

**Cross-cutting skills** (invoked by the loop, not standalone agents): **Promise Tracker**,
**Missing-Information Hunter**, **Objection Handler**, **Quote Builder** — each is a
tool/skill callable by the Orchestrator or a worker.

### The Quality Worker (a deliberate check)
A dedicated verifier runs after high-stakes worker outputs (document analysis, offer
comparison, decision briefs): "is every claim evidence-linked? is confidence honest? is
anything missing?" This is the internal analogue of adversarial verification and directly
targets the hallucination-rate metric (`15-evaluation-lab.md`). It mirrors the "secondary LLM
critic" defense pattern recommended for agentic systems.

## 5. Orchestration patterns

- **Router**: on each inbound event, classify → route to the owning worker for the current
  state. (Agents-SDK "handoffs" or LangGraph conditional edges.)
- **Loop**: nightly + event-driven Completion Loop recomputes scores and enqueues the NBA.
- **Human-in-the-loop interrupt**: crossing `θ_escalate` or hitting a hard rule pauses
  autonomous action and emits a `HumanApproval` (LangGraph `interrupt`; Agents-SDK guardrail +
  human review).
- **Guardrails**: input/output validators run in parallel to workers (PII checks, scope
  checks, price-rule checks, injection filters for WebScout) and can fail-fast a proposal.

## 6. Reference-only / not adopted at MVP

- **NVIDIA NeMo Agent Toolkit** — framework-agnostic library to connect/profile/evaluate
  teams of agents (works across LangChain/CrewAI/etc., supports MCP + A2A). *Infrastructure
  reference* for later profiling/optimization; not an MVP dependency.
  https://github.com/NVIDIA/NeMo-Agent-Toolkit
- **Claude Code (skills/subagents/hooks)** — informs our *authoring model* for playbooks
  (skills = markdown instructions loaded on demand; subagents = isolated context; hooks =
  deterministic lifecycle control). Useful as an internal dev-productivity and
  playbook-authoring pattern. https://code.claude.com/docs/en/skills
- General GUI-automation autonomy is intentionally minimized given OSWorld results; WebScout
  uses **structured, accessibility-tree browser control** (Playwright MCP) rather than
  open-ended pixel GUI agents (see `08`).

## 7. Failure & degradation behavior

- If a worker times out or returns low confidence → the Orchestrator does **not** guess; it
  either requests more info (client/human) or escalates. "Prefer asking over assuming."
- If the LLM/model provider degrades → cascaded voice falls back to shorter scripted turns +
  human handoff; document analysis queues for retry; scores are computed from last-known
  inputs and flagged stale.
- Every degradation is an `AuditEvent`; SLAs surface in the Command Center.

---

**Model choice note**: Default to the latest, most capable models for reasoning-heavy workers
(decision briefs, document/offer analysis, objection handling) and faster/cheaper models for
high-volume, low-stakes steps (classification, routing, short voice turns). The architecture
is model-agnostic via MCP + the orchestrator, so models can be swapped per worker as the
frontier moves.
