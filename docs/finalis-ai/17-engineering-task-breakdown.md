# Finalis AI — Engineering Task Breakdown & Backlog

> This is the developer-facing backlog. It decomposes the architecture (`02`), state machine
> (`03`), data model (`04`), scoring (`05`), voice (`06`), and completion loop (`09`) into
> concrete, sizeable engineering tasks. Nothing here invents new entities, states, or scores —
> every item traces back to those documents.
>
> **Sizing legend**: `S` ≈ ≤2 dev-days · `M` ≈ 3–5 dev-days · `L` ≈ 1–2+ dev-weeks (usually
> split before starting).
>
> **Repo note**: this repository is an **OpenAI + Next.js starter kit**. It is the foundation
> for the **web/dashboard frontend** (the Case Command Center, Epic K) and can host thin
> Next.js API/BFF routes and server actions. The **orchestrator, workers, and scoring layer**
> are a separate Python service (LangGraph + durable scheduler per `02`/`09`), reached from
> Next.js over an internal API. Treat "the app" as two deployables: `web` (this repo) and
> `core` (agents/orchestrator).

---

## 0. Epic map

| ID | Epic (module) | Primary source docs | Deployable |
|---|---|---|---|
| A | Platform / Infrastructure | `02`, `04` | both |
| B | Data Layer & Case Graph | `04` | core |
| C | Orchestrator & Completion Loop | `02`, `03`, `09` | core |
| D | Voice Worker | `06` | core |
| E | Intake Worker | `03`, `05` | core |
| F | Document Intelligence Worker | `04`, `05`, `07` | core |
| G | WebScout Worker | `02`, `05`, `08` | core |
| H | Offer Comparator | `05`, `09` | core |
| I | Follow-up / Promise / Missing-Info | `05`, `09` | core |
| J | Decision Worker | `09`, `05` | core |
| K | Command Center UI (Next.js) | `04`, `09` (this repo) | web |
| L | Integrations (MCP) | `02`, `04` | core |
| M | Autonomy / Guardrails / Audit | `03`, `05` | core |
| N | Evaluation Lab | `05`, `06` | core |
| X | Cross-cutting (multi-tenancy, secrets, observability, CI/CD, testing) | all | both |

---

## Epic A — Platform / Infrastructure

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| A1 | Provision managed **PostgreSQL** (+ `pgvector` extension) per `04` | DB reachable from `core`; `pgvector` enabled; migrations run in CI | M |
| A2 | Provision **S3-compatible object store** for media (`Call.recording_url`, `Document.storage_url`, `Photo.storage_url`) | Signed-URL upload/download works; bucket encryption on | S |
| A3 | Stand up **secrets manager** (Vault/cloud KMS) — `IntegrationAccount.credentials_ref` resolves a handle, never a raw secret | No token/secret exists in DB; app reads secrets only via handle | M |
| A4 | Choose + provision **durable scheduler** substrate (Temporal, or Postgres-backed queue/APScheduler for MVP per `09`) | A job scheduled 72h out survives a service restart | M |
| A5 | Base **core service skeleton** (Python, LangGraph) with health, config, DB pool | `/healthz` green; loads `BusinessProfile` thresholds at boot | S |
| A6 | **Next.js `web` app** baseline on this starter (auth shell, API/BFF layer to `core`) | Authenticated user reaches an empty Command Center calling `core` | M |
| A7 | Environments: dev / staging / prod with per-env config + `data_region` awareness (`BusinessProfile.data_region`) | Tenant data can be pinned to a region; config differs per env | M |
| A8 | Container/build images for `web` and `core`; IaC skeleton | `docker compose up` runs web + core + db + scheduler locally | M |

---

## Epic B — Data Layer & Case Graph

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| B1 | Migrations for **tenant root + config**: `BusinessProfile`, `IndustryPlaybook`, `VoiceProfile`, `UserRole` | Tables created; `thresholds`/`scoring_weights`/`offer_weights` JSON present | M |
| B2 | Migrations for **core case entities**: `Case`, `Party`, `CasePartyRole`, `Conversation`, `Message`, `Call` | All fields + indexes from `04` exist; `Case.status` enum matches `03` exactly | L |
| B3 | Migrations for **evidence + media**: `Document`, `ExtractedField`, `EvidenceReference`, `Photo` | Polymorphic `EvidenceReference` resolves to message/call/doc/source | M |
| B4 | Migrations for **commercial + workflow**: `Offer`, `Comparison`, `Promise`, `MissingItem`, `Action`, `Task`, `FollowUpSequence`, `DecisionBrief`, `RiskFlag`, `HumanApproval` | Each table matches `04` fields/indexes; FKs enforced | L |
| B5 | **`AuditEvent`** append-only table with `hash_prev` tamper-evidence chain | Insert-only enforced; chain verifiable; every write carries `payload`+`evidence_ref_ids` | M |
| B6 | **`graph_edges`** typed edge table + polymorphic node refs | Insert edges of all listed `edge_type`s; `(tenant_id, from_node/to_node/edge_type)` indexed | M |
| B7 | **Recursive-CTE traversals**: "what blocks this quote?", "overdue promises blocking a close?" | Query returns correct blocker set for a seeded case within latency budget | M |
| B8 | **pgvector** columns + indexes on `Message`, `Document`, `Photo`, `Party.deal_memory_embedding` | k-NN "similar past cases / Deal Memory" query returns ranked results | M |
| B9 | **`IntegrationAccount`** table storing only a secrets handle | Row has `credentials_ref` handle; no raw token column | S |
| B10 | **Repository/data-access layer** with mandatory `tenant_id` filter on every query | Query without tenant scope fails a lint/guard test | M |
| B11 | **Event-sourcing projections**: rebuild derived case fields from `AuditEvent` | Dropping + replaying audit reconstructs `Case` scores/state | L |

---

