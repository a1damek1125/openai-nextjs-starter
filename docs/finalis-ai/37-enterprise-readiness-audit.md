# Finalis AI — Enterprise Readiness Audit

> **Audit date**: 2026-07-07 · **Branch**: `claude/finalis-ai-enterprise-e2e-autofix`
> **Ground truth at audit time**: blueprint docs `00–36` + `47` in `docs/finalis-ai/`, plus an
> executable Python scaffold in `finalis/` with **102 tests passing**
> (`python3 -m pytest tests/ -q`), including a 20-step E2E HVAC flow simulation
> (`tests/test_e2e_mvp_flow.py`). **No database, no API server, no UI, no real integrations
> exist.** The repo's Next.js starter README mentions auth/Stripe/Postgres — those are
> marketing claims of the template, not wired code (there is no `package.json`).
>
> **Status vocabulary** (used honestly, per item):
> - **DESIGNED** — specified in a blueprint doc with enough detail to build; zero code.
> - **SCAFFOLDED** — a field/hook/interface exists in the `finalis/` scaffold, but the
>   enterprise behavior it enables is not enforced or implemented.
> - **IMPLEMENTED+TESTED** — working code in `finalis/` with passing tests on this branch.
>   *Scaffold-level only*: in-memory, no persistence, no network — not production-deployed.
> - **MISSING** — not designed, not coded, not mentioned in any blueprint doc.
>
> Severity: **Critical** (blocks any enterprise pilot), **High** (blocks GA / larger
> tenants), **Medium** (blocks scale or specific verticals), **Low** (hygiene).

---

