# Action & Communication Engine — Human Approval Queue

> **Ground truth**: `finalis/actions/engine.py` (`handle` step 9,
> `decide_approval`, `approval_queue`), `finalis/actions/models.py`
> (`MessageDraft.approval_status`, `edited_text`, `final_text`).
> Tests: `tests/test_action_communication.py::TestHumanApproval` +
> `test_4`, `test_19`. Spec: doc 13 (HITL), doc 22 §HumanApprovals
> (`GET /approvals`, `POST /approvals/{id}/decision`).

## 1. Approval states — the enum, honestly

`MessageDraft.approval_status`:

```
NOT_REQUIRED | PENDING | APPROVED | REJECTED | EXPIRED | CANCELLED
```

| State | Set by code today? |
|---|---|
| `NOT_REQUIRED` | Yes — dataclass default; low-risk drafts keep it |
| `PENDING` | Yes — `handle` step 9 when queueing |
| `APPROVED` | Yes — `decide_approval(decision="approve")` |
| `REJECTED` | Yes — `decide_approval(decision="reject")` |
| `EXPIRED` | **Designed only** — declared in the enum; **no timeout worker exists yet**, nothing sets it |
| `CANCELLED` | **Designed only** — declared; no cancel path (e.g. case closed while pending) is coded |

## 2. The flow as coded

```
propose (ActionRequest) → gate says REQUIRE_HUMAN_APPROVAL, or risk_level == "high"
  → draft composed anyway (MESSAGE_DRAFT_CREATED — the human reviews real text)
  → draft.approval_status = "PENDING"
  → queue entry appended: {"draft", "request", "case", "route", "requested_at"}
  → audit HUMAN_APPROVAL_REQUESTED {draft_id}
  → ExecutionOutcome(status="pending_approval", approval_id=draft.id)

decide_approval(draft_id, approver=…, decision=…, now=…, edited_text=…, reason=…)
  ├─ "approve" → status APPROVED; edited_text stored if provided
  │              → audit HUMAN_APPROVAL_GRANTED {draft_id, edited: bool}
  │              → queue entry removed → _send(...) → MESSAGE_SENT
  │              → ExecutionOutcome(status="executed")
  └─ "reject"  → status REJECTED
                 → audit HUMAN_APPROVAL_REJECTED {draft_id, reason}
                 → queue entry removed
                 → ExecutionOutcome(status="blocked", reason="rejected:<reason>")
```

Notes on the coded shape:

- The queue is `engine.approval_queue: list[dict]` and the approval id **is
  the draft id** — there is no first-class `HumanApproval` entity yet (see
  `data-model.md` §2). Unknown `draft_id` → `decide_approval` returns `None`.
- The high-risk templates are deliberately skeletons
  (`[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] …`) — the composer never writes prices,
  discounts, or contract language (`FORBIDDEN_PATTERNS` raises
  `MessageComposeError` on injected price-like variables,
  `test_8_composer_never_invents_price`), so a meaningful high-risk send
  *requires* the human's `edited_text`.
- Scaffold shortcut worth knowing: the approved-path `_send` is called with a
  fresh `ChannelPreference(party_id="approved")` rather than the original
  prefs — routing was already decided at queue time (`entry["route"]`), so
  this only affects the unused prefs argument, but production should re-check
  consent/quiet-hours *at approval time* (the approval may land hours later).

## 3. Before/after edit — both texts stored

`MessageDraft.text` holds what the AI proposed and is never overwritten;
`edited_text` holds what the human changed it to; sending always uses

```python
@property
def final_text(self) -> str:
    return self.edited_text or self.text
```

So the before/after pair is permanently inspectable on the draft, and the
audit event records `{"edited": bool(edited_text)}`. **Tested**:
`test_16_approve_edit_and_send` — approve with `edited_text`, assert
`APPROVED`, `final_text` starts with the human's words,
`HUMAN_APPROVAL_GRANTED` audited.

## 4. Audit trail

| Event | When | Actor |
|---|---|---|
| `HUMAN_APPROVAL_REQUESTED` | draft queued | `ai` |
| `HUMAN_APPROVAL_GRANTED` | approve decision (payload: `draft_id`, `edited`) | the `approver` string |
| `HUMAN_APPROVAL_REJECTED` | reject decision (payload: `draft_id`, `reason`) | the `approver` string |

All on the shared hash-chained `AuditLog`;
`test_19_e2e_high_risk_approval_flow` asserts the full
`HUMAN_APPROVAL_REQUESTED → HUMAN_APPROVAL_GRANTED → MESSAGE_SENT` sequence,
`test_reject_records_reason` asserts the reject leg (draft `REJECTED`,
outcome `blocked`, reason recorded).

## 5. RBAC — Designed

As coded, `approver` is a free string recorded as the audit actor
(`"owner-1"` in tests); **no authorization check is enforced**. The
production requirement (doc 22 §HumanApprovals + `UserRole.permissions`):

- `POST /approvals/{id}/decision` requires `manager`+ (or an explicit
  per-permission grant) — `approver_user_id` must resolve to an authorized
  `UserRole`.
- **The AI can never approve its own action**: the decision endpoint accepts
  only human principals; `actor.kind == "ai_worker"` is rejected outright.
- Second decision on the same approval → `409 already_decided` (idempotent).

## 6. Approval-with-timeout — production plan

Designed, not coded (this is why `EXPIRED` is currently unreachable): a
Temporal `HumanApprovalWorkflow` started when the draft is queued —

```
HumanApprovalWorkflow(approval_id, deadline):
    decided = await workflow.wait_condition(lambda: state.decided,
                                            timeout=deadline)   # signal-driven
    if not decided:
        draft.approval_status = "EXPIRED"
        audit(HUMAN_APPROVAL_EXPIRED); escalate per SLA        # doc 22: sla_breached
```

`POST /approvals/{id}/decision` signals the workflow; timeout marks the draft
`EXPIRED`, removes the queue entry, and raises a Command Center SLA item
(never a silent expiry, and never an auto-send on timeout). Full workflow
sketch: `temporal-workflows.md` §3.