## Epic C — Orchestrator & Completion Loop

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| C1 | **State machine engine** implementing all 17 states + transition table (`03` §4) | Illegal transition is rejected; legal one succeeds; enum 1:1 with `03` | L |
| C2 | **Global invariants** enforcement (`03` §2): active case has non-null `next_best_action` + `due_at`; transition writes `AuditEvent{from,to,actor,reason,evidence_refs}` | Attempt to leave an active case without a next action fails loudly | M |
| C3 | **Global interrupt edge**: any active state → `HUMAN_REVIEW_REQUIRED` when `EscalationScore ≥ θ_escalate` or a hard rule fires | Seeded high-escalation event forces review state and freezes outbound | M |
| C4 | **Durable case runtime** on LangGraph (checkpoint/resume) bound to a `Case` thread id | Kill + restart mid-case resumes at the last checkpoint | L |
| C5 | **Event router** (`02` §5): classify inbound event → route to owning worker for current state | Inbound WhatsApp/call/doc routed to correct worker per state | M |
| C6 | **Worker contract runtime**: workers return *proposals* only; orchestrator applies transitions under autonomy + writes audits (`02` §4) | A worker cannot mutate case state directly (enforced by interface) | M |
| C7 | **Event-driven loop trigger** (`09` §1): any inbound message/call/document/webhook re-runs scoring + NBA immediately | New message recomputes scores and enqueues an action | M |
| C8 | **Nightly stuck sweep** (`03` §5, `09` §1): iterate active cases, recompute `LeadScore`,`MIS`,`StuckScore`,`PromiseBreachScore`,`EscalationScore`; check invariant; enqueue NBA; park exhausted → `RECOVERY_LATER`; wake due `RECOVERY_LATER` | Sweep run on seeded data produces expected transitions + queued actions | L |
| C9 | **NBA selection integration** (`05` §3): choose `a* = argmax Utility`; if above autonomy → emit `HumanApproval` else execute + audit | `a*` persisted to `Case.next_best_action`; runner-ups stored in `Action.chosen_over` | M |
| C10 | **Score persistence** to `AuditEvent` with input vector + weight-set version (`05` §12) | Every score write is reproducible from stored inputs + weight version | S |
| C11 | **Failure/degradation behavior** (`02` §7): worker timeout/low-confidence → request info or escalate, never guess; every degradation is an `AuditEvent` | Simulated worker timeout escalates or asks, and audits the degradation | M |
| C12 | **Opt-out / STOP hard rule** (`03` §2.6): forces `ABANDONED`/`LOST` and permanently suppresses outbound | After STOP, no outbound action can be scheduled for that party | S |

---

## Epic D — Voice Worker

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| D1 | Select + integrate real-time media framework (**LiveKit Agents** or **Pipecat**) with SIP/PSTN (`06` §1) | Inbound PSTN call reaches the agent as a media session | L |
| D2 | **Cascaded streaming pipeline** STT → LLM → TTS with token/sentence-chunked TTS start (`06` §2) | Agent begins speaking on first sentence; interim STT streamed | L |
| D3 | **Barge-in** via VAD: stop TTS ≤200 ms after speech onset; log `Call.barge_in_events` | Interrupting the agent stops speech within target; event recorded | M |
| D4 | **Semantic end-of-utterance / turn detection** (not fixed VAD timeout) (`06` §4) | Mid-thought pause does not trigger premature response | M |
| D5 | **Context prefetch**: load `BusinessProfile`, playbook, calendar, price rules, case state into turn context (`06` §2) | Tool calls resolve without cold DB hit mid-utterance | M |
| D6 | **Latency instrumentation + targets** (`06` §3): TTFA P50 ≤800 ms, P95 ≤1500 ms; store `Call.latency_metrics` | Dashboards show ttfa_p50/p95; fallback triggers on breach | M |
| D7 | **Fallback-when-slow**: holding phrase on soft deadline; human handoff/callback on hard deadline | Injected latency produces a filler phrase then answer | S |
| D8 | **Repair + slot confirmation** for critical slots (address/date/price) (`06` §4) | ASR-ambiguous number triggers a targeted repair question | M |
| D9 | **Language switching** per utterance; store `Call.languages`; drive `VoiceProfile` STT/TTS | Mid-call language switch responds in client's language | M |
| D10 | **Warm human handoff** on `EscalationScore ≥ θ_escalate`, explicit request, anger, safety emergency (with safety script) | Gas-leak keyword triggers safety script + handoff with live summary | M |
| D11 | **Post-call processing** (`06` §5): summary, `Promise` rows, `MissingItem` rows, next-action proposals, `ExtractedField` updates, sentiment timeline — all with transcript-timestamp evidence refs | After a test call, all six artifacts persist with evidence refs | L |
| D12 | **Recording consent gating** per `VoiceProfile.consent_prompt` + `BusinessProfile.recording_consent_config`; audio retention default 90d | Recording suppressed where consent config forbids it | S |

---

## Epic E — Intake Worker

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| E1 | **Intent + intake classifier** driving `NEW_CONTACT → INTAKE_IN_PROGRESS` (`03` §3.1–3.2) | Serviceable request advances; spam/wrong-number → `ABANDONED` | M |
| E2 | **Playbook-driven intake**: instantiate `MissingItem` rows from `IndustryPlaybook.required_fields` | Case gets checklist rows with `weight` + `blocks_quote` from playbook | M |
| E3 | **Structured slot filling** (name, address, problem, urgency, scope, timing, budget band, "already have another quote?") → case fields / `ExtractedField` | Intake conversation fills structured fields with confidence | M |
| E4 | **Over-asking guard**: one consolidated ask, respect `AnnoyanceRisk`; no assuming unstated facts | Worker never asks field-by-field; declines to guess missing values | S |
| E5 | **Returning-client identification** via Deal Memory embedding (`03` §3.1) | Known party matched; context loaded into case | M |
| E6 | Emit **`LeadScore` + `MIS` inputs** to scoring layer at intake (`03` §3.2) | Initial `LeadScore`/`MIS` computed and stored on the case | S |

---

## Epic F — Document Intelligence Worker

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| F1 | **Ingestion + quality pre-check** on arrival (`03` §3.5): compute `Document.ocr_quality`; request re-scan if it fails the gate | Blurry scan → `needs_rescan` + polite re-scan request; never silent | M |
| F2 | **OCR + layout** producing `Document.ocr_text` + `layout_json` (reading order, tables, regions) | Multi-page PDF yields text + region map | L |
| F3 | **Schema-constrained field extraction** → `ExtractedField` with `page`/`bbox` + `EvidenceReference` | Each extracted field links to a document region | L |
| F4 | **`DocRisk` computation** (`05` §5) — implement as discrete scoring task (see Epic — Scoring) | Contract with one-sided terms scores high `A`; ≥θ_docrisk → review | — (see S-DOCRISK) |
| F5 | **RiskFlag generation** with category + severity + evidence ref (`04` `RiskFlag`) | Detected auto-renewal clause creates a `clause` RiskFlag with evidence | M |
| F6 | **Contradiction detection** vs. prior agreements / other docs / call transcript (feeds `DocRisk.C` and state `DOCUMENT_ANALYSIS`) | Price contradicting a prior offer is flagged with both evidence refs | M |
| F7 | **Human-language summary** separating *what we found* from *what we couldn't verify*; never legal advice (`05` §5) | Summary lists unverified items explicitly; disclaimer present | S |
| F8 | State wiring: `WAITING_FOR_DOCUMENTS → DOCUMENT_ANALYSIS` on pass; high `DocRisk`/legal → `HUMAN_REVIEW_REQUIRED` | Transitions fire per `03` §3.5–3.6 | S |

---

