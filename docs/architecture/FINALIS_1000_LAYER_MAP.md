# FINALIS 1000 — LAYER MAP

**Program:** FINALIS_1000 · **SP:** SP0000 — Master Architecture Lock · **Type:** docs-only architecture lock.
**Repository baseline:** branch `claude/finalis-ai-casewoker-blueprint-f1huse` · HEAD `5c30c60` · migration v27 · runtime frontier EMP-A1 (`135de7b`) · 0 real outbound effects.

This map locks the canonical layered decomposition. It **does not implement** any layer. Layers 1–10 are *required future architecture*; Layer 0 is *existing verified foundation that must not be silently rebuilt* (see `FINALIS_1000_DO_NOT_REBUILD.md`).

Direction rule: **dependencies point downward only.** A higher layer may depend on a lower layer's stable contract; a lower layer must never depend on a higher one. No layer may make a model, provider, frontend, or external agent authoritative (see `FINALIS_1000_AUTHORITY_BOUNDARIES.md`).

---

## LAYER 0 — EXISTING VERIFIED FOUNDATION  *(EXISTS — DO NOT REBUILD)*

| Component | Repo evidence | Role | Authoritative? |
|---|---|---|---|
| CRM (Relationship Core) | `finalis/crm/*`, migration v7 | System of record for parties/relationships | Authoritative (data) |
| Evidence Trust Fabric | `finalis/evidence/*`, v5/v6/v8; merkle log + proof reports | Evidence + transparency | Authoritative (evidence) |
| Case Graph | `47cb24e` service layer | Case structure / missing-info / promises / NBA | Authoritative (case) |
| Universal Lifecycle | `finalis/lifecycle/*`, v14 kernel | Completion rule + invariants | Authoritative (lifecycle) |
| CPQ / Quote Builder | `finalis/quotes/*`, v3 | Pricing/approvals/change-orders | Authoritative (commercial) |
| Scheduling | `finalis/scheduling/*`, v4 | Appointments/tokens | Authoritative (schedule) |
| Voice / Telephony logic | `finalis/voice/*`, `finalis/telephony/*`, v2 | Call/voice control (mock providers) | Advisory + mock effect |
| Conversation Intelligence | `8379db9` | Diarized evidence-bound analysis | Advisory |
| Action & Communication | `finalis/actions/*` (NovuMock/ChatwootMock) | Send pipeline (mock delivery) | Advisory + mock effect |
| Command Center / Portal | `finalis/portal/*` (app 11.9k L, ui 4k L) | UI + REST (402 routes, 23 sections) | **Not** authoritative (presentation) |
| RBAC / Admin | `finalis/admin/*`, `6804d92` | 9 roles, 45 perms, deny-by-default | Authoritative (access) |
| Tenant Isolation | portal + stores | Cross-tenant boundary | Authoritative (isolation) |
| Audit Chain | `DbAuditLog` (hash-chained) | Tamper-evident event chain | Authoritative (audit) |
| **Governance foundation** | `finalis/ai_employee/*` | proof-carrying ladder | Authoritative (authority) |
| — CORE-A1..A6 | v9–v15 | identity/authority → tasks → run ledger → approvals → lifecycle → artifacts | Authoritative |
| — TOOL-B1..B9.2 | v16–v26 | registry→assurance→contract→monitor→null broker→read runtime→write-intent draft→pre-B9 assurance→transaction twin→recovery→observatory | Authoritative |
| — EMP-A1 | v27 | Governed Work Admission Fabric (admits + prepares fenced handoff; executes nothing) | Authoritative |

Layer 0 is the load-bearing base. Everything above **consumes its contracts**; nothing above may fork it.

---

## LAYER 1 — EMPLOYEE OPERATING KERNEL  *(REQUIRED — NOT BUILT)*

Owned Work · Run Orchestration · Durable Run State · Wait/Timer/Resume · Event Fabric · Zero-Lost-Work · Live Intervention · Replanning · Recovery Coordination · Priority/Capacity.

- Extends: EMP-A1 admission (consumes its fenced handoff), CORE-A3 run ledger, CORE-A5 lifecycle, TOOL-B9.1 recovery.
- Durable execution is an **architectural capability**, engine **replaceable** (no permanent Temporal/vendor lock — decided later by a TDR, SP0004).
- Owns the Zero-Lost-Work invariant (locked here, formalized in SP0015).

## LAYER 2 — KNOWLEDGE & MEMORY  *(REQUIRED — NOT BUILT)*

Claims · Facts · Provenance · Episodic/Semantic/Relationship/Case/Procedural/Decision/Failure memory · Temporal Validity · Contradiction/Supersession.

- Extends: CORE-A6 claim graph, Evidence Trust Fabric, CRM memory (`crm_memory_items`).
- Memory is **data**, never authority. Temporal validity + supersession are first-class (a fact can expire; an old rule must not stay valid too long).
- **Tenant-scoped (INV-0000-13):** every memory item, claim, fact, and KB snapshot is bound to one tenant; no memory crosses tenants without an explicit governed, anonymized path.

## LAYER 3 — CERTIFIED INTELLIGENCE (LGGT+)  *(REQUIRED — NOT BUILT)*

LGGT+ Trusted Mathematical Core · Typed Knowledge DSL · Semantic Input Firewall · Fact Admission · Temporal KB Snapshots · Certified Decision Service · Independent Verification · Formal Specification Track · Evidence Integration.

