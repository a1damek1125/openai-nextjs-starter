# Action & Communication Engine — Follow-Up Executor

> **Ground truth**: `finalis/actions/engine.py` (`handle`, `_send`,
> `record_delivery`), `finalis/actions/services.py`
> (`ConsentPermissionService`, `RateLimitSpamGuard`),
> `finalis/actions/models.py` (`RateLimitRule`, `ActionExecution`),
> `finalis/actions/adapters.py` (`TemporalMock`, `NovuMock`).
> Tests: `tests/test_action_communication.py` (25 passing).
> Spec: doc 09 (completion loop / follow-up), doc 22 §FollowUpSequences.

## 1. The executed flow

For a follow-up request that passes the ActionGate (see `action-gate.md`),
`handle` runs, in order: channel routing → **consent/business-hours check** →
**rate limit** → (upload link) → compose → (approval) → **defer or send** →
**post-send cadence scheduling**. Every step audited.

## 2. Consent check and business-hours deferral — tested

`ConsentPermissionService.check(prefs, consents, channel, now, urgent)`:

1. `prefs.do_not_contact` → hard block (`do_not_contact`).
2. Any `ConsentPreference(status="opted_out")` matching the routed channel or
   `"any"` → hard block (`opted_out:<channel>`).
3. Outside `prefs.preferred_time_window` (default local hours 8–21) and not
   `urgent` → **not a block**: returns `defer_until` = today at window start
   (+1 day if `now.hour >= end`).

Hard blocks return `blocked` + `ACTION_GATE_BLOCK`. Deferral takes the
durable path — the draft is already composed and stored, then:

```python
self.temporal.schedule("FollowUpWorkflow", run_at=consent.defer_until,
                       payload={"case_id": …, "draft_id": …, "channel": …})
```

audited as `ACTION_SCHEDULED`, outcome status `deferred`.
**Tested**: `test_business_hours_defer_via_temporal` (request at 23:00 →
`deferred`, `eng.temporal.scheduled` non-empty, `ACTION_SCHEDULED` in the
log).

## 3. Rate limiting / anti-spam — the four guards

`RateLimitSpamGuard.check(case_id, action_type, now)` evaluates against one
`RateLimitRule` (scaffold default: `RateLimitRule(tenant_id="default")`;
production: per-tenant/per-action rows). First refusal wins:

| Guard | Rule field / mechanism | Refusal reason | Test |
|---|---|---|---|
| Client-reply pause | `client_replied(case_id)` adds the case to `_paused_cases`; checked first | `paused_client_replied` | `test_client_reply_pauses_followups` — reply delivery event, then a follow-up **2 days later** is still blocked |
| Lifetime attempts | `max_attempts = 3` per `(case_id, action_type)` history | `max_attempts` | branch coded in `check()`; no dedicated test drives it (the 20h cooldown fires first at default settings) |
| Cooldown | `cooldown_minutes = 20 * 60` (**20 hours**) since the last recorded attempt of the same `(case, action_type)` | `cooldown` | `test_10_rate_limit_prevents_duplicate_followup` — second identical request at +1h → `blocked`, reason `rate_limited:cooldown`, `FOLLOW_UP_RATE_LIMITED` audited |
| Daily cap | `max_per_day = 3` across **all** action types for the case on `now.date()` | `daily_limit` | branch coded in `check()`; not directly exercised by a named test (unreachable before cooldown/max_attempts at defaults) |

Refusals surface as `ExecutionOutcome(status="blocked",
reason="rate_limited:<reason>")` with a `FOLLOW_UP_RATE_LIMITED` audit event.
Attempts are recorded (`rate.record`) **only after a successful send**, so
blocked/failed attempts never consume budget. `resume(case_id)` lifts the
reply pause (a human or the loop re-enables follow-ups deliberately).

## 4. Duplicate prevention