## Epic G — WebScout Worker

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| G1 | **Structured accessibility-tree browser control** (Playwright MCP), not pixel GUI agent (`02` §6, `08`) | Research task navigates via a11y tree; no open-ended pixel clicking | L |
| G2 | **Query planning** from case facts → search + fetch primary sources | Given "boiler model X spec", fetches manufacturer spec sheet | M |
| G3 | **`SourceTrust` computation** (`05` §11) — discrete scoring task (see S-TRUST) | Manufacturer page scores higher than forum on Authority/Directness | — (see S-TRUST) |
| G4 | **Fact storage**: URL, source type, date checked, snippet, trust score, relevance; feeds `Source_q` in Confidence (`05` §6) | Each web fact persisted with all fields + trust score | M |
| G5 | **Injection filter guardrail** on fetched web content (`02` §5) | Prompt-injection payload in a page does not alter worker instructions | M |
| G6 | **Corroboration**: seek a second source when trust/consistency is low | Single-source fact flagged low-trust until corroborated | S |

---

## Epic H — Offer Comparator

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| H1 | **Offer normalization** into `Offer` fields (price, scope, warranty, payment, exclusions, hidden_costs) from ours + competitor/client-provided | Two offers parsed into comparable structured records | M |
| H2 | **`OfferScore` computation** (`05` §7) — discrete scoring task with per-vertical weight overrides (see S-OFFER) | HVAC weights `Warranty`+`Service` higher per playbook | — (see S-OFFER) |
| H3 | **`Comparison` builder**: `axis_scores`, `weights_version`, recommendation, `hidden_risk_flags` → `EvidenceReference` | Stored comparison table + plain-language value-based recommendation | M |
| H4 | **Hidden-risk flagging**: shorter warranty, missing service, exclusions — each evidence-linked to the source offer | Each flag cites the offer region it came from | M |
| H5 | State wiring for `NEGOTIATION` / `DOCUMENT_ANALYSIS` competitor-offer path (`03` §3.6, §3.10) | Client-provided competitor offer routes to comparison then negotiation | S |

---

## Epic I — Follow-up / Promise / Missing-Info

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| I1 | **`FollowUpSequence` engine** (`04`, `09` §2): steps, quiet_hours, max_attempts, min_interval, active_step_index, state | Cadence advances step-by-step; exhausted → `RECOVERY_LATER` | M |
| I2 | **`FollowUpPriority` computation** (`05` §4) — discrete scoring task (see S-FUP) | Channel+timing chosen by score, respecting hard guarantees | — (see S-FUP) |
| I3 | **Hard guarantees** (`05` §4, `09` §2): quiet hours, opt-outs, STOP, min interval, max attempts, one consolidated ask | Attempt during quiet hours or after cap is blocked | M |
| I4 | **Channel selection** with learned per-party preference (Deal Memory) + playbook default (WhatsApp→SMS→email→call) | New party uses default order; known party uses learned order | M |
| I5 | **Cadence presets** post-offer `+24h→+72h→+7d→RECOVERY_LATER`; missing-info `+24h→+48h→+72h` (tunable) | Presets seeded per playbook; tenant can override | S |
| I6 | **Promise Tracker** (`09` §3): create `Promise` rows from calls/messages (any party) with importance + dependency_impact | Extracted promise stored with who/what/due_at/evidence ref | M |
| I7 | **`PromiseBreachScore` computation** (`05` §10) — discrete scoring task (see S-BREACH) | Overdue "send signed contract" scores above overdue "send a photo" | — (see S-BREACH) |
| I8 | **Breach routing** (`09` §3): client-side breach → missing-info nudge; company/technician/notary breach → owner alert/escalation | Company broken promise raises owner alert; client one nudges gently | M |
| I9 | **Missing-Information Hunter** (`09` §4): re-evaluate `MissingItem`s each event; on `MIS_normalized ≥ θ_mis` or any `blocks_quote` missing → single example-bearing request | One consolidated request with example hint; marks `received` on satisfaction | M |
| I10 | **Objection Handler** (`09` §5): detect objection types; prepare bounded response or escalate; pull edges from `BusinessProfile` + Comparator | Discount-beyond-authority objection escalates; in-bounds gets suggested reply | M |
| I11 | **Quote Builder** (`09` §6): base + premium variants, assumptions, blockers, risks, sales args from intake+docs+`price_rules`+Deal Memory | Draft quote produced; high uncertainty → `HUMAN_REVIEW_REQUIRED` | M |
| I12 | **`RECOVERY_LATER` wake** with context-aware opener at `wake_at` (`03` §3.17) | Parked lead wakes and re-enters `FOLLOW_UP_ACTIVE` with contextual message | S |

---

## Epic J — Decision Worker

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| J1 | **`DecisionBrief` generator** in canonical shape (`09` §7): summary, value_range, situation, recommended_step, rationale, risk_note, confidence, evidence refs | Brief matches the Kowalski canonical example structure | M |
| J2 | Trigger briefs on **meaningful state changes**; mark prior `superseded` | New brief supersedes old; both retained | S |
| J3 | **Quality/Eval verifier pass** (`02` §4 Quality Worker): every claim evidence-linked, confidence honest, nothing missing | Brief with an unlinked claim fails the verifier | M |
| J4 | Surface brief into Command Center with one-tap actions | Owner sees brief + can act/edit from UI | S |

---

## Epic K — Command Center UI (Next.js, this repo)

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| K1 | **Auth + tenant context** in `web`; all API calls carry tenant scope | User only ever sees their `BusinessProfile` data | M |
| K2 | **Case list / work queue** sorted by score bands (Hot ≥70 / Warm / Cool / Cold) + stuck tile (`05` §1, §9) | Cases sorted by `LeadScore` band; stuck-but-hot float to top | M |
| K3 | **Case detail** view: state, `next_best_action`, `due_at`, timeline of `AuditEvent`s, evidence links | Every AI claim on the page links to its evidence | L |
| K4 | **Case Graph visualization** (blockers, promises, offers) from `graph_edges` | "What blocks this quote?" renders the blocker subgraph | M |
| K5 | **Approvals inbox** for `HumanApproval` (context, options, recommendation, deadline, SLA) | Owner approves/rejects; decision writes `Action` + audit | M |
| K6 | **Tasks board** (`Task`): assignee, priority, due, status | Task states move open→in_progress→done/snoozed | S |
| K7 | **Decision Brief cards** with one-tap send/edit | Brief actionable from UI; edit persists | S |
| K8 | **Offer comparison view**: table + recommendation + hidden-risk flags | Renders `Comparison.axis_scores` + evidence-linked flags | M |
| K9 | **Follow-up / cadence view**: sequence state, next touch, quiet hours, opt-outs | Owner can pause/resume a `FollowUpSequence` | S |
| K10 | **Revenue Recovery view** (`09` §8): recovered leads / pipeline value | Shows recovered pipeline from `RECOVERY_LATER` wakes | M |
| K11 | **Settings**: `BusinessProfile` thresholds, `IndustryPlaybook` weights, autonomy defaults, quiet hours, consent config | Tenant edits thresholds; changes take effect without deploy | M |
| K12 | **Score explainability panels**: show input vector + weight version for any score (from `AuditEvent`) | Clicking a `LeadScore` shows its components + weight version | M |
| K13 | **Realtime updates** (case state, new approvals) via streaming/websocket to the dashboard | New inbound event updates the open case view live | M |
| K14 | **Voice call console**: live transcript, latency, barge-in, handoff button | Owner can watch a live call and take a warm handoff | L |

