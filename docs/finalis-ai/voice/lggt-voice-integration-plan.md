# Finalis Voice Engine — LGGT / Certainty Core Integration Plan

> Voice-specific companion to `32-lggt-certainty-core-integration-plan.md`. Follows doc 32's
> **Option B** exactly: seams and LGGT-compatible shapes now, runtime later; the certainty
> layer may only ever make voice *more* conservative (add approvals/abstentions), never
> authorize what doc 13's autonomy gates would block. One seam rule holds: the only certainty
> import in the voice engine is `finalis.certainty_core`.

---

## 1. What is already wired in the scaffold

Unlike doc 32 (written against a code-free blueprint), the voice scaffold on
`claude/finalis-voice-engine-open-core` has the Phase-1 seams **executing in tests today**:

| Doc-32 component | Voice realization | Where |
|---|---|---|
| `CertaintyCoreAdapter` / `NullAdapter` | Every session's final output is certified: `_end_session` constructs `NullAdapter(self.audit)` and calls `certainty.certify(f"voice_session:{s.id}", facts, policy_version="hvac-playbook-v1")`; the returned `cert.audit_id` (the id of the `certainty.stamped` audit event) is emitted as `certainty_audit_id` in the output JSON | `finalis/voice/engine.py` `_end_session` → `_build_output`; adapter in `finalis/certainty_core.py` |
| `FactBuilder` (voice flavor: **VoiceFactBuilder**) | The `Fact` list built from the extractor's `FieldValue`s — `client_name`, `address`, `preferred_date`, `device_brand`, each with its extraction `confidence` — is the voice fact-normalization step. It is currently inline in `_end_session`; naming it `VoiceFactBuilder` is a refactor, not new behavior | `finalis/voice/engine.py` `_end_session` (the `facts = [Fact(...)]` block); `Fact` in `finalis/certainty_core.py` |
| `ActionGate` | The rule-based autonomy gate runs on the proposed `next_action`: `_next_action` calls `gate(case, "send_missing_info_request")` and sets `requires_human_approval = not g.allowed`; handoff forces `requires_human_approval: True` unconditionally. Every next action is audited (`NEXT_ACTION_CREATED`) | `finalis/voice/engine.py` `_next_action`; gate in `finalis/autonomy.py` |
| `EvidenceBinder` | Every extraction carries its provenance: `VoiceExtraction.source_utterance_ids` links each intent/field/promise/objection/handoff extraction to the utterance(s) it came from, and `FieldValue.source_utterance_id` pins each field value. This is the voice-side `EvidenceReference` chain a Phase-2 binder bundles | `finalis/voice/models.py` (`VoiceExtraction`); `finalis/voice/extractor.py` (`_record`, `_set_field`) |
| Audit join (`audit_id`) | The hash-chained `AuditLog` gives every decision event a tamper-evident id; `verify_chain()` is asserted in every voice test run | `finalis/audit.py`; `tests/test_voice_engine.py::run` |
| Abstention substrate | `unknown / uncertain / confirmed` field statuses with the ASR-uncertainty ceiling (`UNCERTAIN_CONFIDENCE_CEILING = 0.5`) — uncertain values never surface as confirmed and stay in `missing_items` | `finalis/voice/extractor.py`; tested in S11 |

Honest scope statement: the NullAdapter **verifies nothing** — it stamps
`verdict="heuristic"` with `confidence = min(fact confidences)` and an audit id. That is the
whole point of Phase 1: the *shape* is certified-compatible; the *guarantee* is doc 13's
rule-based gating.

## 2. Phase 1 — interface only, LGGT-compatible facts (NOW — done)

Scope (all present and tested):
- Every completed voice session produces one certification call over its fact set; the
  output JSON carries `certainty_audit_id` — the UI/API can already distinguish
  "heuristically decided" from "certified" (doc 32 §2.1 honesty rule).
- Facts carry `key`, `value`, `confidence`; `evidence_ref_id` is reserved (currently `None`
  — wiring it to `FieldValue.source_utterance_id` is a one-line Phase-2 prerequisite, see
  §3 entry criteria).
- `policy_version` ("hvac-playbook-v1") identifies the dialogue policy/playbook the session
  ran under, matching doc 32 §2.3 policy-identity requirements.

Phase-1 acceptance (met): certification adds zero external calls and zero latency beyond an
audit append; removing the stamp is the only behavior change; all 26 voice tests pass with
the seam active.

