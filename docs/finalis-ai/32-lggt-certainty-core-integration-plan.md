# Finalis AI — LGGT "Finalis Certainty Core" Integration Plan

> **Status: NOT PRESENT IN THE BLUEPRINT.** Docs `00`–`23` contain **no** references to
> LGGT, CertaintyCore, or a certificate/proof system (verified by search). LGGT is the
> founder's separate certainty/verification system, capable of certifying AI decisions with
> proofs/certificates. This document adds a **forward-compatible integration plan** without
> making the MVP depend on LGGT in any way. Everything here is interface and schema design —
> **no LGGT runtime is assumed to exist, be stable, or be available for the MVP.** The repo
> contains zero application code; this plan, like the rest of the blueprint, is specification.

---

## 1. Recommendation: Option B — placeholder/interface now, runtime later

**Decision: build LGGT-shaped seams and storage into the MVP now; integrate the actual LGGT
runtime later.**

### 1.1 Decision matrix

| Option | Description | Effort now | Risk | Benefit |
|---|---|---|---|---|
| **A — No LGGT at all** | Ignore LGGT entirely; retrofit later if needed | None | **High**: MVP data shapes (facts, decisions, evidence) crystallize without certification in mind; retrofitting means migrating every decision record, re-keying evidence, and re-plumbing the Orchestrator — the classic incompatible-data-shapes trap | None now; expensive later |
| **B — Placeholder/interface now, runtime later** | Define adapter interfaces, an LGGT-compatible fact/decision/certificate schema, and a pass-through gate; MVP ships a NullAdapter | **Low** (interfaces + one jsonb stamp + reserved schema) | **Low**: worst case the interfaces sit unused; no runtime dependency, no latency, no new failure mode | Every MVP decision is already stored in certifiable shape; LGGT integration becomes an adapter swap, not a migration |
| **C — Integrate LGGT runtime into the MVP** | Certify decisions in the MVP critical path | High | **High**: MVP blocks on an unproven external runtime — its availability, latency, and API stability all become MVP launch risks | Full certification day one (if LGGT is ready — unverified) |
| **D — Build certainty features natively first** | Re-implement proof/certificate machinery inside Finalis, converge with LGGT later | Very high | **High**: duplicates the founder's own system, guarantees a painful reconciliation, and diverts the MVP team from the actual product (`14`) | Independence nobody asked for |

**Conclusion: Option B.**

### 1.2 Justification

- **Versus A**: the risk is not "we lack proofs at MVP" (acceptable) but that *data shapes
  drift*. If `ExtractedField`, decision records, and audit linkage are not designed to be
  fact-normalizable, Phase-2 LGGT integration becomes a data migration across every tenant's
  case history instead of an adapter deployment. The placeholder costs almost nothing now
  and eliminates that cliff.
- **Versus C/D**: the MVP must not block on an unproven runtime. `14` scopes the MVP to the
  headline loop (answer, intake, follow up, never drop a case); `13` already provides the
  MVP-grade safety story (autonomy levels, escalation, validators, abstention). Making
  quote-sends wait on an external certification service adds a hard availability and latency
  dependency the MVP cannot justify — and D additionally burns the team rebuilding what LGGT
  already is.
- **The blueprint is already LGGT-shaped.** `02`'s evidence-first architecture (design
  principle: every AI claim carries an `EvidenceReference`; the Quality Worker is a
  secondary critic), `05`'s deterministic auditable scoring with persisted input vectors and
  weight versions, and `13` §5's hash-chained AuditEvent log are exactly the substrate a
  certainty system certifies over. Option B mostly *names the seams that already exist* and
  reserves the shapes LGGT will need. That is the strongest evidence the placeholder is
  cheap: we are formalizing an alignment, not bolting on a foreign system.

---

## 2. Component design (interfaces/contracts only — no runtime)

All components below are **interfaces**. The MVP implements exactly one of them with real
logic (the NullAdapter stamp); everything else is a contract for Phase 2+. Type notation is
illustrative TypeScript; the normative content is the field lists.

### 2.1 `CertaintyCoreAdapter` — the single seam

The only place Finalis touches certainty machinery. Nothing else in the codebase may import
LGGT concepts directly; the Orchestrator, workers, and API see only this interface.

