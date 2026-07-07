# Case Graph — LGGT / Certainty Core Placeholder Plan

> Case-graph-specific instance of the repo-wide LGGT plan. Normative sources:
> `docs/finalis-ai/32-lggt-certainty-core-integration-plan.md` (Option B — placeholder
> now, runtime later) and `docs/finalis-ai/44-lggt-integration-decision.md` (decision
> record: Option B Phase 1 executed in the scaffold). This document maps that plan onto
> the Case Graph module on branch `claude/finalis-case-graph-completion-loop`
> (160 tests passing).

## 1. What exists — Implemented and tested

`finalis/certainty_core.py` (~65 lines) is Phase 1 of Option B, live on this branch:

- **`CertaintyCoreAdapter`** — a `typing.Protocol` with the single seam:
  `certify(decision_ref: str, facts: list[Fact], policy_version: str) -> Certificate`.
  Nothing else in `finalis/` imports LGGT concepts (doc 32 §4 "One seam" guardrail
  holds: `certainty_core` is the only module naming certificates or facts).
- **`Fact`** — LGGT-compatible fact record: `key, value, evidence_ref_id, confidence`.
  `build_facts(fields)` is the executable FactBuilder (doc 32 §2.2): it maps
  `ExtractedField` → `Fact` losslessly (`field_key`/`field_value`/`id`/multiplicative
  `confidence`).
- **`Certificate`** — the `LGGTCertificate` placeholder schema (doc 32 §2.7):
  `decision_ref, facts, policy_version, verdict (certified | heuristic | abstained),
  confidence, audit_id, proof_blob, id`.
- **`NullAdapter`** — the only implementation: calls no external system, computes
  `confidence = min(fact confidences, default 1.0)`, appends a **`certainty.stamped`**
  AuditEvent (`{decision_ref, mode: "heuristic", n_facts}`) and returns a `Certificate`
  with `verdict="heuristic"` and `audit_id` = that event's id — so every stamped
  decision is addressable on the tamper-evident hash chain from day one.

**Test evidence:**
`tests/test_case_graph_services.py::TestLGGTPlaceholderCallable::test_placeholder_certifies_without_runtime`
certifies `decision_ref="case_transition:test"` with one Fact under
`policy_version="v1"` and asserts `cert.verdict == "heuristic"`, `cert.audit_id` is
set, and exactly one `certainty.stamped` event was written. (The broader MVP flow test
`tests/test_e2e_mvp_flow.py::test_e2e_hvac_quote_flow` additionally certifies a
decision brief under `policy_version="hvac-playbook-v1"` and checks the event survives
`verify_chain()`.)

**What does NOT exist:** any LGGT runtime call, `PolicyCompiler`, `EvidenceBinder` as
code, proof rendering, `LGGTCertificate` persistence, or the `/v1/certainty/*`
endpoints. Those are Phase 2+ by design — the MVP has zero dependency on LGGT
availability.

## 2. Integration points in the Case Graph module

These are the seams in **this module** where the real adapter plugs in. Each is an
existing, tested choke point; Phase 2 adds a `certify()` call at that point — it never
adds a new code path.

| # | Seam (code today) | Doc 32 §3 certified class | What LGGT certifies |
|---|---|---|---|
| 1 | **`ActionGateService.evaluate`** (`finalis/case_services.py`) — every proposed action passes here; every decision already writes an AuditEvent and returns its `audit_id` in `GateDecision` | §2.5 ProofGate | **This is the future ProofGate hook.** Phase 2: gate calls `adapter.certify(f"action:{action_type}", facts, policy_version)` before ruling; `verdict="fail"` routes to `HumanApproval` (never silent block), `verdict="abstained"` behaves like `confidence < 0.5` (`ABSTAIN_MISSING_DATA`). The gate may only become **more** conservative — it can add approvals, never bypass `HIGH_RISK`/opt-out/autonomy rules. |
| 2 | **State transitions** — `finalis.state_machine.transition`, which writes `case.state_changed` | Class 3, "Case transition" | "This transition is legal per doc 03 §4 and its required data is present" (e.g. `LOST` carries a loss reason; final-state exits carry `human_override`). Certificate binds to the `case.state_changed` AuditEvent id. |
| 3 | **Missing-info validity** — `MissingInfoService.detect` (writes `MISSING_INFO_DETECTED`) | Class 2 | "This `MissingItem` request is justified by the industry profile and not already satisfied by held evidence" — certifies the profile-vs-known-facts diff before the loop asks the client for anything. |
| 4 | **Follow-up permission** — `CompletionLoop.can_touch`/`send_followup` + the loop's duplicate-prevention set (`FOLLOW_UP_RATE_LIMITED`, `followup.suppressed/sent`) | Class 1 | "This outbound touch violates no hard guarantee" — quiet hours, min interval, max attempts, opt-out, duplicate cooldown — certified before send. Phase 1 already enforces these heuristically and audits every suppression. |
| 5 | **Decision briefs** — today an audit-event-only record (`DECISION_BRIEF_CREATED`) | §2.6 renderer surface | Phase 2 attaches a certificate to each brief and renders it in plain language ("what was decided, which facts, which policy version, what was NOT verified"). The MVP flow test already stamps a brief via `NullAdapter`. |