## 3. Phase 2 — certify selected voice decisions

Real LGGT runtime behind the same `CertaintyCoreAdapter`. Five voice certification classes,
each mapped to the exact hook in `engine.py` where the decision already flows through one
choke point:

| # | Certification | What LGGT checks | Existing hook in `engine.py` |
|---|---|---|---|
| 1 | **Follow-up permission** | the proposed outbound touch (`send_photo_request`, `send_missing_info_request`) violates no hard guarantee: opt-out, quiet hours, attempt caps | `_next_action` — insert `adapter.certify` beside the existing `gate(case, ...)` call; `verdict: fail` ⇒ `requires_human_approval = True` (the field already exists) |
| 2 | **Missing-info validity** | each `MissingItem` is justified by the playbook and not already satisfied by held evidence | `_end_session`, the `missing = extractor.missing_items()` block, before `case.missing_items.append(...)` and the `MISSING_INFO_DETECTED` audit event |
| 3 | **Escalation requirement** | the handoff (or non-handoff) decision matches the θ_escalate policy and hard-override rules — certifying *non*-escalation is the safety-critical direction | `run_call` handoff branch (`if u.handoff_triggers:`) and `_handoff` — certify at the `HUMAN_HANDOFF` audit point; non-handoff certified once at `_end_session` |
| 4 | **Case transition** | the voice-driven case creation/transition is legal per doc 03 with required data present | `_end_session`, the `Case(... state=CaseState.NEW_CONTACT)` creation + `case.created` audit event (future: any voice-triggered state change) |
| 5 | **Critical-answer permission** | a spoken answer containing price/commitment/legal content is policy-covered before TTS says it | `run_call`, the `price_asked_without_data` branch — today rules force `NO_PRICE_LINE`; Phase 2 certifies any generated (LLM, VS4) answer in this class before `_say` |

Entry criteria for Phase 2 (all must hold):
1. `Fact.evidence_ref_id` populated from `source_utterance_id` for every fact (closes the
   EvidenceBinder loop; round-trip test per doc 32 Phase-1 AC-3).
2. VS4 landed or scoped: certification matters most once an LLM, not rules, produces
   answers/extractions — rules are self-certifying by inspection, LLM outputs are not.
3. LGGT runtime availability SLO agreed; **unavailability degrades to Phase-1 heuristic
   stamp + alert, never blocks the call** (doc 32 Phase-2 AC-1).
4. Latency budget respected: certification runs **async off the voice path** for classes
   1–4 (post-call/pre-send); only class 5 is in-call, and it gates a *content class* that
   already has a scripted safe fallback (`NO_PRICE_LINE`), so a certification timeout falls
   back to the script — doc 06 latency budgets untouched.
5. Per-tenant kill switch reverts any class to Phase-1 instantly.

Phase-2 acceptance: ≥99% of decisions in the five classes carry `mode: "certified"`; every
`fail` verdict yields a `HumanApproval` (never silent block/pass); `audit_id` always resolves
to a hash-chain-verified event.

## 4. Phase 3 — full ProofGate for critical voice decisions

LGGT becomes **mandatory** (not best-effort) for the critical voice set: autonomous outbound
voice calls (L4/L5 chains), spoken quotes/booking commitments, and release of
`HUMAN_REVIEW_REQUIRED` voice cases. No certificate ⇒ automatic `HumanApproval` — the system
stays safe by ceasing to be autonomous, never by executing uncertified (doc 32 Phase-3
posture; completion-loop guarantees keep driving the case during outage).

- ProofGate position: the same `_next_action` / pre-`_say` choke points as Phase 2 — no new
  seams; the gate flips from "certify if available" to "no pass, no autonomy".
- Plain-language proof rendering (doc 32 §2.6) attached to voice DecisionBriefs: which
  utterances (by `source_utterance_id`) supported the decision, which policy version, what
  was not verified.
- Acceptance: zero critical-class autonomous executions without a `pass` certificate
  (measured over outage windows); external auditor can re-verify a sampled month from
  AuditEvent chain + certificates alone; certified-decision reversal rate ≤ heuristic rate
  on matched classes.

## 5. Non-goals

No voice feature may block on LGGT before Phase 3 criteria are explicitly accepted; no
second certainty import path outside `finalis/certainty_core.py`; no UI surface may present
`mode: "heuristic"` output as verified.
