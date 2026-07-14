# FINALIS 1000 — RESEARCH REGISTER

**SP0000 · docs-only.** Research executed 2026-07-11 by two independent research passes (SWARM-C1: harness/durable/orchestration/A2A/MCP; SWARM-C2/E/F: observability/evals/Viktor/EU-AI-Act).

> **RETRIEVAL LIMITATION (honest disclosure).** Direct `WebFetch` returned **HTTP 403 Forbidden on every target URL** across all hosts (origin bot-protection on the WebFetch fetcher path). The local egress proxy was verified healthy (`recentRelayFailures: []`) — this is **not** an org-egress denial. All content below was corroborated from **WebSearch result snippets served by the same primary domains** (and, for dates, independent press). Status fields reflect this: `CURRENT (content via search index, not direct render)`. Pages that could not even be corroborated are marked `UNREACHABLE`/`UNCERTAIN` and **must not be cited as evidence**. This limitation is recorded per SP §2.1 ("if the environment limits execution, do not fake it — record the limitation").

Record fields: SOURCE_NAME · FULL_URL · PUBLISHER · DATE · RETRIEVED_AT · CLAIM_SUPPORTED · PRIMARY/SECONDARY · STATUS · ARCHITECTURAL_IMPLICATION.

---

## A. Agent harness / control-plane vs compute-sandbox (PRIMARY: OpenAI)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| 1 | The next evolution of the Agents SDK | https://openai.com/index/the-next-evolution-of-the-agents-sdk/ | 2026-04-15 | CURRENT (via index) | Explicit harness (control plane: loop, tool routing, handoffs, approvals, tracing, recovery, run-state) vs compute (disposable sandbox) boundary; keeps credentials out of model-code environments → **Finalis must own its harness; no vendor sandbox/model holds business/governance authority.** |
| 2 | Sandbox Agents (API guide) | https://developers.openai.com/api/docs/guides/agents/sandboxes | living/2026 | CURRENT (via index) | Compute is pluggable across ~7 providers (Blaxel, Cloudflare, Daytona, E2B, Modal, Runloop, Vercel) + BYO via Manifest → **sandbox is a commodity, replaceable trust domain holding no durable authority/secrets.** |
| 3 | Harness engineering | https://openai.com/index/harness-engineering/ | ~2026-02 (UNCERTAIN) | CURRENT (via index) | Durable value sits in the harness (intent/env/feedback), not the model → **harness is a retained Finalis asset; model is replaceable.** |
| 4 | Unrolling the Codex agent loop | https://openai.com/index/unrolling-the-codex-agent-loop/ | 2026 (UNCERTAIN) | CURRENT (via index) | Tools/MCP/skills run "under a consistent policy model" the harness enforces → **policy authority belongs to the loop owner, not tools/MCP/sandbox.** |
| 5 | Symphony (open-source Codex orchestration) | https://openai.com/index/open-source-codex-orchestration-symphony/ | 2026-04-27 | CURRENT (via index); *minimal/demo spec* | Workflow/control plane kept OUTSIDE the model (board + documented workflow + human review) → **orchestration authority + approval gates externalized from model/sandbox.** |

## B. Durable execution (PRIMARY: Temporal — capability, not mandated dependency)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| 6 | Durable Agent w/ OpenAI Agents SDK | https://docs.temporal.io/ai-cookbook/openai-agents-sdk-python | living/2026 | CURRENT (via index); *integration = public preview* | Agent orchestration as Workflow, each LLM call an Activity; auto-persist + resume after crash → **durability is an orchestration wrapper layered on top → replaceable without touching business logic.** |
| 7 | Human-in-the-Loop AI Agent | https://docs.temporal.io/ai-cookbook/human-in-the-loop-python | living/2026 | CURRENT (via index) | Workflow can pause for human input seconds→years at zero compute, then resume deterministically → **model governance approvals + long human delays as first-class durable wait-states.** |
| 8 | Why Temporal | https://docs.temporal.io/evaluate/why-temporal | living/2026 | CURRENT (via adjacent index) | Durable Execution = exactly-resume via Event History; replaces hand-written state-machine/retry → **generic capability, NOT proprietary lock-in; Temporal = one interchangeable provider.** |
| 9 | Temporal Integrations | https://docs.temporal.io/integrations | — | **UNREACHABLE** (403; no corroborating snippet) | UNVERIFIED — **must not be cited as evidence.** |