---

## Epic L — Integrations (MCP)

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| L1 | **MCP tool host + typed contracts** so each integration is a swappable server (`02` §3) | A worker calls an MCP tool with a typed schema; server is testable in isolation | M |
| L2 | **WhatsApp Business** MCP server (send/receive, media) | Inbound WhatsApp creates `Conversation`+`Message`; outbound sends | M |
| L3 | **SMS provider** MCP server | Outbound SMS with delivery status recorded | S |
| L4 | **Email (Gmail/Outlook)** MCP server (threaded) | Email thread maps to a `Conversation` | M |
| L5 | **Telephony/SIP** MCP integration feeding Voice Worker | PSTN call bridged to Voice Worker session | M |
| L6 | **Calendar** MCP server (Google) for `SCHEDULED` bookings/reminders | Booking creates a calendar event; reminders `-24h`/`-2h` fire | M |
| L7 | **CRM / Drive** MCP servers (optional at MVP) | Read/write validated against typed contract | M |
| L8 | **`IntegrationAccount` OAuth flows** storing only a secrets handle (`04`) | Connect flow writes handle, not token; least-privilege scopes | M |
| L9 | **Webhook ingest** normalizing all channels into inbound events for the router (`02` §1) | Any channel webhook produces a normalized event for C5 | M |

---

## Epic M — Autonomy / Guardrails / Audit

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| M1 | **Autonomy levels (1–5)** per action type from `BusinessProfile.autonomy_defaults` / `Case.autonomy_level` | Action above level → `HumanApproval` instead of execution | M |
| M2 | **HITL interrupt** wiring: `HUMAN_REVIEW_REQUIRED` caps autonomy at Level 2 "Prepare"; freezes outbound (`03` §3.11) | In review state, no client-facing action can execute | M |
| M3 | **Input/output guardrails** run in parallel to workers (`02` §5): PII checks, scope checks, price-rule checks, injection filters | A price-rule violation fails-fast a proposal before send | M |
| M4 | **`EscalationScore` computation** (`05` §8) — discrete scoring task with hard overrides (see S-ESC) | LegalSensitivity=1 on a signing decision escalates regardless of sum | — (see S-ESC) |
| M5 | **Abstention rule** (`05` §6): `Confidence < θ_conf` must not assert fact as certain; blocks autonomous client-facing action | Low-confidence fact surfaced as *unverified*, no autonomous send | M |
| M6 | **Full `AuditEvent` coverage** + `hash_prev` chain verification job (`04`) | Any transition/score/action/approval writes an audit; chain verifies | M |
| M7 | **GDPR erasure + DSAR export** as first-class operations; opt-out suppression survives erasure (`04`) | Erase removes PII + media/OCR; suppression hash remains | L |
| M8 | **Human-override logging** as labeled training data (`05` §13) | Each override stored as a `(context, action, decision)` example | S |

---

## Epic N — Evaluation Lab

| # | Story / task | Acceptance criterion | Size |
|---|---|---|---|
| N1 | **Score calibration harness**: reliability curves, Brier / ECE for `P(close|a)` and `Confidence` (`05` §13) | Calibration report generated on logged outcomes | M |
| N2 | **Shadow scoring / back-test**: apply new weight sets to historical cases before rollout (`05` §13) | Weight change back-tested; diff report produced | M |
| N3 | **Score-distribution drift monitors** per tenant; alert on sudden shifts (`05` §13) | OCR regression inflating `Q` triggers a drift alert | M |
| N4 | **Voice eval suite**: TTFA P50/P95, barge-in latency, handoff precision, reasoning under disfluency (`06` §3, §6) | Voice metrics tracked per call and aggregated | M |
| N5 | **Extraction / comparison eval**: field-extraction F1, contradiction-detection precision, human-override rate (`03` §3.6) | Golden-set F1 reported in CI on the doc pipeline | M |
| N6 | **Hallucination-rate metric** driven by the Quality Worker's evidence-link checks (`02` §4) | Unlinked-claim rate tracked and gated | M |
| N7 | **Golden case fixtures** + replayable event streams for regression | A recorded case replays deterministically through the loop | M |

---

## Scoring functions — discrete implementable tasks

> All scores are **deterministic, auditable functions** (`05`): LLMs/specialist models produce
> the *inputs*; this layer combines them with tenant-tunable weights from
> `IndustryPlaybook.scoring_weights` / `offer_weights`. Each task ships with: a pure function,
> a normalization step for every sub-signal to `[0,1]`, weight-version stamping, persistence of
> the input vector to `AuditEvent`, and unit tests over golden inputs.

| Task ID | Score | Formula (from `05`) | Acceptance criterion | Size |
|---|---|---|---|---|
| S-LEAD | **LeadScore** | `100·(0.30V+0.20U+0.15F+0.15C+0.10D+0.10R)` (§1) | Bands Hot≥70/Warm/Cool/Cold correct; cold-start sets `R=0.5` + `low_confidence` flag | M |
| S-MIS | **MIS** | `Σ w_i·m_i`, `MIS_normalized = MIS/Σw_i` (§2) | Any `blocks_quote` missing blocks `QUOTE_PREPARATION`; `≥θ_mis` queues one `MissingItem` request | S |
| S-NBA | **NBA Utility** | `P(close\|a)·Value − Cost(a) − Risk(a) − DelayPenalty(a)` (§3) | `argmax` selection; heuristic prior table per (state, action); ties → lower cost/risk; runner-ups stored | L |
| S-FUP | **FollowUpPriority** | `LeadScore·TimeDecay·IntentSignal − AnnoyanceRisk` (§4) | Hard guarantees never violated regardless of score; channel/timing chosen by score | M |
| S-DOCRISK | **DocRisk** | `100·(0.25A+0.20M+0.20C+0.15P+0.10L+0.10Q)` (§5) | `≥θ_docrisk`(60) → `HUMAN_REVIEW_REQUIRED` "requires human before signing"; found vs. unverified separated | M |
| S-CONF | **Confidence** | `OCR_q·Extraction_q·Source_q·Consistency_q` (§6) | `<θ_conf`(0.6) → must-not-assert; abstention path exercised | S |
| S-OFFER | **OfferScore** | `100·(0.25Price+0.20Scope+0.15Warranty+0.15Time+0.10Payment+0.10Risk+0.05Service)` (§7) | Price normalized within comparison set; per-vertical weight overrides applied; value-based (not cheapest) recommendation | M |
| S-ESC | **EscalationScore** | `Risk+ValueCriticality+LowConfidence+ClientEmotion+LegalSensitivity+UnusualRequest` (§8) | `≥θ_escalate`(1.5) → interrupt edge; hard overrides escalate regardless of sum | M |
| S-STUCK | **StuckScore** | `DaysSinceProgress·LeadScore·MissingBlockerWeight` (§9) | Computed nightly; `≥θ_stuck` → follow-up or owner alert per autonomy; surfaces on stuck tile | S |
| S-BREACH | **PromiseBreachScore** | `Importance·Delay·DependencyImpact` (§10) | Symmetric client/company; `≥θ_breach` → reminder (client) or owner alert/escalation (company) | S |
| S-TRUST | **SourceTrust** | `100·(0.35Authority+0.25Recency+0.20Corroboration+0.15Directness+0.05Transparency)` (§11) | Feeds `Source_q` in Confidence; every web fact stored with trust score | S |

