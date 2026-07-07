# Finalis AI — LGGT / Certainty Core Integration Decision

> Decision record on branch `claude/finalis-ai-enterprise-e2e-autofix` (scaffold: 102
> passing tests). Normative plan: `32-lggt-certainty-core-integration-plan.md`. LGGT is the
> founder's separate certainty/verification system; nothing in the MVP may depend on its
> availability.

## 1. Decision matrix

| Option | Description | Effort now | Risk | Benefit |
|---|---|---|---|---|
| **A — No LGGT at all** | Ignore LGGT; retrofit later if needed | None | **High** — data shapes (facts, decisions, evidence) crystallize without certification in mind; retrofit means migrating every decision record and re-plumbing the Orchestrator | None now; expensive later |
| **B — Placeholder now, runtime later** | Adapter interface + LGGT-compatible fact/decision/certificate schema + pass-through stamp; MVP ships a NullAdapter | **Low** — interfaces, one stamp, reserved schema | **Low** — worst case the interfaces sit unused; no runtime dependency, no latency, no new failure mode | Every MVP decision stored in certifiable shape from day one; LGGT becomes an adapter swap, not a migration |
| **C — Partial LGGT runtime in the MVP** | Certify selected decisions in the MVP critical path | High | **High** — MVP launch blocks on an unproven external runtime's availability, latency, and API stability | Partial certification day one, if LGGT is ready (unverified) |
| **D — Full Certainty Core / build natively first** | Re-implement proof/certificate machinery inside Finalis, converge later | Very high | **High** — duplicates the founder's own system, guarantees painful reconciliation, diverts the MVP team | Independence nobody asked for |

## 2. DECISION: Option B — placeholder now, runtime later

**And: Option B Phase 1 is ALREADY EXECUTED in the scaffold.** This is no longer a plan —
`finalis/certainty_core.py` implements it and the E2E suite exercises it:

- **`CertaintyCoreAdapter` protocol** — the single seam; nothing else in the codebase
  imports LGGT concepts (`32` §2.1, "One seam" guardrail).
- **`NullAdapter`** — stamps every certified decision with `mode=heuristic` and an
  `audit_id` equal to the id of the `certainty.stamped` AuditEvent it appends; calls no
  external system; ~40 lines total.
- **`FactBuilder`** — `build_facts()` maps `ExtractedField` → `Fact`
  (key/value/evidence_ref_id/confidence), the `32` §2.2 compatibility mapping in
  executable form.
- **`Certificate` schema** — decision_ref, facts, policy_version, verdict
  (certified | heuristic | abstained), confidence, `audit_id`, proof_blob — the `32` §2.7
  `LGGTCertificate` placeholder.
- **Tested in the E2E flow** — `tests/test_e2e_mvp_flow.py::test_e2e_hvac_quote_flow`
  Step 13 builds facts from the document's extracted fields, certifies the decision brief
  under `policy_version="hvac-playbook-v1"`, asserts `cert.verdict == "heuristic"` and
  `cert.audit_id` is set, and the audit-completeness check asserts the
  **`certainty.stamped`** event is present in the chain (which itself passes
  `audit.verify_chain()`).

## 3. Phase 2 — certify selected actions (per `32` §3)

Scope: real adapter backed by the LGGT runtime; PolicyCompiler turning versioned playbooks
into checkable policies; ActionGate enforcing verdicts. Exactly five certified action
classes:

1. **Follow-up permission** — outbound touch violates no hard guarantee (quiet hours, min
   interval, max attempts, opt-out).
2. **Missing-info validity** — the `MissingItem` request is playbook-justified and not
   already satisfied by held evidence.
3. **Case transitions** — transition legal per `03` §4 with required data present.
4. **Document risk flags** — the `RiskFlag` assertion is supported by a complete evidence
   bundle with honest confidences.
5. **Escalation decisions** — escalation/non-escalation matches θ_escalate policy and
   hard-override rules.

**Entry criteria (`32` §3 Phase 2 acceptance):** ≥99% of actions in the five classes carry
a certificate, with unavailability degrading to `mode: heuristic` + alert — LGGT outage
degrades to MVP behavior, never blocks the loop; every `fail` verdict produces a
`HumanApproval` (never a silent block or pass); certification P95 ≤ 250 ms off the voice
path; every `audit_id` resolves to a hash-chain-verified AuditEvent; plain-language proof
rendering on DecisionBriefs; per-tenant kill-switch reverting any class to Phase-1 behavior.

## 4. Phase 3 — full Certainty Core for critical decisions (per `32` §3)

Scope: LGGT mandatory (not best-effort) for the critical decision set — quote/offer send,
discounting, booking commitments, L4/L5 autonomy chains, `HUMAN_REVIEW_REQUIRED` release
recommendations. No certificate ⇒ automatic `HumanApproval` — the system stays safe, it
just stops being autonomous.

**Entry criteria:** zero critical-class actions execute autonomously without a `pass`
certificate, with LGGT outage converting critical-class autonomy to HITL (100% of
outage-window critical actions have HumanApproval rows), never to unsafe execution or a
dropped case; an external auditor can independently re-verify a sampled month of decisions
from AuditEvents + certificates + policy versions; certified-decision reversal rate ≤
heuristic reversal rate on matched classes; tenant-facing "why + proof" surface in the
Command Center.

## 5. Justification

- **B over C/D:** the MVP must not block on an unproven runtime. LGGT's availability,
  latency, and API stability are all unverified; making quote-sends wait on an external
  certification service adds a hard dependency the MVP cannot justify (`14` scopes the MVP
  to the headline loop; `13` already provides the MVP-grade safety story — autonomy levels,
  validators, escalation, abstention). D additionally burns the team rebuilding what LGGT
  already is.
- **B over A:** the real risk of A is not "no proofs at MVP" (acceptable) but **data-shape
  drift** — if decisions, facts, and evidence aren't fact-normalizable from day one,
  Phase 2 becomes a migration across every tenant's case history instead of an adapter
  swap. Data-shape compatibility costs almost nothing — **proven, not estimated: the
  NullAdapter in the scaffold is ~40 lines** (`finalis/certainty_core.py`), and it already
  gives every decision an LGGT-addressable `audit_id` on the tamper-evident audit chain.
- **Standing guardrails** (`32` §4): LGGT can only tighten — it may add approvals or
  abstentions, never authorize what `13`'s gates would block; all LGGT knowledge stays
  behind the one `CertaintyCoreAdapter` seam; a second import path is a defect.