- LGGT+ **certifies formalizable conclusions relative to versioned facts + rules + a KB snapshot**. It is NOT the conversational brain, NOT a world-truth oracle, NOT execution authority.
- The current LGGT source must be audited directly under SP0021 before implementation (do not treat any older LGGT doc as complete).

## LAYER 4 — ADAPTIVE COGNITION  *(REQUIRED — NOT BUILT)*

Uncertainty · Next Best Action · Model Router · Skill Genome · Worker Orchestrator · Risk/Quality/Cost/Latency optimization.

- Extends: TOOL-B2 planner-selection boundary, governance scoring.
- One user-facing employee identity; many internal specialists; controlled orchestration; **no agent democracy**.

## LAYER 5 — OUTCOME INTELLIGENCE  *(REQUIRED — NOT BUILT)*

Business Outcome Engine · Completion Contracts · Effect Observer · Completion Proof · Failure Intelligence · Win/Loss Intelligence.

- Separates **activity ≠ effect ≠ outcome ≠ completion** (D-0000-05). `EMAIL_SENT ≠ CUSTOMER_RESPONDED`; `INVOICE_SENT ≠ PAYMENT_RECEIVED`.

## LAYER 6 — CONTINUOUS EXPERIENCE INTELLIGENCE  *(REQUIRED — NOT BUILT)*

Experience Capture · Outcome Attribution · Correction/Strategy Learning · Consolidation · Replay · Skill Evolution · Regression Gates.

- Learning is **gated**: experience → candidate → consolidation → counterexamples → replay → evaluation → regression → safe promotion. **Never** experience → direct production mutation (D-0000-09).
- **Tenant-scoped (INV-0000-13):** learning candidates and promotions are per-tenant by default; cross-tenant generalization is forbidden unless it passes an explicit governed, anonymized path — this closes cross-tenant negative transfer, which regression eval-gating alone does not catch.

## LAYER 7 — COMMUNICATION CORTEX  *(REQUIRED — NOT BUILT)*

Email · Voice · Phone · SMS · WhatsApp · Slack · Teams + Communication Goals · Channel Strategy · Timing · Cross-Channel Continuity · Dialogue State · Objections · Questions · Persuasion · Negotiation · Promises · Human Handoff.

- Channels are **communication tools**, not owners of business truth (D-0000-03). Channel history must not become a second source of truth (INV-0000-07).

## LAYER 8 — REAL-WORLD EFFECT BOUNDARY  *(REQUIRED — NOT BUILT — GATED)*

External Adapter Boundary · Credentials · Providers · Browser/Computer Sandbox · MCP Gateway · A2A Gateway · Effect Reconciliation.

- The **first point where a real external effect may occur**. Everything before it is simulated/mocked/drafted/proven. Corresponds to the roadmap's re-scoped TOOL-B10. Every effect must pass Finalis governance (INV-0000-10). MCP/A2A output is data, not authority.

## LAYER 9 — ROLE / VERTICAL COMPOSITION  *(REQUIRED — NOT BUILT)*

Core + Role Pack + Vertical Pack + Country/Jurisdiction Pack + Language Pack + Company Pack.

- Multi-industry/multi-country/multi-language expansion is by **composition, not core forks** (D-0000-14). Control Language ≠ Work Language (D-0000-13; initial PL/EN/DE/ES).

## LAYER 10 — PRODUCTION PLATFORM  *(REQUIRED — NOT BUILT)*

Production Persistence (PostgreSQL) · Event/Queue infra · Object Storage · IAM · KMS · Observability · Billing · Deployment · DR · Residency · Privacy · Scale.

- Replaces the dev-grade SQLite/single-writer/monolith substrate (AUDIT-TRACE-1 gap #9). Horizontal scale must not weaken authority or tenant isolation.

---

## Canonical data / authority flow (locked)

```
USER OR WORLD EVENT
  → EMPLOYEE INTAKE / OWNED WORK            (L1)
  → DURABLE EMPLOYEE STATE                  (L1)
  → MEMORY + KNOWLEDGE + CASE CONTEXT       (L2, L0 case)
  → GENERATIVE / ADAPTIVE REASONING         (L4)
  → OPTIONAL LGGT CERTIFICATION             (L3, formalizable only)
  → FINALIS GOVERNANCE (authority/policy/approval)  (L0 governance)
  → CAPABILITY GRANT                        (L0 governance)
  → TOOL / PROVIDER / SANDBOX               (L8)
  → REAL OR SIMULATED EFFECT                (L8)
  → OUTCOME OBSERVER                        (L5)
  → COMPLETION OR NEXT ACTION               (L1/L5)
  → EXPERIENCE                              (L6)
  → CONTROLLED LEARNING                     (L6, gated)
```

Intelligence proposes; governance authorizes; effectors execute; observers verify; learning improves — each in a distinct layer, none collapsing into another.

> **Build-dependency vs runtime-data-flow (red-team clarification).** The downward dependency rule governs *build/contract* dependencies. The *runtime data flow* above (effect → observe → learn) moves information "upward" from L8 to L5/L6 — this does **not** violate the rule because L5 (Outcome Observer) and L6 (Learning) depend only on the **L1 event fabric's contract**, not directly on L8. Effects (real or already-simulated) are published as events; observers/learners consume the event contract. Module dependency stays downward (L5/L6 → L1); only decoupled event data flows up.