> **Thresholds** (`θ_qualify, θ_escalate, θ_docrisk, θ_conf, θ_mis, θ_stuck, θ_breach`,
> high-value, quiet hours, max attempts) live in `BusinessProfile.thresholds` /
> `IndustryPlaybook` — never hard-coded (`03` §5, `05`).

---

## X. Cross-cutting

### X.1 Multi-tenancy + Row-Level Security
- [ ] Every table carries `tenant_id`; **Postgres RLS policies** enforce tenant isolation at the DB layer (not just app filters). `S`
- [ ] Data-access layer injects `tenant_id` on every query; a guard test fails any unscoped query (see B10). `M`
- [ ] `data_region` pinning per `BusinessProfile.data_region`; cross-region access blocked. `M`
- [ ] Tenant-scoped connection/context propagated through orchestrator → workers → MCP tools. `M`

### X.2 Secrets management
- [ ] All external credentials in the **secrets manager**; DB stores only `IntegrationAccount.credentials_ref` handles (see A3, B9). `M`
- [ ] Least-privilege OAuth scopes; token rotation; encryption at rest for tokens. `M`
- [ ] Secret access is audited (`AuditEvent`); no secret ever logged. `S`

### X.3 Observability / tracing
- [ ] **Distributed tracing** across router → worker → MCP tool → LLM call (align with OpenAI Agents SDK tracing / LangGraph run traces, `02`). `M`
- [ ] Structured logging with `tenant_id`, `case_id`, `event_type`; PII-minimized. `S`
- [ ] Metrics: TTFA (voice), sweep duration, queue depth, approval SLA breach, score distributions. `M`
- [ ] `hash_prev` audit-chain integrity monitor (see M6). `S`

### X.4 CI/CD
- [ ] CI: lint + typecheck + unit tests for `web` (Next.js) and `core` (Python). `S`
- [ ] Migration gate: DB migrations run + verified in CI against a disposable DB. `S`
- [ ] Golden-set eval gates (extraction F1, hallucination rate) block merges on regression (see N5/N6). `M`
- [ ] Deploy pipelines for `web` and `core` with staging → prod promotion; secrets injected at deploy, never committed. `M`

### X.5 Testing
- [ ] **State-machine property tests**: only legal transitions (`03` §4); invariants always hold. `M`
- [ ] **Scoring golden tests**: every score function has golden input→output vectors + weight-version reproducibility. `M`
- [ ] **Loop integration tests**: replay recorded event streams through the completion loop (see N7). `M`
- [ ] **Guardrail tests**: prompt-injection, price-rule, PII, quiet-hours, STOP/opt-out. `M`
- [ ] **Voice E2E**: scripted call fixtures asserting latency + post-call artifacts. `M`
- [ ] **Multi-tenancy isolation tests**: tenant A can never read tenant B. `S`

---

## Suggested build sequence (dependency order)

```
1. Data model + state machine + orchestrator skeleton   (B1–B6, C1–C4, A1–A5)
2. Intake + Case Graph                                   (E1–E6, B7–B8, S-LEAD, S-MIS)
3. One channel end-to-end: WhatsApp                      (L1, L2, L9, C5–C7)
4. Follow-up loop (nightly sweep + cadence + guarantees) (C8, I1–I5, S-FUP, S-STUCK, M1–M2)
5. Promise + Missing-Info + NBA                          (I6–I12, C9, S-NBA, S-BREACH)
6. Documents                                             (F1–F8, S-DOCRISK, S-CONF)
7. Voice                                                 (D1–D12, L5, N4)
8. WebScout                                              (G1–G6, S-TRUST)
9. Offer Comparator                                      (H1–H5, S-OFFER)
10. Decision Briefs + Quality Worker                     (J1–J4, N6)
11. Command Center polish + Revenue Recovery + eval lab  (K2–K14, N1–N7, M3–M8)
```

**Rationale**: nothing works without the durable state machine + data model + orchestrator
skeleton (`03`/`04`/`02`), so that is the critical path. Intake + a single channel (WhatsApp)
gives the first live case; the follow-up loop is the product's core differentiator (`09`) and
comes next; heavier workers (documents, voice, webscout, offers) attach to already-working
states afterward; decision briefs and Command Center polish sit on top of everything.

---

## Milestone view (Phases → tasks)

| Phase | Duration | Goal | Tasks in scope |
|---|---|---|---|
| **Phase 0** | 2 wks | Design & de-risk | Finalize framework picks (LangGraph vs. Agents SDK per `02`; LiveKit vs. Pipecat per `06`; telephony provider); schema review (B1–B6 on paper); threshold defaults per playbook; A1–A3 provisioning; CI skeleton (X.4) |
| **Phase 1** | 4–6 wks | Prototype (one vertical, one channel) | B1–B8, C1–C9, E1–E6, L1/L2/L9, I1–I9, S-LEAD, S-MIS, S-FUP, S-NBA, S-STUCK, S-BREACH, C8 nightly sweep, M1–M2, basic K1–K3; multi-tenancy X.1 + secrets X.2 baseline |
| **Phase 2** | 8–12 wks | Beta (real HVAC/plumbing tenants) | F1–F8 + S-DOCRISK/S-CONF, D1–D12 voice + N4, H1–H5 + S-OFFER, J1–J4 + Quality Worker, K4–K14 Command Center, L3–L8 integrations, M3–M8 guardrails/audit/GDPR, N1–N3/N5–N7 eval lab, full X.3 observability |
| **Phase 3** | Paid MVP | Harden + monetize | G1–G6 WebScout + S-TRUST, S-ESC + hard overrides, calibration/back-test in production (N1–N2), SLA dashboards, billing/onboarding, X.5 full test coverage, performance tuning of sweep + graph traversals |
| **Phase 4** | Multi-vertical | Scale beyond HVAC | New `IndustryPlaybook`s (plumbing/electrical/renovation → auto/property) via config only (no code changes to scoring); per-vertical `offer_weights`/`scoring_weights`; optional Neo4j migration if graph traversal thresholds (`04`) are exceeded; realtime-voice adapter for simple flows (`06` §1) |