```ts
interface CertaintyCoreAdapter {
  /** Called for every decision the Orchestrator applies (NBA execution, transition,
   *  risk flag, escalation, quote send). Must be fast and must never block the MVP path. */
  certify(req: CertifyRequest): Promise<CertaintyStamp>;

  /** Phase 2+: fetch a previously issued certificate. */
  getCertificate(id: string): Promise<LGGTCertificate | null>;

  /** Capability probe — lets callers/UI know whether real certification is active. */
  mode(): "heuristic" | "certified";
}

interface CertifyRequest {
  decision_ref: DecisionRef;      // what is being decided (see 2.8 join)
  facts: FactRecord[];            // from FactBuilder (2.2)
  policy_id?: string;             // from PolicyCompiler (2.3), Phase 2+
  context: { case_id, tenant_id, autonomy_level, scores_snapshot };
}

type CertaintyStamp =
  | { mode: "heuristic"; audit_id: string }                       // MVP (NullAdapter)
  | { mode: "certified"; audit_id: string; certificate_id: string;
      verdict: "pass" | "fail" | "abstain"; confidence: number }; // Phase 2+
```

**MVP implementation — `NullAdapter`**: performs no verification, calls no external system,
and stamps `certainty: { mode: "heuristic", audit_id }` (jsonb) onto the decision's
AuditEvent payload, where `audit_id` is the AuditEvent's own id (see 2.8). Cost: one jsonb
field. Effect: every MVP decision is already addressable by the certainty layer, and the
UI/API can honestly distinguish "heuristically decided" from "certified" from day one.

### 2.2 `FactBuilder` — normalize case facts to LGGT-compatible fact records

```ts
interface FactBuilder {
  buildFacts(case_id: string, claim_scope: DecisionRef): FactRecord[];
}

interface FactRecord {
  fact_id: string;            // deterministic hash of (source_type, source_id, locator, value)
  subject: string;            // case-scoped entity, e.g. "case:{id}/field:boiler_model"
  predicate: string;          // normalized field key / claim type
  value: unknown;             // typed value
  confidence: number;         // 0–1
  provenance: ProvenanceRef;  // where it came from (mapping below)
  observed_at: string;        // ISO timestamp
  tenant_id: string;
}
```

**Field mapping from existing entities (`04`)** — this is the compatibility payload of
Option B; these mappings are lossless over what the MVP already stores:

| `FactRecord` field | From `ExtractedField` | From `EvidenceReference` | From `Source` (WebScout) |
|---|---|---|---|
| `subject` | `document_id` + case linkage | `claim_id` (polymorphic) | `case_id` |
| `predicate` | `field_key` | `source_type` + claim type | `extracted_facts` key |
| `value` | `field_value` (+ `data_type`) | `snippet` | `extracted_facts` value |
| `confidence` | `confidence` (= `ocr_q · extraction_q · source_q · consistency_q`, `05` §6) | `confidence` | `confidence` (with `trust_score` → `Source_q`) |
| `provenance.source_type` | `"document_region"` | `source_type` (message \| call_segment \| document_region \| web_source) | `"web_source"` |
| `provenance.source_id` | `document_id` | `source_id` | `Source.id` (`url` retained) |
| `provenance.locator` | `page` + `bbox` | `locator` (page+bbox \| call ts range \| url+snippet) | `url` + `date_checked` |
| `observed_at` | row `created_at` | row `created_at` | `date_checked` |

MVP obligation: none at runtime. Design obligation: **do not add a fact-bearing field to
`04` that cannot be expressed in this record** (concretely: every fact-bearing entity keeps
explicit source, locator, confidence, and timestamp — which `04` already mandates).

### 2.3 `PolicyCompiler` — playbook rules as checkable policies (interface only)

```ts
interface PolicyCompiler {
  /** Compile a versioned IndustryPlaybook (+ BusinessProfile thresholds) into a
   *  checkable policy bundle. Pure function of (playbook version, profile version). */
  compile(playbook: IndustryPlaybook, profile: BusinessProfile): CompiledPolicy;
}

interface CompiledPolicy {
  policy_id: string;
  policy_version: string;     // = playbook.version + profile threshold snapshot
  rules: PolicyRule[];        // e.g. "quote requires all blocks_quote items received",
                              // "outbound requires outside quiet_hours",
                              // "price within price_rules bounds"
}
```