(Doc 32's remaining Phase-2 classes — document risk flags, escalation decisions — live
in the OCR/autonomy modules, not the Case Graph; listed there.)

## 3. `LGGTCertificatePlaceholder` entity mapping

How the scaffold's `Certificate` dataclass maps to the reserved Phase-2
`LGGTCertificate` table (doc 32 §2.7):

| `LGGTCertificate` (doc 32, reserved) | Scaffold `Certificate` today | Notes |
|---|---|---|
| `decision_ref` (jsonb `{kind, entity_id, case_id}`) | `decision_ref: str` (e.g. `"case_transition:test"`, `"decision_brief:{case_id}"`) | **`decision_type` → `decision_ref`**: the string encodes the decision kind today; Phase 2 structures it into the jsonb shape. |
| `facts` (jsonb `FactRecord[]`) | `facts: list[Fact]` | Lossless per doc 32 §2.2 mapping; `Fact.evidence_ref_id` preserves provenance. |
| **`facts_hash`** | — not present | **Phase-2 addition to `Certificate`**: deterministic hash of the certified fact set, so the exact input is re-verifiable. |
| **`rules_hash`** | — not present (only `policy_version: str`) | **Phase-2 addition**: hash of the `CompiledPolicy` rule bundle (doc 32 §2.3), alongside the human-readable `policy_version`. |
| `verdict` (`pass | fail | abstain`) | `verdict` (`certified | heuristic | abstained`) | **`certificate_status` → `verdict`**: Phase 1 only ever emits `heuristic`; Phase 2 introduces `pass/fail` from the real runtime (naming reconciled at migration time; `heuristic` remains the degraded-mode value). |
| `confidence` | `confidence` (min over facts in `NullAdapter`) | Same semantics. |
| `audit_id` (FK → `AuditEvent.id`) | `audit_id: str` = id of the `certainty.stamped` event | **The join**: `audit_id → AuditEvent.id`. Because AuditEvents are hash-chained (`hash_prev`/`hash_self`, `AuditLog.verify_chain()`), a certificate inherits tamper evidence — the certified decision provably wasn't rewritten. Already true in the scaffold. |
| `proof_blob` (opaque, LGGT-owned) | `proof_blob: dict` (empty in Phase 1) | Reserved. |
| `id`, `created_at`, indexes, immutability | `id` (uuid) | Persistence, `(tenant_id, audit_id)` index, append-only regime — all Designed, land with the database. |

## 4. Phases

### Phase 1 — Placeholder + LGGT-compatible storage — **DONE on this branch**

Scope: `CertaintyCoreAdapter` protocol, `NullAdapter` stamp, `Fact`/`Certificate`
schemas, `build_facts` mapping, `certainty.stamped` on the audit chain. Verified:
`TestLGGTPlaceholderCallable` passes; zero runtime calls to any external system;
removing the stamp is the only behavior-affecting change (doc 32 §3 Phase-1 criteria 1,
2, 5 satisfied in the scaffold; criterion 3's full fixture round-trip and criterion 4's
spec reservations live at repo level, docs 04/22/32).

### Phase 2 — Certify selected actions — Designed

Scope in this module: real adapter behind the same protocol; `certify()` calls at seams
1–4 of §2; `facts_hash`/`rules_hash` added to `Certificate`; `LGGTCertificate` table +
`(tenant_id, audit_id)` join; `verdict="fail"` → `HumanApproval`, `verdict="abstained"`
→ abstain path; plain-language rendering on decision briefs; per-tenant kill-switch
back to Phase-1 behavior.

**Entry criteria** (from docs 32 §3 / 44 §3): LGGT runtime available with a stable
certify API; persistence layer live (certificates need a table and the AuditEvent FK);
PolicyCompiler producing versioned rule bundles from playbooks. **Acceptance:** ≥99% of
actions in the certified classes carry a certificate, LGGT unavailability degrades to
`mode: heuristic` + alert (never blocks the loop), P95 certification latency ≤ 250 ms
off the voice path, every `audit_id` resolves to a chain-verified event, kill-switch
proven.

### Phase 3 — Mandatory certification for critical decisions — Designed

Scope in this module: offer/quote sends, `close_won`/`close_lost`, final-state
overrides, `HUMAN_REVIEW_REQUIRED` release recommendations, L4/L5 autonomy chains —
**no certificate ⇒ automatic `HumanApproval`** (system stays safe, stops being
autonomous; the loop keeps driving cases).

**Entry criteria:** Phase 2 stable in production with reversal-rate data from the
Evaluation Lab showing certified decisions reverse no more often than heuristic ones;
outage drill demonstrating 100% of outage-window critical actions produced
`HumanApproval` rows; external-auditor replay of a sampled month from
AuditEvent chain + certificates + policy versions.

## 5. Guardrails (standing, from doc 32 §4)

- **No MVP dependency**: Phase 1 is deliverable with LGGT not existing — trivially true
  here (nothing calls it).
- **LGGT can only tighten**: at every phase it may add approvals/abstentions, never
  authorize what the autonomy levels, `ActionGateService` rules, or hard guarantees
  would block.
- **One seam**: all LGGT knowledge stays behind `CertaintyCoreAdapter`; a second import
  path is a review defect.
- **Honest labeling**: `heuristic` vs `certified` must be visible wherever confidence
  is shown; the system never implies a proof it doesn't hold.