## 1. Multi-tenancy

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| `tenant_id` on core entities | SCAFFOLDED | High | `tenant_id` exists on the `Case` aggregate root in `finalis/models.py` (child entities hang off the case). Carry it to every persisted table when the Postgres schema from `04` is built; make it `NOT NULL` everywhere. | Every table in the migration set has a `NOT NULL tenant_id`; a schema lint in CI fails on any table without it. |
| Tenant isolation (row-level security) | DESIGNED (`04`, `23`) | Critical | Postgres RLS policies keyed on `tenant_id`, set via `SET LOCAL app.tenant_id` per request/worker transaction. No application-code-only filtering. | A cross-tenant read/write test suite (tenant A queries tenant B's cases via every repository method) returns zero rows / raises; RLS enabled on 100% of tenant tables. |
| Per-tenant configuration (`BusinessProfile`) | SCAFFOLDED (autonomy defaults concept) / DESIGNED (`04`) | High | Implement `BusinessProfile` as the single per-tenant config root (autonomy defaults, price rules, quiet hours, data region, consent settings). | Config change takes effect on the next action decision without redeploy; config reads are audit-logged. |
| Per-tenant billing limits / quotas | DESIGNED (`23`) | High | Meter `CostEvent`s per tenant against plan entitlements; soft-warn at 80%, hard-stop non-critical actions at 100% (HITL actions never blocked silently). | Synthetic tenant hitting quota gets warning event at 80%, action refusal + owner notification at 100%; all recorded in audit. |
| Per-tenant audit partitioning/export | DESIGNED (`04`, `22`, `32`) | High | Partition `AuditEvent` by `tenant_id`; expose tenant-scoped export (see §4). | Export for tenant A contains zero events from tenant B, verified by test. |
| Noisy-neighbor / per-tenant rate fairness | DESIGNED (partially, `22`/`23`) | Medium | Per-tenant concurrency caps in the workflow engine (Temporal task-queue partitioning per `18`). | Load test: one tenant at 10x volume does not raise another tenant's P95 action latency beyond SLO. |

**Verdict**: single-tenant-shaped scaffold with the right seams. Nothing enforces isolation
today because nothing persists — RLS must land in the same sprint as the first migration
(S1 in `35`), not after.

---

## 2. Identity & access management

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| User roles (owner / operator / viewer) | DESIGNED (`04`, `13`) | High | RBAC enum on `User`; role checked at API layer and in approval flows (`HumanApproval.decided_by` must hold an authorized role). | Role matrix test: every API route × role has an expected allow/deny; viewer cannot approve; operator cannot change autonomy defaults. |
| Permission enforcement in approval flow | DESIGNED (`13` §1/§6); approval objects SCAFFOLDED (`finalis/models.py: HumanApproval`) | High | Wire role checks into the autonomy gate's approval resolution when the API layer exists. | An approval decided by an unauthorized user is rejected and audit-logged as a security event. |
| Session management / token lifetimes | MISSING as spec | Medium | Adopt the dashboard framework's session handling (NextAuth) with short-lived JWTs + refresh; document lifetimes. | Idle timeout and absolute lifetime configurable per tenant; revocation takes effect ≤60 s. |
| ABAC (attribute-based access) | MISSING (not designed) | Low | **Defer.** RBAC with per-tenant scoping covers the target segment (SMB/home-services). Revisit only if enterprise tenants demand case-level or region-level access rules. | Explicit ADR recording the deferral and the trigger condition for revisiting. |
| Service-to-service identity | DESIGNED (implied by `22` API keys) | Medium | Scoped API keys per integration + per worker; rotate via secret store. | Key rotation drill completes with zero downtime; old key rejected ≤5 min after rotation. |

**Verdict**: RBAC is designed but 0% implemented. Nothing in the scaffold checks *who* a
human approver is — acceptable for a domain-logic scaffold, disqualifying for any deployment.

---

## 3. Enterprise authentication (SSO)

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| SSO / OIDC for dashboard | **MISSING from all blueprint docs** — flagged as a documentation gap | Critical (for enterprise tenants) / High (for SMB MVP) | Phase 2: NextAuth with OIDC (Google Workspace / Microsoft Entra) for the Command Center. | Operator logs in via tenant IdP; local-password path can be disabled per tenant. |
| SAML for larger tenants | MISSING | Medium (Phase 3+) | Buy, don't build: WorkOS-class provider (WorkOS/Stytch B2B) bridging SAML→OIDC. | One pilot enterprise tenant completes SAML login + SCIM-less JIT provisioning. |
| MFA | MISSING | High | Enforce at IdP where SSO is used; TOTP fallback for password tenants. | MFA required for any role that can approve HITL actions or change autonomy levels. |
| API keys for programmatic access | DESIGNED (`22`) | High | Hashed-at-rest, prefix-identifiable keys, per-key scopes, last-used tracking. | Key with `read:cases` scope cannot POST; key list shows last-used; revocation immediate. |
| SCIM / directory sync | MISSING | Low | Defer to Phase 3+ alongside SAML (same vendor covers both). | ADR recorded. |

**Verdict**: the single largest *documentation* gap found by this audit — no blueprint doc
mentions SSO at all. Add an auth section to `22` or a new doc before Phase 2 build starts.

---

## 4. Audit & compliance

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| Append-only hash-chained audit log | **IMPLEMENTED+TESTED** (`finalis/audit.py`; tamper-detection test passes in `tests/test_autonomy_audit.py`) | — | Port the chain semantics (`hash_prev` linkage, verify walk) onto the `AuditEvent` table from `04`; anchor periodic chain heads to external WORM storage. | Existing scaffold tests stay green against the DB-backed implementation; mutating any historical row breaks `verify()`; chain verification runs nightly in CI/ops. |
| AI action log (every autonomous action recorded) | SCAFFOLDED (gate + transition events emitted into the audit log in scaffold flows) | High | Enforce "no action without an audit event" as an invariant at the action-execution layer, not by convention. | Coverage test: executing any `Action` type without a paired `AuditEvent` fails the invariant check. |
| Human approval log | SCAFFOLDED (`HumanApproval` objects created by the autonomy gate; exercised in tests) | High | Persist approvals with decider identity, timestamps, edit-distance-from-draft (`13` §L2). | Every ALWAYS_HITL action in production has a linked approved `HumanApproval` or was never executed. |
| Decision history / DecisionBrief lineage | SCAFFOLDED (events exist in scaffold) / DESIGNED (`09` §7) | Medium | Supersede-chain on briefs; every claim carries an `EvidenceReference`. | Unlinked-claim rate ≈0 on the golden set (`15`). |
| Audit export (tenant-scoped, machine-readable) | DESIGNED (`22`, `32`) | High | `GET /audit/export` streaming NDJSON with chain-verification manifest; tenant-scoped (see §1). | Exported file re-verifies the hash chain offline with a published verifier script. |
| `audit_id` correlation on API responses | DESIGNED (`22`) | Medium | Return `audit_id` on every mutating API response; propagate as trace attribute. | Support can go from a customer-reported `audit_id` to the full decision context in ≤2 minutes. |
| Retention of audit records | DESIGNED (`04` retention table: long, e.g. 7y config) | Medium | Immutable partitioned storage with legal-hold flag. | Retention job never deletes audit-class rows inside the configured window; legal hold blocks deletion. |

**Verdict**: this is the strongest enterprise area — the tamper-evident chain is the one
enterprise control that is already real, executable code with a passing tamper test. The gap
is persistence and export, not design or core logic.

---

## 5. Privacy & data protection

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| PII classification/tagging on entities | DESIGNED (`04` — per-entity retention/privacy notes + summary table) | High | Column-level PII annotations in the schema; generate the redaction/erasure map from annotations, not by hand. | Every column in the schema is classified; unclassified columns fail CI. |
| Retention policies (audio 90d default, case-linked media 12–24 mo, audit long) | DESIGNED (`04` retention table) | High | Scheduled retention worker; per-tenant overrides via `BusinessProfile`. | Fixture tenant with 1-day retention shows media gone and audit intact after the sweep; deletions themselves are audit-logged. |
| Right to erasure (GDPR Art. 17) / DSAR export | DESIGNED (`04`, `16` §3.1) | Critical (EU launch) | DSAR endpoints: export + erasure that removes PII payloads while preserving audit skeleton (references, hashes) and opt-out suppression records. | Erasure request leaves zero recoverable PII for the party across DB, object storage, and search indexes; opt-out survives erasure (tested). |
| Data residency (`BusinessProfile.data_region`) | DESIGNED (`04`) | Medium | Region-pinned storage + region-aware model endpoints; start EU-only if that is the launch market. | Tenant with `data_region=eu` has zero data rows/objects in non-EU regions (verified by inventory audit). |
| Call-recording consent | DESIGNED (`06`, `16` §3.2) | High | Per-jurisdiction consent config; announce-and-consent flow in the voice pipeline; suppress recording where required. | Two-party-consent jurisdiction fixture: no audio persisted without recorded consent event. |
| Messaging consent / opt-in (TCPA-style) & STOP | DESIGNED (`12`, `16` §3.3); opt-out honored in scaffold completion loop (`opted_out` flag gates sends, tested) | High | Channel-level opt-in records; global STOP already modeled in scaffold policy — wire to real channel webhooks. | STOP on any channel halts all outbound on that channel ≤1 min; suppression list survives erasure. |
| PII redaction in logs / LLM prompts | DESIGNED (`16` §4.4) — no spec for structured logging exists (see §8) | High | Redaction middleware at the logging layer + prompt-construction layer; deny-by-default field allowlist for prompts. | Log-scan job finds zero raw phone numbers/emails in a 24h production log sample. |
| Consent/processing records (Art. 30) | DESIGNED (implied `16` §3) | Low | Generate the processing-activity record from the PII classification map. | Document exists and matches deployed schema version. |

**Verdict**: unusually well-designed on paper (per-entity retention notes are already in the
data model doc); 0% implemented. Nothing can leak today only because nothing persists or
transmits.

---

## 6. Security

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| No secrets in repo | **TRUE — verified** (no `.env`, no key files; `set-api-key.png`/`remove-api-key.png` are starter-template screenshots, not credentials; scaffold requires no API keys) | — | Keep it true: add secret-scanning (gitleaks/GitHub secret scanning) to CI before any integration code lands. | CI fails on any committed credential pattern. |
| Secrets by reference (`IntegrationAccount` tokens in external secret store, never DB) | DESIGNED (`04`) | High | Vault/KMS-backed secret store; DB stores references only. | Schema audit: no token/secret column in any migration; secret access is logged. |
| Prompt/document injection threat model | DESIGNED (`08`, `13` — mapped against OWASP LLM01 / agentic threat patterns; `16` §1.7) | High | Input provenance labeling (web/client-doc content is never instruction-privileged), output validators (`13` §3), injection red-team suite in Evaluation Lab. | Injection fixture set (hostile web pages + hostile PDFs) produces zero policy-violating actions in CI. |
| Browser sandbox for WebScout | DESIGNED (`08`, `16` §4.5) | High | Playwright in a locked-down container (no cloud metadata route, egress allowlist), a11y-tree interaction only. | Sandbox escape checklist passes; WebScout cannot reach internal networks (tested). |
| WebScout hard restrictions (robots/paywall/no-login policy) | IMPLEMENTED+TESTED at policy level (`finalis/webscout.py` raises `RestrictionViolation`; restriction tests pass) | Medium | Keep the policy layer as the mandatory choke point in front of the real browser. | Real fetcher cannot be invoked except through the policy layer (enforced by construction + test). |
| Webhook signing (inbound + outbound) | DESIGNED (`22`) | High | HMAC-SHA256 signatures with timestamp + replay window on all webhooks, both directions. | Unsigned/stale/replayed webhook rejected with 401 and audit event; partner-facing verification doc published. |
| Rate limiting — follow-up/anti-spam | **IMPLEMENTED+TESTED** in scaffold (`finalis/completion_loop.py`: quiet hours, min inter-touch interval, max attempts, opt-out; tests pass) | — | Preserve these hard guarantees as non-overridable when the cadence engine goes durable. | Existing anti-spam tests stay green on the production engine; no config can exceed `max_attempts`. |
| Rate limiting — API | DESIGNED (`22`) | Medium | Token-bucket per key + per tenant at the gateway. | 429 with `Retry-After` under synthetic burst; per-tenant fairness holds. |
| Dependency / supply-chain scanning | **MISSING** | Medium (Low today — scaffold has zero runtime deps; rises to High the day real deps land) | `pip-audit` + Dependabot (and npm audit once a UI exists) in CI; fail on known-critical CVEs. | CI blocks merge on critical CVE in any locked dependency. |
| Encryption at rest / in transit | DESIGNED (`04` notes, `16` §4) | High | Managed Postgres + object-store encryption; TLS everywhere; document key management. | Config audit confirms encryption on all data stores; TLS-only endpoints. |

**Verdict**: strong threat-model coverage in docs, one genuinely implemented control
(anti-spam hard guarantees) and one verified hygiene fact (no secrets). Everything
network-facing is still paper.

---

## 7. Reliability & operations

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| Durable workflows | DESIGNED (`18`: Temporal for case processes, LangGraph for agent steps) — restart-survival **simulation TESTED in scaffold** (state machine + completion loop resume from persisted-in-memory state across a simulated restart) | Critical | Temporal workflows for the case lifecycle; the scaffold state machine becomes the workflow's legality oracle. | Kill a worker mid-case in staging; case resumes with no duplicate outbound action and no illegal transition. |
| Retry / idempotency / DLQ | DESIGNED (`22`: idempotency keys, event delivery semantics) | Critical | Idempotency keys on all mutating endpoints; at-least-once consumers with dedup; DLQ + replay tooling. | Duplicate webhook delivery produces exactly one action; poisoned event lands in DLQ with alert, replayable after fix. |
| Backup / disaster recovery | **MISSING from all docs** — flagged | Critical | Standard managed-Postgres PITR (e.g. 7–35 day window) + daily snapshots + object-store versioning; document RPO/RTO (suggest RPO ≤5 min, RTO ≤4 h initially); quarterly restore drills. | A restore drill recovers a full tenant to a point in time within the stated RTO; audit chain re-verifies post-restore. |
| Health checks / readiness probes | **MISSING** | High | `/healthz` (liveness) + `/readyz` (DB, queue, model-provider dependency checks) on every service; wire to orchestrator restarts and load balancer. | Dependency outage flips readiness within 30 s; orchestrator stops routing to the instance. |
| Model/provider outage degradation | DESIGNED (`16` §1.5: fallback providers, degrade-to-capture mode) | High | Provider failover for LLM/STT/TTS; voice degrades to "take a message" mode rather than failing calls. | Chaos test: primary LLM provider blocked → inbound calls still captured, cases created, humans notified. |
| Graceful shutdown / zero-downtime deploy | MISSING as spec | Medium | Drain in-flight workflow activities on SIGTERM; rolling deploys. | Deploy during synthetic call load drops zero cases. |
| Incident response runbook | MISSING | High | On-call rotation doc, severity matrix, kill-switch procedure (§9), customer-comms templates, postmortem template. | A game-day incident is handled end-to-end using only the runbook. |

**Verdict**: the design bets (Temporal, idempotent events) are right and the scaffold proves
the resume logic is sound, but **backup/DR and health checks are absent even from the
documentation** — the two most standard enterprise checklist items in this audit's MISSING
column.

---

## 8. Observability

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| Metrics plan (business + system) | DESIGNED (`15` metric definitions, `21`) | High | Prometheus/OpenTelemetry metrics keyed by tenant + case-type; Evaluation Lab metrics (`15`) emitted from production paths. | Dashboards show per-tenant action volume, approval rates, escalation rates, cost per case. |
| Distributed tracing | DESIGNED (`15`/`21`) | Medium | OTel traces spanning webhook → workflow → model call → outbound action; `audit_id` as span attribute. | One trace covers an entire inbound-call-to-follow-up flow in staging. |
| Voice TTFA instrumentation | DESIGNED (`21` — available out-of-the-box in Pipecat 1.5 per the tech review) | Medium | Enable Pipecat's TTFA/latency metrics from day one of voice work; export P50/P95 against `06` targets. | First 100 staging calls produce a TTFA distribution report; targets in `06` become measurements. |
| Structured logging | **MISSING as spec** | High | JSON logs with mandatory fields (`tenant_id`, `case_id`, `audit_id`, `trace_id`, severity); PII-redacting formatter (§5). | Log queries by `case_id` reconstruct a case's system-side story; redaction scan passes. |
| Alerting | Partially DESIGNED (`15` names review cadences and thresholds; no paging spec) | High | Alert rules for: chain-verification failure, DLQ depth, approval-queue age, cost-budget breach, provider error rates; route to on-call. | Each alert has a runbook link; synthetic breach pages within 2 min. |
| SLO definitions | Partially DESIGNED (voice latency targets in `06`; no service SLOs) | Medium | Define SLOs for inbound answer rate, action latency, dashboard availability. | SLO doc exists; error budgets reported monthly. |

**Verdict**: measurement *targets* are unusually well specified (Evaluation Lab is the
best-specified module in `34`); the operational telemetry to observe a running system —
structured logs, alerts, SLOs — has no spec at all.

---

## 9. Cost controls

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| Cost model / unit economics | DESIGNED (`23` — per-case cost estimates by channel/model) | — | Keep `23` as the rate-card source of truth; refresh quarterly. | Estimated vs. actual per-case cost within ±25% after first 100 real cases. |
| Cost metering (`CostEvent` / `CostRateCard`) | DESIGNED (`04` entities, `23`) | High | Emit a `CostEvent` from every metered operation (LLM call, minute of voice, OCR page, message); aggregate per tenant/case. | Every metered operation type produces events; per-case cost visible in Command Center. |
| Budgets & limits per tenant | DESIGNED (`23`) | High | Plan entitlements + soft/hard budget thresholds (see §1 quotas). | 80%/100% threshold behavior tested per §1. |
| Kill switch | **MISSING** — flagged | Critical | Two-layer switch tied to the existing autonomy gate (`finalis/autonomy.py`): (a) **per-tenant, per-action-type** switch that forces effective autonomy to L1 (observe-only), (b) **global** switch that halts all autonomous outbound actions platform-wide. Must be operable from the ops console and CLI, take effect on the *next* gate evaluation (no deploy), and be audit-logged with actor + reason. | Flipping the global switch stops 100% of autonomous outbound actions ≤60 s in staging load test; per-tenant switch affects only that tenant; both events appear in the audit chain; in-flight HITL approvals are preserved, not lost. |
| Runaway-loop protection | Partially IMPLEMENTED (scaffold `max_attempts` + anti-spam caps bound follow-up loops) | Medium | Add per-case and per-tenant hourly action-count circuit breakers on top of cadence caps. | Fuzzed pathological case cannot exceed N actions/hour; breaker trip is audit-logged and pages. |
| Model-spend anomaly detection | MISSING | Low | Daily spend-per-tenant anomaly alert (simple z-score is enough initially). | 3x day-over-day spend spike alerts within the day. |

**Verdict**: the money *model* is designed; the money *brakes* are not. The kill switch is
cheap to build precisely because the autonomy gate already exists as the single choke point —
build it there, first.

---

## 10. Legal & operational safety

| Item | Status | Severity | Recommended implementation | Acceptance criteria |
|---|---|---|---|---|
| HITL for risky actions (autonomy gate + ALWAYS_HITL) | **IMPLEMENTED+TESTED** (`finalis/autonomy.py`: `ALWAYS_HITL = {send_out_of_rule_price, grant_discount_beyond_bound, send_legal_content, sign_contract, take_payment}`; gate tests pass, incl. HUMAN_REVIEW_REQUIRED capping at L2) | — | Keep the gate as the sole path to action execution in production; make bypass impossible by construction (no action executor accepts an ungated request). | Static/architectural check: no code path executes an `Action` without a `GateResult`; ALWAYS_HITL set is config-extensible but never reducible below the shipped floor. |
| `sign_contract` / `take_payment` never autonomous | **IMPLEMENTED+TESTED** (in ALWAYS_HITL; covered by gate tests even at L5) | — | Preserve as a hard invariant test in CI forever. | L5 case requesting `sign_contract` yields `HumanApproval`, never execution — test stays green. |
| No legal advice boundary | DESIGNED (`03`/`10`/`13` prohibited actions; `16` §3.5) | High | Output validator blocking legal-conclusion language; contract analysis always labeled "informational, not legal advice"; `send_legal_content` already in ALWAYS_HITL. | Red-team prompt set produces zero unlabeled legal conclusions; validator failures escalate. |
| No medical advice | DESIGNED (prohibited-action class, `13`) | Medium | Same validator family; out-of-domain detection routes to human. | Medical-flavored fixture inquiries are declined + escalated. |
| No autonomous financial commitment | DESIGNED (`13` L4/L5 bounds) + partially TESTED (out-of-rule price and discount-beyond-bound in ALWAYS_HITL; rule-covered quote bounds designed) | High | Implement the price-rule validator (`13` §3) so "rule-covered" is machine-checkable before any L4 quote-send. | Quote outside `price_rules` or above `high_value_threshold` is gated at every autonomy level (property-based test). |
| AI disclosure ("caller knows it's AI") | DESIGNED (`16` §3.6) | Medium | Mandatory disclosure line in voice/message openers; per-jurisdiction config. | Every outbound first-contact transcript in staging contains the disclosure. |
| Scraping limits | **IMPLEMENTED+TESTED at policy level** (`finalis/webscout.py` hard restrictions; violation tests pass) | — | Bind the same policy object in front of the real browser (§6). | Policy tests re-run unchanged against the production WebScout. |
| Anti-spam / harassment guarantees | IMPLEMENTED+TESTED (scaffold cadence caps, quiet hours, opt-out — see §6) | — | Carry into the durable follow-up worker as non-overridable floors. | Guarantees hold under fuzzed cadence configs. |
| Insurance / liability posture | MISSING (business item) | Low | E&O/tech liability review before GA; align ToS with the prohibited-action list. | Signed-off ToS referencing the enforced action boundaries. |

**Verdict**: the strongest area relative to industry norms. The most dangerous actions are
already structurally impossible to automate in the scaffold, with tests — the remaining work
is keeping that property true across the persistence/API layers as they appear.

---

## Top 12 enterprise gaps (severity-ranked)

| # | Gap | Severity | Why it ranks here | First action |
|---|---|---|---|---|
| 1 | **SSO (OIDC/SAML)** | Critical | Absent from every blueprint doc; enterprise deal-breaker and a *design* gap, not just a build gap. | Add auth spec (NextAuth+OIDC Phase 2, WorkOS-class SAML Phase 3+) to `22` or a new doc `38`. |
| 2 | **Backup / DR** | Critical | Not mentioned anywhere in docs; unrecoverable data loss is existential. | One-page DR spec: Postgres PITR, snapshot cadence, RPO/RTO, restore-drill schedule. |
| 3 | **Kill switch** | Critical | An autonomous-action product with no emergency stop; cheap to build on the existing autonomy gate. | Per-tenant + global action kill switch tied to the gate; ops-console + CLI. |
| 4 | **RLS implementation (tenant isolation)** | Critical | Designed but nothing enforces it; must ship with the first migration, retrofit is risky. | RLS policies + cross-tenant test suite in sprint S1. |
| 5 | **Health checks** | High | No liveness/readiness anywhere; blocks any orchestrated deployment. | `/healthz` + `/readyz` convention in the service template. |
| 6 | **Structured logging (with PII redaction)** | High | No log spec; observability and privacy both depend on it. | JSON log schema + redacting formatter as a shared library. |
| 7 | **DSAR endpoints (export + erasure)** | High | GDPR-critical for the EU-leaning target market; designed but unimplemented. | Build export first, erasure second, both audit-logged. |
| 8 | **Webhook signing implementation** | High | Designed in `22`; unsigned webhooks are an injection/forgery vector on day one of integrations. | HMAC + replay-window middleware in the API gateway. |
| 9 | **PII redaction in logs/prompts** | High | Overlaps #6 but distinct control: prompts to third-party models are an egress path. | Deny-by-default prompt field allowlist. |
| 10 | **Per-tenant quota enforcement** | High | Metering is designed; without enforcement one tenant can burn the platform budget. | Wire `CostEvent` aggregates to soft/hard limits. |
| 11 | **Dependency scanning** | Medium | Zero runtime deps today (low exposure) but must exist before the first real dependency lands. | `pip-audit` + Dependabot in CI this week — near-zero effort. |
| 12 | **Incident response runbook** | Medium | No on-call/severity/comms procedure; matters the first week real tenants exist. | Runbook doc + one game-day before pilot. |

---

## Bottom line

- **What is enterprise-real today**: the tamper-evident audit chain, the HITL autonomy gate
  with a hard never-autonomous action set, anti-spam hard guarantees, and WebScout policy
  restrictions — all implemented and covered by the 102-test suite, at scaffold (in-memory)
  level.
- **What is designed but not built**: multi-tenancy enforcement, RBAC, privacy/retention
  machinery, webhook signing, durable workflows, metering.
- **What is missing even from the design**: SSO, backup/DR, health checks, kill switch,
  structured logging, dependency scanning, incident response. Three of these (DR, kill
  switch, health checks) are standard checklist items whose absence from 38 documents is
  itself the finding.
- No enterprise pilot should begin before gaps #1–#5 are closed; #11 should be closed
  immediately because it costs nearly nothing.