Playbooks are already versioned, tenant-tunable rule sets (`04` `IndustryPlaybook`, `22`
`PATCH /playbooks` creates immutable versions), and scores already persist `weights_version`
— so policy identity is already reproducible. Phase 2 gives these rules a checkable form
LGGT can verify decisions against; the MVP just keeps playbook versioning immutable (already
specified).

### 2.4 `EvidenceBinder` — bind evidence chains to a claim

This component **already effectively exists** as `04`'s `EvidenceReference` — the universal
citation object. The interface formalizes "collect the full chain for one claim":

```ts
interface EvidenceBinder {
  bind(claim_id: string): EvidenceBundle;
}

interface EvidenceBundle {
  claim_id: string;
  evidence: FactRecord[];       // EvidenceReferences mapped per §2.2 table
  weakest_confidence: number;   // min over chain — feeds abstention (§2.9)
  complete: boolean;            // every claim hop has at least one reference
}
```

Mapping: `EvidenceReference.claim_id` → `EvidenceBundle.claim_id`;
`(source_type, source_id, locator, snippet, confidence)` → one `FactRecord` each via §2.2.
The `13` §4 rule "a claim with no evidence ref is treated as unverified and cannot drive an
autonomous action" is exactly `complete == false` — the binder gives that rule a name LGGT
can consume.

### 2.5 `ProofGate` / `ActionGate` — pre-action hook in the Orchestrator

`13` §1 already defines a single choke point where every action passes the autonomy gate
(`effective_level = min(case, tenant-per-action-type, state_cap)`), and `22` §2.2 routes
every `action.proposed` through guardrail validators. The ActionGate is **one more validator
in that existing chain** — same position, same fail-fast semantics:

```ts
interface ActionGate {
  /** Runs after autonomy gating and 13 §3 validators, before execution. */
  check(action: ProposedAction, stamp: CertaintyStamp): GateResult;
}

type GateResult =
  | { allow: true }
  | { allow: false; reason: string; route: "human_approval" | "block" };
```

