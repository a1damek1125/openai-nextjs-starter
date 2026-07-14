# Action & Communication Engine — Temporal Workflows

> **Ground truth**: `finalis/actions/adapters.py` (`WorkflowAdapter`
> protocol, `TemporalMock`), scheduling call sites in
> `finalis/actions/engine.py`. Tests:
> `tests/test_action_communication.py::test_12_temporal_mock_schedules_and_fires`,
> `test_business_hours_defer_via_temporal`. Spec: doc 18 (stack — durable
> timers), doc 22 §2.3 (timers survive restarts).

## 1. The six required workflows

| Workflow | Purpose | Status |
|---|---|---|
| `FollowUpWorkflow` | Deferred sends (business-hours) + the post-send 24h cadence check | **Mock-implemented and tested** — the only workflow name the engine actually schedules today; scheduled at `consent.defer_until` (engine step 10) and at `now + 24h` after every successful send (`_send`); fired via `TemporalMock.advance_to` in `test_12_temporal_mock_schedules_and_fires` and scheduled-on-defer in `test_business_hours_defer_via_temporal` |
| `PromiseReminderWorkflow` | Durable timer per open `Promise.due_at`; fires the due-soon/overdue/breach evaluation (case-graph `PromiseTracker`) instead of relying solely on the nightly sweep | **Designed** |
| `HumanApprovalWorkflow` | Approval SLA: wait for a decision signal with a deadline; on timeout mark the draft `EXPIRED` and escalate | **Designed** (see `human-approval-queue.md` §6) |
| `CaseStuckWorkflow` | Per-case inactivity timer reset on progress; fires stuck-score recompute / NBA re-plan when a case sits idle | **Designed** |
| `RecoveryLaterWorkflow` | Durable `wake_at` timer for parked cases (`RECOVERY_LATER` → `case.woken`, doc 22) | **Designed** |
| `DeliveryRetryWorkflow` | Retry-with-backoff after both primary and fallback channels fail (`MESSAGE_FAILED`); exponential backoff + jitter, max attempts, then DLQ/owner notify | **Designed** |

### Designed signal/timer patterns (exact shapes to use)

```python
# HumanApprovalWorkflow — signal + wait_condition with timeout
@workflow.defn
class HumanApprovalWorkflow:
    def __init__(self): self.decision = None
    @workflow.signal
    def decide(self, decision: dict): self.decision = decision
    @workflow.run
    async def run(self, approval_id: str, deadline_s: int):
        ok = await workflow.wait_condition(lambda: self.decision is not None,
                                           timeout=timedelta(seconds=deadline_s))
        if not ok: await workflow.execute_activity(expire_approval, approval_id)

# PromiseReminderWorkflow / RecoveryLaterWorkflow — durable sleep, cancellable
await workflow.sleep(until - workflow.now())          # survives restarts
await workflow.execute_activity(fire_promise_check, promise_id)

# CaseStuckWorkflow — resettable timer via signal
@workflow.signal
def progress(self): self.last_progress = workflow.now()   # loop re-arms sleep

# DeliveryRetryWorkflow — retry policy on the activity, not hand-rolled loops
await workflow.execute_activity(send_message, args,
    retry_policy=RetryPolicy(initial_interval=1s, backoff_coefficient=2,
                             maximum_interval=5m, maximum_attempts=8))
```

## 2. `TemporalMock` semantics

`WorkflowAdapter` protocol: `schedule(workflow, *, run_at, payload) -> str`
and `advance_to(now) -> list[dict]`.

- **Simulated clock**: nothing fires on wall time. `schedule` appends
  `{"id": "wf-N", "workflow", "run_at", "payload"}` to `self.scheduled` and
  audits `TEMPORAL_WORKFLOW_STARTED`; `advance_to(now)` moves every entry
  with `run_at <= now` to `self.completed` and audits
  `TEMPORAL_WORKFLOW_COMPLETED`. Tests control time exactly
  (`advance_to(T0 + timedelta(days=2))`).
- **Restart-survivable plain-data state**: the mock's docstring is the
  design statement — *"Scheduled work survives 'restarts' because state is
  plain data — exactly the property Temporal provides for real."* The mock
  holds no closures, threads, or live timers; a scheduled workflow is a dict
  that could be serialized and reloaded. That is deliberately the same
  contract as Temporal's event-sourced workflow state, so swapping the mock
  for the real SDK changes the transport, not the engine's assumptions.
- **No decisions in the adapter**: per the adapters-module docstring, mocks
  are deterministic and observable and *"none of these adapters makes
  decisions — the Finalis brain (gate/approval/audit) is always upstream."*
  A firing workflow re-enters `handle()`/the loop, where gate, consent, and
  rate limits are re-evaluated at fire time.

## 3. What is audited

`TEMPORAL_WORKFLOW_STARTED` (payload: `workflow`, `wf_id`, `run_at`) on every
schedule; `TEMPORAL_WORKFLOW_COMPLETED` (payload: `workflow`, `wf_id`) on
every fire — asserted in `test_12_temporal_mock_schedules_and_fires` and
included in the `test_20_audit_written_for_all_important_steps` event-set
check.

## 4. Production adapter plan

- **Temporal Python SDK** (`temporalio`), self-hosted or Temporal Cloud per
  doc 18. The `WorkflowAdapter` protocol keeps the engine unchanged:
  `schedule()` becomes `client.start_workflow(...)` with a computed start
  delay / timer inside the workflow; `advance_to()` disappears (real clock).
- **One activity per provider call.** Workflow code stays deterministic;
  every Meta/Twilio/SES/Chatwoot HTTP call is an activity with its own
  timeout and `RetryPolicy`. No network I/O in workflow code, ever.
- **Idempotency keys.** Workflow id = deterministic business key
  (`followup-{case_id}-{action_type}-{run_at}`,
  `approval-{draft_id}`) with `WorkflowIdReusePolicy` rejecting duplicates —
  the at-least-once event bus (doc 22 §2.3) then cannot double-start a
  cadence; each send activity carries idempotency key = `action_id` so a
  retried activity cannot double-send.
- **Saga-style compensation for multi-step sends.** A send that is
  create-upload-link → compose → provider send → record execution runs as a
  saga: each step registers its compensation (revoke link, mark draft
  cancelled, record `MESSAGE_FAILED`) and a failure after partial progress
  runs compensations in reverse instead of leaving half-executed state. The
  scaffold's single-process version does not need this; distributed
  execution does.