**Lock (D-0000-07, OQ-01):** durable-execution capability REQUIRED; engine REPLACEABLE; no permanent Temporal dependency (TDR = SP0004).

## C. Multi-agent orchestration (PRIMARY: Google ADK)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| 10 | Why we built ADK 2.0 | https://developers.googleblog.com/why-we-built-adk-20/ | ~2026-06 (UNCERTAIN) | CURRENT (via index) | "Where B always follows A, use determinism, not an LLM"; Workflows (Sequential/Parallel/Loop) beside LLM routing → **deterministic orchestration governs; LLM confined to bounded adaptive steps.** |
| 11 | ADK 2.0 docs root | https://google.github.io/adk-docs/2.0/ | — | **UNCERTAIN** (path unconfirmed; 403) | The version-pinned path may not resolve — **cite the docs root, not this URL.** |
| 12 | Multi-agent systems | https://google.github.io/adk-docs/agents/multi-agents/ | 2026 | CURRENT (via index) | One coordinating structure over many specialists → **"one employee identity, many internal specialists"; coordinator holds authority.** |
| 13 | Workflow agents | https://google.github.io/adk-docs/agents/workflow-agents/ | 2026 | CURRENT (via index) | Sequential/Parallel/Loop are deterministic orchestrators separable from model reasoning → **control flow is code-owned + provider-neutral.** |
| 14 | Sequential agents | https://google.github.io/adk-docs/agents/workflow-agents/sequential-agents/ | 2026 | CURRENT (via index) | Fixed strict order → **governance-critical ordering (validate-before-act) guaranteed by structure, not model discretion.** |
| 15 | Parallel agents | https://google.github.io/adk-docs/agents/workflow-agents/parallel-agents/ | 2026 | CURRENT (via index) | Concurrent independent sub-agents → **parallelism ≠ distributed authority; results funnel to one controller.** |