**MVP implementation: pass-through + log.** Always `{ allow: true }`; writes the
`CertaintyStamp` into the action's AuditEvent. Phase 2: for the certified action classes
(§3, Phase 2), `verdict: "fail"` routes to `HumanApproval` (never silent block — consistent
with `22`'s 202-approval pattern) and `verdict: "abstain"` behaves like low confidence
(§2.9). The gate may only ever make the system *more* conservative than `13` — it can add a
human approval, never bypass one.

### 2.6 `Proof-to-Plain-Language Renderer`

```ts
interface ProofRenderer {
  /** Turn a certificate into owner-readable text, in the DecisionBrief voice (09 §7):
   *  what was decided, which facts supported it, which policy version it satisfied,
   *  and what was NOT verified. Localized per tenant language. */
  render(cert: LGGTCertificate, audience: "owner" | "auditor"): RenderedProof;
}

interface RenderedProof {
  summary: string;              // ≤ 3 sentences, non-technical
  supported_by: { fact: string; source_label: string; evidence_ref_id: string }[];
  not_verified: string[];       // honest gaps — mirrors 13 §4 "found vs. couldn't verify"
  policy_line: string;          // "checked against Playbook vX policy Y"
}
```

MVP: unimplemented (nothing to render). The contract exists so Phase-2 UI work (`11`
evidence chips, brief surfaces) can slot rendered proofs where confidence chips already go.

### 2.7 `LGGTCertificate` — data-model addition, **marked Phase 2**

To be added to `04-data-model.md` as a Phase-2 entity (reserved now, not created in MVP
migrations):

```
### `LGGTCertificate`  (Phase 2 — reserved, no MVP table)
- id            uuid
- audit_id      FK → AuditEvent.id of the certified decision (the join, §2.8)
- decision_ref  jsonb  { kind: action|transition|risk_flag|escalation|missing_info,
                         entity_id, case_id }
- facts         jsonb  FactRecord[] (§2.2) — the exact fact set certified
- policy_version text  (§2.3 CompiledPolicy.policy_version)
- verdict        enum  pass | fail | abstain
- confidence     numeric 0–1
- proof_blob     bytea/jsonb  opaque LGGT proof object (format owned by LGGT, versioned)
- created_at     timestamptz
- Indexes: (tenant_id, audit_id), (tenant_id, decision_ref->>case_id)
- Immutable, append-only — same regime as AuditEvent.
```

### 2.8 `audit_id` — the join (already effectively exists)

The hash-chained `AuditEvent` log (`13` §5, `04`) is already an immutable, per-decision,
tamper-evident identifier space — precisely what a certificate must bind to. **Definition:
`audit_id := AuditEvent.id` of the event that recorded the decision** (the
`action.executed` / `case.state_changed` / `escalation.triggered` event). The join:

```
LGGTCertificate.audit_id  →  AuditEvent.id
AuditEvent.payload.certainty = { mode, audit_id, certificate_id? }   (stamped by adapter)
```

Because the AuditEvent chain is tamper-evident via `hash_prev`, a certificate over an
`audit_id` inherits integrity: the certified decision provably wasn't rewritten after
certification. No new MVP field beyond the `certainty` jsonb stamp (§2.1).

### 2.9 Abstention manager — maps to existing `θ_conf` abstention (`05` §6)

The MVP already has an abstention mechanism: `Confidence < θ_conf` (default 0.6) →
must not assert, surface as unverified, cannot drive autonomous client-facing action, API
returns `422 confidence_below_threshold` (`22` §1.4). The interface names it:

```ts
interface AbstentionManager {
  evaluate(claim: EvidenceBundle): "assert" | "abstain";
}
```

- **Phase 1 implementation = the existing rule**: `weakest_confidence < θ_conf ⇒ abstain`.
- **Phase 2+**: LGGT strengthens it — `verdict: "abstain"` from certification joins the
  heuristic rule (abstain if *either* says abstain; LGGT can only tighten, never loosen —
  the same one-way-conservative principle as the ActionGate §2.5).

### 2.10 Future LGGT endpoints — reserved paths, Phase 2+

Reserved in the `22` API surface; **not implemented in MVP**, listed so nothing else claims
the paths:

| Method & path | Phase | Purpose |
|---|---|---|
| `POST /v1/certainty/certify` | 2+ | Submit a `CertifyRequest` (§2.1); returns stamp + certificate id. Internal/Orchestrator-facing first; server-to-server key scope `certainty`. |
| `GET /v1/certainty/certificates/{id}` | 2+ | Fetch an `LGGTCertificate`; `?render=plain` returns the §2.6 rendering. Read-only, any role; access audit-logged. |

Reserved event types (envelope per `22` §2.1): `certainty.certified`,
`certainty.abstained`, `certainty.check_failed` — consumed like `quality.check_failed`
(block/escalate path).

---

## 3. Phased rollout

### Phase 1 — Placeholder + LGGT-compatible storage (MVP, now)

Scope: `NullAdapter` stamp; `certainty` jsonb on decision AuditEvents; §2.2 mapping honored
by any new fact-bearing entity; §2.7 schema reserved (documented, no table); §2.10 paths
reserved; ActionGate present as pass-through validator in the `13` §3 chain.

**Acceptance criteria:**
1. 100% of decision AuditEvents (`action.executed`, `case.state_changed`,
   `escalation.triggered`) carry `certainty: { mode: "heuristic", audit_id }` with
   `audit_id` equal to their own event id.
2. Zero runtime calls to any external certainty system; removing the NullAdapter's stamp
   line is the *only* code change that would alter behavior (proven by a no-op latency/path
   test: adapter on vs. off differs only by the stamp).
3. A round-trip test converts every fixture `ExtractedField`, `EvidenceReference`, and
   `Source` row into a `FactRecord` per §2.2 and back without information loss.
4. `04` and `22` carry the Phase-2 reservations (`LGGTCertificate`, `/certainty/*`), and no
   MVP feature occupies those names.
5. MVP ship date has zero dependency on LGGT availability (trivially true — nothing calls it).

### Phase 2 — Certify selected actions

Scope: real `CertaintyCoreAdapter` backed by the LGGT runtime; `PolicyCompiler` producing
checkable policies from playbook versions; ActionGate enforcing verdicts (fail → HumanApproval,
abstain → `θ_conf`-equivalent handling); certificates persisted and rendered. **Certified
action classes (exactly five):**
1. **Follow-up permission** — "this outbound touch violates no hard guarantee" (quiet hours,
   min interval, max attempts, opt-out) certified before send.
2. **Missing-info validity** — "this `MissingItem` request is justified by the playbook and
   not yet satisfied by held evidence."
3. **Case transition** — "this transition is legal per `03` §4 and its required data is
   present" (e.g. `LOST` has a loss reason).
4. **Document risk flag** — "this `RiskFlag`/DocRisk assertion is supported by its evidence
   chain" (binder bundle complete, confidences honest).
5. **Escalation decision** — "this escalation (or non-escalation) matches the `θ_escalate`
   policy and hard-override rules."

**Acceptance criteria:**
1. ≥99% of actions in the five classes carry a certificate (`mode: "certified"`); the
   remainder degrade to `mode: "heuristic"` with an alert — **LGGT unavailability degrades
   to MVP behavior, never blocks the loop** (matching `02` §7 degradation posture).
2. Every `verdict: "fail"` produces a `HumanApproval`, never a silent block or a silent
   pass; reversal rate of failed verdicts tracked in the Evaluation Lab (`15`).
3. Certification adds ≤ agreed latency budget (target: P95 ≤ 250ms per decision, async off
   the voice path — voice latency budgets in `06` are untouched).
4. For every certificate, `audit_id` resolves to a hash-chain-verified AuditEvent, and
   `GET /audit-events/verify` extended checks certificate↔event binding.
5. Plain-language rendering (§2.6) shown on DecisionBriefs for certified decisions; owner
   comprehension validated in UX review (`11`).
6. Kill-switch: per-tenant flag reverts any class to Phase-1 behavior instantly.

### Phase 3 — Full Certainty Core for critical decisions

Scope: LGGT becomes *mandatory* (not best-effort) for the critical decision set — quote/
offer send, discounting, booking commitments, autonomy-level L4/L5 chains, `HUMAN_REVIEW_REQUIRED`
release recommendations. For these, no certificate ⇒ automatic `HumanApproval` (the system
stays safe, it just stops being autonomous). Abstention manager fully fused (§2.9); public
`/certainty/*` endpoints exposed to tenants/auditors.

**Acceptance criteria:**
1. Zero critical-class actions execute autonomously without a `pass` certificate; LGGT
   outage converts critical-class autonomy to HITL (measured: 100% of outage-window critical
   actions have `HumanApproval` rows) — never to unsafe execution and never to a dropped case
   (the loop keeps driving; A1/A2 of `31` still hold during outage).
2. An external auditor, given only the AuditEvent chain + certificates + policy versions,
   can independently re-verify a sampled month of critical decisions (the `13` §5 trust
   proposition, now machine-checkable).
3. Certified-decision reversal rate ≤ heuristic-decision reversal rate on matched action
   classes (Evaluation Lab, `15`) — i.e. certification demonstrably improves decision
   quality, not just paperwork.
4. Tenant-facing certainty surface in the Command Center: per-decision "why + proof" view
   powered by §2.6, with the evidence-chip UX of `11`.

---

## 4. Non-goals and guardrails for this plan

- **No MVP dependency.** Phase 1 must be deliverable with LGGT not existing. Any Phase-1
  task that cannot proceed without LGGT input is mis-scoped by definition.
- **LGGT can only tighten.** At every phase, the certainty layer may add human approvals or
  abstentions; it may never authorize an action that `13`'s autonomy levels, validators, or
  hard guarantees would gate. The `13` safety model remains the floor.
- **One seam.** All LGGT knowledge lives behind `CertaintyCoreAdapter`. If a second import
  path appears in review, it is a defect.
- **Honest labeling.** `mode: "heuristic"` vs `"certified"` must be visible wherever
  confidence is shown (`11`) — the system never implies a proof it doesn't hold, the same
  honesty rule as `05` §6 abstention.