---

## Team, skills & parallelization

| Role | Focus epics | Notes |
|---|---|---|
| **Backend / orchestration eng (×2)** | C, B, I, M | Owns the state machine, durable loop, scoring, autonomy. Critical path. |
| **Data / ML eng (×1–2)** | E, F, G, N + all scoring tasks | Extraction, embeddings/Deal Memory, calibration, eval lab. |
| **Voice eng (×1)** | D, L5 | Real-time media, latency, telephony. Specialist; can run in parallel from Phase 2. |
| **Frontend eng (×1–2)** | K (this Next.js repo), parts of A6 | Command Center; can start against mocked `core` APIs early. |
| **Integrations eng (×1)** | L, X.2 | MCP servers per channel; parallelizable once L1 host exists. |
| **Platform / DevOps (×1)** | A, X.1, X.3, X.4 | Infra, RLS, secrets, tracing, CI/CD. Enables everyone. |
| **PM / domain (HVAC) (×1)** | Playbooks, thresholds, eval golden sets | Owns `IndustryPlaybook` content and acceptance labels. |

**Parallelization guidance**
- **Phase 0–1**: platform (A/X) + backend (B/C) are the critical path; frontend builds K against
  mocked APIs; integrations builds the WhatsApp MCP server (L2) in parallel behind the L1 contract.
- Once the state machine + case graph exist, **scoring tasks (S-*) are highly parallelizable** —
  each is an independent pure function with golden tests.
- **Voice (D)**, **Documents (F)**, **WebScout (G)**, and **Offer Comparator (H)** are independent
  workers that attach to already-built states; they can be staffed concurrently in Phase 2 as
  capacity allows.
- **Eval Lab (N)** should start early (golden fixtures + calibration harness) so it gates the
  workers as they land rather than being retrofitted.

---

## 90-Day Sprint Plan (Phase 0 → end of Phase 1 → into Phase 2)

> Six 2-week sprints (S1–S6, days 1–84, with days 85–90 as hardening buffer inside S6). This is
> the milestone view above cut into shippable increments, following the **suggested build
> sequence** exactly: data model + state machine + orchestrator first, then WhatsApp channel,
> follow-up loop, promises/missing-info/NBA, documents, voice, briefs + dashboard. Voice runs as
> a **parallel specialist track** from S4 (per the parallelization guidance) so it lands by day
> 90 without blocking the critical path.
>
> **Day-90 target** (consistent with Phase 1 goals in `14` §2 and the P1 column of the
> capability matrix): end-to-end demo on 5–10 real cases — AI answers phone + WhatsApp, creates
> cases, hunts missing info, follows up on cadence, analyzes an uploaded document, produces
> Decision Briefs, and the Command Center shows the pipeline + approvals.

### S1 (days 1–14) — Phase 0: design, de-risk, foundations

| | |
|---|---|
| **Sprint goal** | All Phase-0 open decisions closed as ADRs; infra + skeletons exist; nothing downstream is blocked. |
| **Tasks** | Framework picks (LangGraph vs. Agents SDK per `02`; LiveKit vs. Pipecat per `06`; telephony + OCR provider); schema review of B1–B6 on paper; threshold defaults per playbook (`BusinessProfile.thresholds`); **A1–A5, A8** (Postgres+pgvector, object store, secrets manager, durable scheduler, core skeleton, local compose); CI skeleton (X.4 lint/typecheck/migration gate); begin **B1–B2** migrations; **N7** golden case fixtures started (Eval Lab starts early). |
| **Demo / checkpoint** | `docker compose up` runs web + core + db + scheduler; a job scheduled 72h out survives a restart (A4); B1–B2 migrations green in CI; ADRs merged. |
| **Exit criteria** | All Phase-0 decisions have a merged ADR; A1–A5 acceptance criteria met; `Case.status` enum in B2 matches `03` 1:1; CI red/green gate live. |

### S2 (days 15–28) — State machine, orchestrator core, data layer complete

| | |
|---|---|
| **Sprint goal** | The durable spine exists: every case lives in the state machine, under invariants, with audit. |
| **Tasks** | **C1** state-machine engine (17 states + transition table); **C2** global invariants (non-null `next_best_action` + `due_at`; transitions write `AuditEvent`); **C3** global interrupt edge (Sprint 2 ships hard-override rules only; full S-ESC scoring lands Phase 3 — see 03 §2 invariant 5 MVP note); **C4** durable LangGraph case runtime; finish **B3–B6** (evidence, commercial/workflow tables, `AuditEvent` hash chain, `graph_edges`); **B10** tenant-scoped repository layer; **A6** Next.js `web` baseline + **A7** environments; X.5 state-machine property tests. |
| **Demo / checkpoint** | Scripted walkthrough in a test harness: seeded case driven `NEW_CONTACT → INTAKE_IN_PROGRESS → … → WON`, illegal transition rejected, kill-and-restart resumes mid-case (C4); audit chain verifies. |
| **Exit criteria** | C1–C4 acceptance criteria met; property tests pass (only legal transitions, invariants always hold); B1–B6 + B10 done; authenticated user reaches an empty Command Center calling `core` (A6). |

### S3 (days 29–42) — Intake + Case Graph + first live channel (WhatsApp)

| | |
|---|---|
| **Sprint goal** | First **real case from a real channel**: an inbound WhatsApp message becomes a scored, stateful case. |
| **Tasks** | **E1–E6** Intake Worker (classifier, playbook-driven `MissingItem` instantiation, slot filling, over-asking guard, returning-client Deal Memory match, score emission); **B7–B8** (recursive-CTE traversals, pgvector); **S-LEAD, S-MIS**; **L1** MCP tool host, **L2** WhatsApp Business server, **L9** webhook ingest; **C5–C7** (event router, worker-proposal contract, event-driven loop trigger); X.1 RLS policies + isolation test; **K1** auth/tenant context in `web`. |
| **Demo / checkpoint** | Live demo: send a WhatsApp message → `Conversation`+`Message` created → intake conversation fills slots → case lands in `QUALIFIED` with `LeadScore`/`MIS` persisted; spam message → `ABANDONED`. |
| **Exit criteria** | Inbound WhatsApp routed to the correct worker per state (C5); workers cannot mutate state directly (C6); S-LEAD bands + cold-start `R=0.5` golden tests pass; tenant A can never read tenant B. |

### S4 (days 43–56) — Follow-up loop: the core differentiator