*(Corroborating, off-list: "Announcing ADK Go 2.0" https://developers.googleblog.com/announcing-adk-go-20/ — graph workflows + built-in HITL primitive, ~late June 2026.)*

## D. A2A protocol v1.0 (interoperability boundary, NOT internal authority)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| 16 | A2A home | https://a2a-protocol.org/latest/ | living | CURRENT (via index) | Open standard for cross-org agent discovery/communication/delegation; LF-governed (AWS/Cisco/Google/IBM/Microsoft/Salesforce/SAP/ServiceNow TSC) → **cross-org edge boundary, not internal authority.** |
| 17 | Announcing v1.0 | https://a2a-protocol.org/latest/announcing-1.0/ | early 2026 (UNCERTAIN) | CURRENT (via index) | First stable/production release; breaking changes; AgentCard advertises v0.3+v1.0; multi-tenancy + modernized security → **ratified standard safe as an edge; version-negotiate, don't pin internal design.** |
| 18 | Specification | https://a2a-protocol.org/latest/specification/ | v1.0.0 line | CURRENT for `/v1.0.0/` (via index); *`/dev/` = DRAFT — do not conflate* | JSON-RPC/gRPC/REST bindings w/ equivalence; JWS-signed (RFC 7515) JCS (RFC 8785) Agent Cards; mTLS/OAuth 2.0 Device Code/PKCE → **cryptographically-verifiable trust boundary; inbound A2A = external claim to authenticate + authorize.** |
| 19 | What's New in v1.0 | https://a2a-protocol.org/latest/whats-new-v1/ | early 2026 | CURRENT (via index) | Breaking: enum SCREAMING_SNAKE_CASE, camelCase, ISO-8601 ms; signed cards; per-interface versioning; gRPC tenant scoping → **implement A2A behind a versioned edge adapter; never bake wire formats into internal state.** |
| 20 | A2A SDK | https://a2a-protocol.org/latest/sdk/ | 2026 | CURRENT (via index) | Official SDKs in Python/Go/JS/Java/.NET/Rust → **edge implementable in Finalis's own stack; vendor-neutral.** |

## E. MCP (tool/context adapter; output = data, not authority)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| 21 | MCP home | https://modelcontextprotocol.io/ | ratified spec = **2025-11** | CURRENT (via index) | Standardizes tools/context to LLMs; servers expose tools/resources under host policy; official registry exists → **MCP servers are external trust domains; outputs are data to validate, never authority.** |
| 22 | MCP Roadmap | https://modelcontextprotocol.io/development/roadmap | 2026 | CURRENT (via index); *roadmap = intentions* | Prioritizes transport scale, agent comms, governance maturation, enterprise readiness (no fixed dates) → **governance still maturing → Finalis supplies its own governance now; do not assume MCP provides it.** |
| 23 | The 2026 MCP Roadmap (blog) | https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/ | 2026 | CURRENT as roadmap; **2026-07-28 revision = RELEASE CANDIDATE, not final at retrieval** | Announces RC (stateless HTTP core, MCP Apps UIs, Tasks extension, OAuth/OIDC auth) → **build against ratified 2025-11 spec; treat 07-28 features as forthcoming; unratified features must not be load-bearing for authority.** |

## F. Observability (PRIMARY: OpenTelemetry — vendor-neutral, privacy-first)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| A1 | GenAI Observability with OTel | https://opentelemetry.io/blog/2026/genai-observability/ | 2026 (semconv v1.41) | CURRENT (via index) | Vendor-neutral GenAI semconv: model, input/output tokens, finish reasons, agent/workflow/tool/model spans + latency/token metrics → **adopt OTel GenAI semconv as native telemetry contract; emit once, route anywhere.** |
| A2 | Semantic conventions (semconv) | https://opentelemetry.io/docs/specs/semconv/ | GenAI conv = experimental; OTel graduated CNCF 2026-05-21 | CURRENT (GenAI = experimental) | Content capture is **OPT-IN, OFF BY DEFAULT** (SHOULD NOT capture message content by default; NO_CONTENT default); sensitive attrs carry PII warnings → **default metadata-only; content capture is an explicit switch; isolate emission behind an adapter (conventions still experimental).** |

## G. Continuous improvement / gated learning (PRIMARY: OpenAI)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| B1 | Agent Improvement Loop | https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop | 2026 | CURRENT (via index) | traces → evals+feedback → failure modes → candidate change → **regression eval gate + human diff approval** → gated promotion; every failure encoded as a permanent eval → **improvement is a GATE, not self-mutation; no trace→live path skips the eval gate.** |
| B2 | Self-improving tax agents w/ Codex | https://openai.com/index/building-self-improving-tax-agents-with-codex/ | 2026 | CURRENT (via index); *metrics vendor-reported/UNVERIFIED* | Corrections become tasks only after review+grouping into bounded findings; only bounded high-confidence eval-passing changes auto-apply, else route to humans → **raw feedback is evidence, not instruction.** |
| B3 | Eval skills | https://developers.openai.com/blog/eval-skills | 2026 | **UNCERTAIN** (exact page not independently indexed; theme corroborated by B1) | Evals as durable versioned assets; LLM-as-judge for dev-phase feedback → **evals = first-class versioned assets = institutional memory + promotion gate.** |

## H. Competitor reference — ViktorAI (ALL records = VENDOR CLAIMS, not independent evidence)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| C1 | Viktor home ("a hire, not a tool") | https://viktor.com/ | launch Feb 2026 | CURRENT (marketing) | AI employee in Slack/Teams w/ own cloud computer, "real work" → **LEARN the one-employee metaphor + analyze→decide→act framing; do NOT make the persistent cloud computer the architectural core.** |
| C2 | Product | https://viktor.com/product | 2026 | CURRENT; *integration count = fluctuating marketing (3,000+/3,200+ inconsistent)* | Persistent compute, 3k+ integrations, workspace memory, proactivity → **LEARN real execution + persistent context; do NOT make integration COUNT the moat.** |
| C3 | Brand | https://viktor.com/brand | 2026 | **UNCERTAIN** (page not independently indexed) | Provider-specific single persona → **do NOT hard-couple core to a branded persona/single model; keep persona + model pluggable.** |
| C4 | What is an AI coworker | https://viktor.com/blog/what-is-an-ai-coworker | 2026 | CURRENT (sibling `/what-is-an-ai-employee` confirmed; exact slug UNVERIFIED) | "logs into tools, does real work, no per-step scripting" → **LEARN the act-not-answer altitude; pair with governance the vendor framing omits.** |
| C5 | Viktor vs Claude in Slack | https://viktor.com/blog/viktor-vs-claude-in-slack | 2026 | CURRENT as marketing; *claims about Claude UNVERIFIED + self-serving* | Positions execution gap ("answer that doesn't become completed work") → **LEARN the diagnosis; do NOT accept competitor characterization as fact.** |

## I. EU AI regulatory architecture (NOT legal advice; architecture must SUPPORT future compliance)

| # | Source | URL | Date | Status | Claim → Implication |
|---|---|---|---|---|---|
| D1 | Regulatory framework on AI | https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | living/2026 | CURRENT (via index) | Risk-tiered (prohibited/high-risk/limited/minimal); employment/HR = high-risk w/ risk-mgmt, documentation, human oversight, monitoring, transparency → **risk tier is a modeled property of each capability, not a compliance afterthought.** |
| D2 | High-risk guidelines (draft) | https://digital-strategy.ec.europa.eu/en/policies/guidelines-ai-high-risk-systems | draft 2026-05-19; consultation to 2026-07-23 | CURRENT but **DRAFT/NON-BINDING** | "Intended purpose" (incl. marketing materials) drives classification; employment scope broad (recruitment/terms/promotion/termination/task-allocation/monitoring; incl. freelancers/platform workers) → **govern product positioning + capability catalog together; the product can pull itself into high-risk by its own marketing.** |
| D3 | Regulation (EU) 2024/1689 (AI Act) OJ | https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng | OJ 2024-07-12; in force 2024-08-01; phase-in dates **UNVERIFIED** | CURRENT (in force); dates UNCERTAIN | Art. 6(2)+Annex III high-risk incl. employment; **Art. 14 effective human oversight** (detect/correct errors incl. discriminatory patterns; no fully-automated final placement/rejection) → **Article-14 human oversight is a HARD structural constraint: a control point to intervene/override/stop, not a bolt-on checkbox.** Exact phase-in dates (secondary sources cite both 2026-08-02 and 2027-12-02) **must be re-verified against OJ before any compliance-timeline commitment.** |

---

## Consolidated architectural implications (locked into the master)

1. **Harness/compute split** → Finalis owns its harness (authority, policy, secrets, run-state); sandbox/model/provider are commodity, replaceable, authority-free (D-0000-06/07, INV-0000-02, Layer 1/8).
2. **Durable execution = capability, engine replaceable** → no permanent Temporal lock (D-0000-07, OQ-01); approvals + human delays as durable wait-states (Layer 1).
3. **Deterministic orchestration governs; LLM confined to bounded adaptive steps** → "one employee identity, many internal specialists; no agent democracy" (D-0000-02, INV-0000-06, Layer 4).
4. **A2A = external interoperability edge, cryptographically verified, never internal authority** (D-0000-12, INV-0000-03, Layer 8); pin ratified `/v1.0.0/` behind a versioned adapter.
5. **MCP = adapter; output is data not authority; servers are external trust domains** → Finalis supplies its own governance now; build to ratified 2025-11 spec, treat 07-28 RC as forthcoming (INV-0000-03, Layer 8).
6. **Observability = OpenTelemetry GenAI semconv, vendor-neutral, no default content capture** (Master §12, privacy-aware).
7. **Learning = gated** (traces → candidate → eval-gate + human approval → promotion); raw feedback is evidence not instruction; evals are versioned assets (D-0000-09, INV-0000-08, Layer 6).
8. **Viktor is a reference, not an authority** → learn the employee metaphor + real execution; do not copy persistent-computer-as-core or integration-count-as-moat; keep persona/model pluggable (D-0000-01/06).
9. **Regulatory risk classification lives in the architecture** with structural Article-14 human oversight; intended purpose (incl. marketing) drives high-risk classification (Master §13, SP0005).

## Source-handling rules honored
Vendor self-claims (OpenAI/Google/Temporal/Viktor) labeled PRIMARY-as-vendor, not independent evidence. Roadmap items (MCP 2026 priorities, A2A future) not treated as shipped. Release candidates (MCP 2026-07-28) and previews (Temporal×OpenAI SDK) not treated as stable standards. Draft guidance (EU high-risk guidelines) marked non-binding. Unverifiable exact URLs (#9, #11, B3, C3) explicitly excluded from evidentiary use.
