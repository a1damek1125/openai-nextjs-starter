# Case Graph — Action Gate

> **Ground truth**: `finalis/case_services.py` (`ActionGateService`,
> `GateDecision`), `finalis/autonomy.py` (`ALWAYS_HITL`, `MIN_LEVEL`,
> `gate()`), `finalis/models.py` (`Case.effective_autonomy`), branch
> `claude/finalis-case-graph-completion-loop`, 160 tests passing.
> Spec: doc 13 (autonomy & safety), doc 22 §1.4,
> doc 32/44 (LGGT integration).

## 1. The four outcomes AS CODED

`ActionGateService.evaluate(case, action_type, *, confidence=1.0, audit,
context=None)` returns a `GateDecision(outcome, reason, audit_id)`. The rules
fire **in this order** (first match wins):

| # | Rule (as coded) | Outcome | `reason` |
|---|---|---|---|
| 1 | `case.opted_out` and `action_type` starts with `send_` / `call_` / `ask_` | **BLOCK** | `client_opted_out` — the opt-out hard block (doc 22 §1.4); refuses outright, no approval minted |
| 2 | `action_type in HIGH_RISK` | **REQUIRE_HUMAN_APPROVAL** | `high_risk_action` — even at L5, even at confidence 1.0 |
| 3 | `confidence < 0.5` | **ABSTAIN_MISSING_DATA** | `confidence={x:.2f}<0.5` — never act on thin evidence |
| 4 | `case.effective_autonomy <= 2` and outbound prefix (`send_`/`call_`/`ask_`) | **REQUIRE_HUMAN_APPROVAL** | `autonomy_L{n}` — frozen/low autonomy holds client-facing sends |
| 5 | `action_type in AUTO_OK` | **ALLOW** | `low_risk@L{n}` |
| 6 | anything else | **REQUIRE_HUMAN_APPROVAL** | `unknown_action_conservative_default` — unknown actions are never auto-executed |

### The sets

```python
HIGH_RISK = ALWAYS_HITL | {"close_won", "close_lost", "send_offer_commitment"}
# ALWAYS_HITL (finalis/autonomy.py, doc 13 §1/§6):
#   send_out_of_rule_price, grant_discount_beyond_bound,
#   send_legal_content, sign_contract, take_payment

AUTO_OK = {"ask_for_missing_info", "send_photo_request",
           "send_document_request", "send_follow_up", "confirm_receipt",
           "create_quote_task", "analyze_document", "compare_offer",
           "do_nothing_wait", "mark_recovery_later", "request_human_review",
           "schedule_visit", "call_client"}
```

**Nuance worth knowing**: because rule 4 only matches the outbound prefixes,
non-outbound `AUTO_OK` actions (`analyze_document`, `create_quote_task`,
`do_nothing_wait`, `compare_offer`, ...) are ALLOWed even at L1–L2 — matching
doc 13's L1 "Observe"/L2 "Prepare" semantics where internal analysis and
drafting are always permitted. Client-facing `AUTO_OK` actions effectively
require **L3+** ("Communicate").

### Frozen autonomy

`Case.effective_autonomy = min(autonomy_level, autonomy_frozen_at)` when
`autonomy_frozen_at` is set — the `HUMAN_REVIEW_REQUIRED` cap at L2
(doc 13 §2.2). An L4 case frozen at 2 gets `REQUIRE_HUMAN_APPROVAL` for
`send_follow_up`
(`tests/test_case_graph_services.py::TestActionGate::test_frozen_autonomy_requires_human`).

## 2. Every decision writes a typed audit event

There is no silent path — all four outcomes append to the hash chain, and the
event's `id` is returned on the decision (`d.audit_id = ev.id`) so callers can
reference the exact ledger row:

| Outcome | Audit event (`actor="ai"`, payload `{action, outcome, reason}`) |
|---|---|
| ALLOW | `ACTION_CREATED` |
| BLOCK | `ACTION_BLOCKED` |
| REQUIRE_HUMAN_APPROVAL | `HUMAN_REVIEW_REQUESTED` |
| ABSTAIN_MISSING_DATA | `ACTION_ABSTAINED` |

## 3. Spec lists → code sets

Doc 13's "AI may do automatically (at sufficient level)" list maps to
`AUTO_OK` (informational sends, missing-info requests, follow-ups, internal
analysis/comparison, scheduling, parking, self-escalation). Doc 13's "always
requires a human regardless of level" list maps to `HIGH_RISK`:
`ALWAYS_HITL` verbatim (out-of-rule pricing, discounts beyond bound, legal
content, contract signing, payments) **plus** the case-closing and
offer-commitment actions (`close_won`, `close_lost`, `send_offer_commitment`)
added at this service layer — closing a deal and committing an offer are
commitments, so they are HITL in the scaffold even though doc 13 L4/L5 could
eventually allow rule-covered variants.

Note there are **two gates** in the codebase, by design:

- `finalis/autonomy.py::gate()` — the per-action-type minimum-level table
  (`MIN_LEVEL`, doc 13 §6); mints `HumanApproval` objects; raises on unknown
  action types. Used by the Voice engine.
- `ActionGateService` — the Case Graph service gate documented here: coarser
  risk classes, confidence abstention, opt-out block, conservative default
  (never raises), and a typed audit event per decision. This is the gate the
  completion loop runs every tick.

## 4. Relationship to the autonomy ladder and future LGGT ProofGate

The gate is the **enforcement point of doc 13's five-level ladder** at
runtime: L1–L2 prepare-only (rule 4), L3+ communicate (`AUTO_OK` sends),
always-HITL set independent of level (rule 2), plus the two global overrides
that live upstream in scoring (`must_escalate` hard-escalates legal-signing
and safety emergencies, freezing autonomy at L2 — which this gate then
respects via `effective_autonomy`).

It is also the declared **LGGT integration point** (docs 32/44): the class
docstring reads *"Rule-based gate (Phase-1; LGGT ProofGate strengthens it
later)"*. `finalis/certainty_core.py` already ships the `NullAdapter`
placeholder that stamps `certainty.stamped` heuristic certificates
(`tests/test_case_graph_services.py::TestLGGTPlaceholderCallable`); when the
LGGT runtime lands, ProofGate slots in as an additional check inside
`evaluate()` — same signature, same four outcomes, proofs instead of (only)
rules.

## 5. Test coverage

| Behavior | Test (`tests/test_case_graph_services.py::TestActionGate` unless noted) |
|---|---|
| ALLOW low-risk at L3 + audit_id returned | `test_allow_low_risk` |
| HIGH_RISK forces approval even at L5 (`close_won`, `sign_contract`, `take_payment`) + 3× `HUMAN_REVIEW_REQUESTED` | `test_require_human_for_high_risk` |
| Opt-out hard block + `ACTION_BLOCKED` | `test_block_on_optout` |
| Confidence 0.3 → abstain | `test_abstain_on_low_confidence` |
| L4 frozen at 2 → approval | `test_frozen_autonomy_requires_human` |
| Unknown action → conservative approval | `test_unknown_action_conservative` |
| Gate inside the loop tick (NBA proposal gated, ALLOW path sends) | `TestCompletionLoopService::test_run_case_selects_action_and_respects_gate` |
| `send_offer_commitment` → approval → `HUMAN_APPROVAL_GRANTED` → human sends | `TestE2EHvacLifecycle::test_full_lifecycle` (steps 17–18) |
| Level-table gate (`autonomy.gate`) incl. opt-out and unknown-action `ValueError` | `tests/test_autonomy_audit.py` |