| | |
|---|---|
| **Sprint goal** | No case is ever silently dropped: the nightly sweep + cadence engine + hard guarantees are live. |
| **Tasks** | **C8** nightly stuck sweep (recompute scores, invariant check, park/wake `RECOVERY_LATER`); **I1–I5** (`FollowUpSequence` engine, hard guarantees, channel selection, `+24h/+48h/+72h` presets); **S-FUP, S-STUCK**; **M1–M2** autonomy levels + HITL interrupt; **C12** STOP/opt-out hard rule; **K2** work queue by score bands + stuck tile; guardrail tests (quiet hours, STOP, max attempts). ▸ *Voice track starts in parallel:* **D1** media framework + SIP/PSTN, **D2** cascaded STT→LLM→TTS spike. |
| **Demo / checkpoint** | Time-travel demo on seeded cases: sweep run produces expected transitions + queued follow-ups; an attempt during quiet hours is blocked; STOP permanently suppresses outbound; owner sees Hot/Warm/Cool/Cold queue in the Command Center. |
| **Exit criteria** | C8 sweep acceptance met; hard guarantees never violated regardless of score (S-FUP); action above autonomy level yields `HumanApproval` instead of execution (M1); exhausted cadence parks to `RECOVERY_LATER` and wakes on `wake_at`. |

### S5 (days 57–70) — Promises, Missing-Info Hunter, NBA + document pipeline opens

| | |
|---|---|
| **Sprint goal** | The completion loop is whole (hunt gaps, track promises, pick the next best action) and documents start flowing. |
| **Tasks** | **I6–I12** (Promise Tracker, breach routing, Missing-Information Hunter, Objection Handler, `RECOVERY_LATER` wake — Quote Builder I11 in draft-only mode per MVP scope); **C9** NBA selection + **S-NBA, S-BREACH**; **F1–F3** (ingestion/quality gate, OCR + layout, schema-constrained extraction with `EvidenceReference`); **S-CONF** abstention rule + **M5**; **K3** case detail with timeline + evidence links; **K5** approvals inbox; **N5** extraction eval (golden-set F1 in CI). ▸ *Voice track:* **D3–D7** (barge-in, turn detection, context prefetch, latency instrumentation, fallback-when-slow) + **L5** telephony MCP. |
| **Demo / checkpoint** | End-to-end on a live case: client promises a document on a call transcript fixture → `Promise` row → overdue → nudge; `blocks_quote` gap → one consolidated example-bearing request; blurry scan → polite re-scan request; owner approves a proposed action from the approvals inbox. |
| **Exit criteria** | `a*` persisted to `Case.next_best_action` with runner-ups in `Action.chosen_over` (C9); missing-info recall ≥ 0.9 on the golden set; OCR field F1 at target on the pilot doc mix (N5 gate in CI); company-side breach raises owner alert, client-side breach nudges (I8). |

### S6 (days 71–90) — Voice live, document analysis complete, briefs + dashboard: the Day-90 demo

| | |
|---|---|
| **Sprint goal** | The full Phase-1 story on real cases; days 85–90 reserved for hardening + demo rehearsal (no new scope). |
| **Tasks** | *Voice track lands:* **D8–D12** (repair/slot confirmation, language switching, warm handoff, post-call processing with evidence refs, consent gating) + **N4** voice eval suite; *documents complete:* **F4–F8** + **S-DOCRISK** (contradiction check vs. prior agreements, RiskFlags, found-vs-unverified summary, state wiring); **J1–J4** Decision Briefs + Quality Worker verifier + **N6** hallucination gate; **K6–K7, K9, K13** (tasks board, brief cards, cadence view, realtime updates); **L6** calendar booking; **M6** full audit coverage check; **N7** replay regression on the demo cases. |
| **Demo / checkpoint** | **Day-90 end-to-end demo on 5–10 real cases** (`14` Phase 1 goal): AI answers a PSTN call and WhatsApp, creates the case, hunts missing info, follows up on cadence, analyzes an uploaded PDF (fields + confidence + summary + consistency check), produces a Decision Brief the owner acts on with one tap, and the Command Center shows pipeline, hot/stuck leads, promises due, and approvals — with every claim evidence-linked. |
| **Exit criteria** | Voice TTFA P50 ≤ 800 ms / P95 ≤ 1500 ms on simple turns (D6/N4); post-call artifacts persist with evidence refs (D11); `DocRisk ≥ θ_docrisk` routes to `HUMAN_REVIEW_REQUIRED` (F8); brief with an unlinked claim fails the verifier (J3); demo cases replay deterministically (N7). |

**Deliberately after day 90** (Phase 2/3 per the milestone view): WebScout (G, S-TRUST), Offer
Comparator (H, S-OFFER), S-ESC full computation (the C3 interrupt edge ships on hard rules
first), remaining integrations (L3/L4/L7/L8), M3/M7 guardrail depth + GDPR erasure, K4/K8/K10–K12/K14,
N1–N3 calibration/drift, billing.

---

## Acceptance Criteria (MVP definition of done, per module)

> "Done" means the criterion is **mechanically verified** — by a test in CI, an eval metric on
> the golden set, or a production invariant with alerting. Thresholds (`θ_*`) come from
> `BusinessProfile.thresholds` / `IndustryPlaybook`, never hard-coded. Metric names match `05`,
> `06`, `14` §1 and Epic N.