There is no separate dedup table in the scaffold: duplicate suppression *is*
the cooldown — two `send_photo_request`s for the same case within 20h cannot
both send (`test_10_rate_limit_prevents_duplicate_followup`). Production adds
the idempotency layer of doc 22 (`Idempotency-Key`, deterministic
`action_id` send keys) so at-least-once event delivery cannot double-send
either; see `temporal-workflows.md` §4.

## 5. The 24h / 48h / 72h cadence

The cadence is emergent, not a stored sequence entity:

- **`RateLimitRule` defaults** shape it: 20h cooldown means at most one
  follow-up per ~day per action type; `max_attempts = 3` caps the sequence
  at three touches (≈ 24h, 48h, 72h after the trigger).
- **Post-send scheduling**: every successful `_send` durably schedules the
  next check —

  ```python
  self.temporal.schedule("FollowUpWorkflow", run_at=now + timedelta(hours=24),
                         payload={"case_id": …, "action_type": …,
                                  "attempt_followup": True})
  ```

  When that workflow fires 24h later, the loop re-proposes; the gate, consent,
  rate limiter (cooldown satisfied at 24h > 20h), and reply-pause decide
  whether touch N+1 actually goes out. Exhaustion (`max_attempts`) is the
  point where the completion loop parks the case (`RECOVERY_LATER`,
  doc 22 `followup.exhausted`) — that transition lives in the case graph, not
  ACE.

**Tested**: `test_12_temporal_mock_schedules_and_fires` (send → cadence
workflow scheduled → `advance_to(+2 days)` fires `FollowUpWorkflow`,
`TEMPORAL_WORKFLOW_COMPLETED` audited);
`test_18_e2e_offer_followup_after_72h` (offer sent, no response for 72h →
low-risk `send_follow_up_after_offer` executes on the client's preferred
email channel, no approval queue involvement, audit chain verifies).

## 6. Delivery fallback on provider failure — tested

`_send` tries the routed channel first; on provider failure it retries
**once** on the router's precomputed fallback channel:

- `execution.retry_count += 1`, `execution.channel = route.fallback`,
  same `draft.final_text` resent.
- Both fail (or no fallback) → `execution.status = "failed"`,
  `MESSAGE_FAILED` audited, outcome `blocked` / `delivery_failed` — the
  completion loop sees a loud failure, never a silent drop.

**Tested**: `test_provider_failure_uses_fallback_channel`
(`fail_channels={"whatsapp"}` → executed on `sms`, `retry_count == 1`).
Retry-with-backoff beyond the single fallback hop is the Designed
`DeliveryRetryWorkflow` (`temporal-workflows.md` §3).

## 7. Delivery tracking states

`ActionExecution.status` flow (as declared in the model):

```
created → queued → scheduled → sent → delivered | failed | read | replied
```

`created` at construction; `sent`/`failed` set by the send path; the
post-send states are written by `record_delivery(execution, status=…,
provider_message_id=…, payload=…)`, which appends a `DeliveryEvent`, mutates
`execution.status`, and audits:

| Delivery status | Audit event |
|---|---|
| `delivered` | `MESSAGE_DELIVERED` (`test_15_delivery_event_updates_status`) |
| `read` | `MESSAGE_READ` |
| `replied` | `CLIENT_REPLIED` |
| `failed` | `MESSAGE_FAILED` |
| other (`clicked`, `uploaded`, …) | `MESSAGE_DELIVERED` (default mapping) |

(`queued`/`scheduled` are declared for the production queue/scheduler stages;
no scaffold path sets them on the execution — deferral is represented by the
Temporal workflow record.)

## 8. `CLIENT_REPLIED` → pause

The last line of `record_delivery`:

```python
if status == "replied":
    self.rate.client_replied(execution.case_id)
```

A client reply immediately pauses **all** automated follow-ups for the case —
the conversation is live and the AI must not keep executing a cadence over
it. `CLIENT_REPLIED` is audited with `actor="provider"`. Tested end-to-end in
`test_client_reply_pauses_followups`. This is the executable form of doc 22's
"`message.received` → Follow-up Worker stops pending cadence step".
