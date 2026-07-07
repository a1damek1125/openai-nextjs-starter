# Action & Communication Engine — Action Gate Usage

> **Ground truth**: `finalis/actions/engine.py`
> (`ActionCommunicationEngine.handle`, `HIGH_RISK_ACTION_TYPES`), reusing
> `finalis/case_services.py::ActionGateService` unchanged; tests in
> `tests/test_action_communication.py` (25 passing, 185 repo-wide).
> The gate itself is documented in
> `docs/finalis-ai/case-graph/action-gate.md` — this page covers only how
> ACE *uses* it.

## 1. One gate, reused — not reimplemented

ACE constructs the case-graph `ActionGateService` directly
(`self.gate = ActionGateService()` in `ActionCommunicationEngine.__init__`)
and calls the same `evaluate(case, action_type, confidence=…, audit=…)` with
the same four outcomes:

| Gate outcome | ACE reaction (engine step 3) |
|---|---|
| `ALLOW` | continue down the pipeline (routing → consent → rate → compose → send) |
| `BLOCK` | `ExecutionOutcome(status="blocked", reason=decision.reason)` — stop |
| `ABSTAIN_MISSING_DATA` | `blocked` with reason `abstain:<gate reason>` — stop |
| `REQUIRE_HUMAN_APPROVAL` | draft is still composed, then parked in the approval queue (`pending_approval`) — never silently dropped |

Confidence is forwarded from the request:
`confidence=request.payload.get("confidence", 1.0)`.

## 2. The ACE-specific mapping onto gate action types

The gate's rule table keys on case-graph action names, while ACE requests use
communication action names (`send_photo_request`,
`send_follow_up_after_offer`, `send_price_negotiation`, …). ACE maps them
onto exactly two gate actions:

```python
HIGH_RISK_ACTION_TYPES = {"close_case_won", "close_case_lost",
                          "send_quote_status_update_with_price",
                          "send_price_negotiation", "send_contract_response"}

gate_action = ("send_out_of_rule_price"
               if request.action_type in HIGH_RISK_ACTION_TYPES
               else "send_follow_up")
```

- **High-risk comm actions** → evaluated as `send_out_of_rule_price`, which
  is in the gate's `ALWAYS_HITL` set → `REQUIRE_HUMAN_APPROVAL` at any
  autonomy level, any confidence (case-graph gate rule 2).
- **All other (low-risk) comm actions** → evaluated as `send_follow_up`,
  which is in `AUTO_OK` → `ALLOW` at effective autonomy ≥ 3, but still
  subject to the gate's opt-out `BLOCK` (rule 1), low-confidence abstain
  (rule 3), and the L≤2 / frozen-autonomy approval hold (rule 4).

This is deliberately coarse in the scaffold: the gate sees two risk classes,
and the finer distinctions (consent, business hours, rate limits, channel
permission) are enforced by ACE's own downstream checks in the same `handle`
call.

## 3. The `risk_level="high"` override

Independently of the gate outcome, engine step 9 forces the approval queue:

```python
if decision.outcome == "REQUIRE_HUMAN_APPROVAL" or request.risk_level == "high":
```

So a request flagged `risk_level="high"` goes to the human queue **even if
the gate said ALLOW**. Belt and braces: the proposer's risk assessment and
the gate's rule table are independent tripwires, and either one alone is
sufficient to require a human. (In practice every `HIGH_RISK_ACTION_TYPES`
request in the tests also carries `risk="high"`, so both fire.)

## 4. Paths that bypass the client gate — deliberately

Two branches run **before** the gate (engine steps 1–2):

1. **`handoff_to_human`** → `_handoff()` → Chatwoot conversation with the AI
   summary as a private note. Bypasses the messaging gates because handing a
   case to a human is itself the safe action — blocking it on autonomy or
   consent grounds would trap the case with the AI. The client is not
   messaged by this path; a conversation is opened for a *human* to handle
   (`test_14_chatwoot_mock_creates_handoff`).
2. **`notify_owner` / `create_internal_task`** → `_internal()` → owner inbox
   via the notification adapter. Skips client gates because there is **no
   client contact**: consent, quiet hours, and anti-spam protect the client,
   and none of them applies to telling the business owner something
   (`test_13_novu_mock_sends` — channel is `inbox`).

Both paths still write `ACTION_REQUESTED` and their execution/audit records —
bypassing the gate never means bypassing the ledger.

## 5. ACE's additional blocks after the gate

Passing the gate is necessary, not sufficient. In order, `handle` can still
stop the action:

| Check (step) | Block reason | Audit event |
|---|---|---|
| Channel routing (4) — every permitted channel opted out / unavailable | `no_permitted_channel` | `ACTION_GATE_BLOCK` |
| Consent & hours (5) — `do_not_contact` or channel/`any` opt-out | `do_not_contact` / `opted_out:<ch>` | `ACTION_GATE_BLOCK` |
| Consent & hours (5) — outside `preferred_time_window`, not urgent | not a block: `deferred` via Temporal | `ACTION_SCHEDULED` |
| Rate limit (6) | `rate_limited:<cooldown\|max_attempts\|daily_limit\|paused_client_replied>` | `FOLLOW_UP_RATE_LIMITED` |
| Delivery (10) — provider + fallback both failed | `delivery_failed` | `MESSAGE_FAILED` |

## 6. Every outcome is audited

The engine docstring is the contract: *"Every decision point writes an audit
event; nothing sends without passing the gate; a rejected/blocked action is
never silent."* Events on this path (all on the shared hash-chained
`AuditLog`, `verify_chain()` asserted in the E2E tests):

`ACTION_REQUESTED` (always, before anything) → one of the gate's own events
(`ACTION_CREATED` / `ACTION_BLOCKED` / `HUMAN_REVIEW_REQUESTED` /
`ACTION_ABSTAINED`, written inside `ActionGateService.evaluate`) → then
`ACTION_GATE_BLOCK`, `FOLLOW_UP_RATE_LIMITED`, `UPLOAD_LINK_CREATED`,
`MESSAGE_DRAFT_CREATED`, `HUMAN_APPROVAL_REQUESTED`, `ACTION_SCHEDULED`,
`MESSAGE_SENT` / `MESSAGE_FAILED` as the path dictates.

## 7. Test coverage

| Behavior | Test (`tests/test_action_communication.py`) |
|---|---|
| Request audited (`ACTION_REQUESTED`) + low-risk send executes | `test_1_action_request_created_and_audited` |
| Gate ALLOW for low-risk action | `test_2_gate_allow_low_risk` |
| Gate BLOCK on `case.opted_out` (rule 1 reused verbatim) | `test_3_gate_block_on_optout_case` |
| High-risk → approval even at L5 + `HUMAN_APPROVAL_REQUESTED` | `test_4_gate_requires_approval_for_high_risk` |
| Channel-level opt-out (`any`) → `no_permitted_channel` block | `test_9_consent_gate_blocks_optout` |
| Full high-risk approval E2E (gate → queue → approve → send) | `test_19_e2e_high_risk_approval_flow` |
| Audit completeness incl. gate's `ACTION_CREATED` + chain verify | `test_20_audit_written_for_all_important_steps` |