| Module | Acceptance criteria (MVP definition of done) | How verified (test / eval metric) |
|---|---|---|
| **State machine** (C1–C4, C12) | All 17 states + transition table 1:1 with `03` §4; illegal transitions rejected; every active case has non-null `next_best_action` **and** `due_at`; every transition writes `AuditEvent{from,to,actor,reason,evidence_refs}`; kill/restart resumes at last checkpoint; STOP forces `ABANDONED`/`LOST` and permanently suppresses outbound. | State-machine **property tests** (X.5) in CI; invariant check enforced at write time + **nightly sweep alert** on any violating case; chaos test kills `core` mid-case and asserts resume; STOP guardrail test. |
| **Scoring functions** (S-LEAD … S-TRUST) | Each score is a pure, deterministic function of a persisted input vector + weight-set version; recomputing from the stored `AuditEvent` reproduces the value bit-for-bit; bands/thresholds behave per `05` (Hot ≥ 70, `θ_mis`, `θ_docrisk` = 60, `θ_conf` = 0.6, `θ_escalate` = 1.5); cold-start `R=0.5` + `low_confidence` flag. | **Golden input→output vectors** per score in CI (X.5); reproducibility test replays audit rows; threshold-boundary unit tests at `θ ± ε`. |
| **Intake** (E1–E6) | Serviceable request advances `NEW_CONTACT → INTAKE_IN_PROGRESS`; spam/wrong-number → `ABANDONED`; `MissingItem` rows instantiated from `IndustryPlaybook.required_fields` with `weight` + `blocks_quote`; one consolidated ask (never field-by-field); no unstated fact ever assumed; initial `LeadScore`/`MIS` persisted; returning client matched via Deal Memory. | Intake **golden conversation set**: intent-classification accuracy + slot-fill F1 reported in CI; over-asking guard test (asserts ≤ 1 consolidated request per gap batch); Deal Memory match precision on seeded returning parties. |
| **WhatsApp channel** (L1, L2, L9, C5–C7) | Inbound message creates `Conversation` + `Message` and is routed to the owning worker for the current state; outbound sends with delivery status; media (photos/PDFs) ingested to object store; any inbound event re-runs scoring + NBA immediately; workers return proposals only. | **Loop integration test** replaying a recorded WhatsApp event stream (N7); webhook-ingest contract test per L9; interface-level test that a worker cannot mutate case state (C6); routing table test per (state × event type). |
| **Follow-up loop** (C8, I1–I5) | Cadence presets `+24h→+48h→+72h` (missing-info) and `+24h→+72h→+7d→RECOVERY_LATER` (post-offer) fire on schedule; quiet hours, opt-outs, min interval, max attempts **never** violated regardless of score; exhausted → `RECOVERY_LATER`, wakes at `wake_at` with contextual opener; nightly sweep recomputes all five scores on every active case and enqueues NBA. | Time-travel **sweep test** on seeded fixtures asserting expected transitions + queued actions; guardrail tests injecting quiet-hours/cap violations (must block); production metric: **follow-up reply lift vs. no-AI baseline** measurable per `14` §1; sweep-duration metric (X.3). |
| **Promise tracker** (I6–I8, S-BREACH) | Promises extracted from calls + messages for **any** party with who/what/`due_at`/importance/`dependency_impact` + evidence ref; overdue high-importance promise outscores trivial one; client breach → gentle nudge, company/technician breach → owner alert. | Promise-extraction **recall/precision on golden transcripts**; S-BREACH golden vectors (signed-contract vs. photo ordering); breach-routing integration test asserting nudge-vs-alert per party role. |
| **Missing-info hunter** (I9, S-MIS) | `MissingItem`s re-evaluated on every event; `MIS_normalized ≥ θ_mis` or any missing `blocks_quote` item triggers exactly one consolidated, example-bearing request; items marked `received` on satisfaction; missing `blocks_quote` blocks `QUOTE_PREPARATION`. | **Missing-info recall ≥ 0.9 on the golden set** (`14` §1); consolidation test (n gaps → 1 message); state-gate test that `QUOTE_PREPARATION` is unreachable with an open `blocks_quote` item. |
| **Document intelligence** (F1–F8, S-DOCRISK, S-CONF) | Quality gate computes `ocr_quality`, failing docs get `needs_rescan` + polite re-scan request (never silent); every `ExtractedField` carries `page`/`bbox` + `EvidenceReference`; contradictions vs. prior agreements flagged with both evidence refs; summary separates *found* vs. *couldn't verify*, never legal advice; `DocRisk ≥ θ_docrisk` → `HUMAN_REVIEW_REQUIRED`. | **OCR field F1 ≥ target per field type** on the tenant doc mix, gated in CI (N5); contradiction-detection precision on golden pairs; rescan-path integration test; verifier check that no summary claim lacks an evidence link. |
| **Voice worker** (D1–D12) | **TTFA P50 ≤ 800 ms, P95 ≤ 1500 ms** on simple turns; barge-in stops TTS ≤ 200 ms after speech onset; mid-thought pause does not trigger premature response; critical slots (address/date/price) confirmed via repair questions; gas-leak/safety keyword → safety script + warm handoff with live summary; post-call artifacts (summary, `Promise`, `MissingItem`, next-action proposals, `ExtractedField`, sentiment timeline) all persist with transcript-timestamp evidence refs; recording suppressed where consent config forbids. | **Voice eval suite N4**: `Call.latency_metrics` dashboards (ttfa_p50/p95), barge-in latency, handoff precision; scripted-call E2E fixtures (X.5) asserting latency + all six post-call artifacts; consent-gating unit test per `VoiceProfile.consent_prompt` config. |
| **Decision briefs** (J1–J4) | Every brief matches the canonical shape (`09` §7: summary, value_range, situation, recommended_step, rationale, risk_note, confidence, evidence refs); every claim evidence-linked; confidence honest (no assertion below `θ_conf`); new brief supersedes prior (both retained); actionable one-tap from UI. | **Quality Worker verifier** blocks any brief with an unlinked claim (J3); **hallucination / unsupported-claim rate near-zero** on evidence-required outputs, tracked + gated (N6); schema validation test against the canonical Kowalski example. |
| **Command center** (K1–K3, K5–K7, K9, K13) | User sees only their tenant's data; work queue sorted by score bands with stuck-but-hot on top; case detail shows state, `next_best_action`, `due_at`, audit timeline — **every AI claim on the page links to its evidence**; approvals inbox shows context/options/recommendation/deadline and decisions write `Action` + audit; inbound events update the open case view live. | Multi-tenancy **isolation tests** (tenant A never reads tenant B, RLS-level); UI e2e asserting band ordering + evidence-link presence on every claim element; approval round-trip test (approve → `Action` + `AuditEvent`); websocket-update e2e on a live inbound event. |
| **Autonomy / approvals / audit** (M1–M2, M5–M6, C2–C3) | Action above the case/tenant autonomy level yields `HumanApproval` instead of executing; `HUMAN_REVIEW_REQUIRED` caps autonomy at Level 2 and freezes all client-facing outbound; `Confidence < θ_conf` facts surface as *unverified* and block autonomous client-facing action; every transition/score/action/approval writes an `AuditEvent`; `hash_prev` chain verifiable end-to-end; every human override stored as a labeled `(context, action, decision)` example. | Autonomy matrix test over (action type × level); frozen-outbound test in review state; abstention-path test at `Confidence = θ_conf − ε`; **audit-chain integrity job** (M6/X.3) alerting on any break; audit-coverage assertion in loop integration tests (no state change without an audit row). |
| **Evaluation lab** (N4–N7 at MVP; N1–N3 Phase 2+) | Golden fixtures + replayable event streams exist for intake, docs, voice, and the full loop; a recorded case replays deterministically; extraction F1 and hallucination-rate gates block merges on regression; voice metrics aggregated per call. | **CI eval gates** (X.4): golden-set extraction F1 (N5) + unlinked-claim rate (N6) red/green on every merge; deterministic-replay test (N7) in CI; N4 voice metric aggregation verified on fixture calls; calibration harness (N1) scheduled for Phase 2, not an MVP gate. |

> Roll-up MVP bar (from `14` §1): all module criteria above green **plus** demonstrable
> follow-up reply lift vs. baseline and recovered-pipeline € across pilot tenants — the two
> outcome metrics no unit test can fake.
