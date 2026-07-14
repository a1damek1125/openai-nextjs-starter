# Case Graph — Completion Loop Contract

Refines `docs/finalis-ai/09-completion-loop-followup-promises.md` (canonical loop
spec). Executable form: `finalis/completion_loop.py` (core) +
`CompletionLoopService.run_case` in `finalis/case_services.py` (the tick). Status:
**Implemented and tested** — 13 tests in `tests/test_completion_loop.py`, 3 loop-tick
tests plus the 23-step E2E in `tests/test_case_graph_services.py`; part of the
160-test suite (`python3 -m pytest tests/ -q` → `160 passed`).

## The `run_case` tick

One tick per case, deterministic against an injected `now` (simulated clock). Steps,
exactly as coded:

1. **Load state.** If `case.state ∈ FINAL_STATES` the tick returns immediately with
   `skipped=["final_state"]` — final cases are excluded *visibly* in the tick report,
   never mutated and never silently ignored (tested:
   `test_final_case_skipped_never_dropped_silently`).
2. **Promises evaluate.** `PromiseTrackerService.evaluate(case, now)` buckets open
   promises into DUE_SOON (≤ 6 h out) / OVERDUE / BREACHED; a breach
   (`promise_breach_score ≥ θ_breach = 0.3`, doc 05 §10) flips the promise to
   `broken` and audits `PROMISE_BREACHED`.
3. **Stuck sweep.** `CompletionLoop.stuck_sweep([case], now)` recomputes StuckScore
   from days-since-`last_progress_at`, lead score, and the heaviest open blocker
   weight; audits `scores.recomputed` for *every* active case (tested:
   `test_sweep_writes_score_audit_for_every_active_case`); cases ≥ θ_stuck (40) enter
   a queue sorted by score descending (tested:
   `test_stuck_high_value_case_floats_to_top`).
4. **NBA select.** `NextBestActionService.select` ranks deterministic candidates by
   the doc 05 §3 utility and re-arms `case.next_best_action` +
   `next_action_due_at = now + 4h`, auditing `NEXT_ACTION_CREATED`.
5. **ActionGate evaluate.** The selected action passes through the four-outcome gate
   (`ALLOW` / `BLOCK` / `REQUIRE_HUMAN_APPROVAL` / `ABSTAIN_MISSING_DATA`) with the
   NBA's confidence; every outcome is audited.
6. **Execute-if-allowed, with duplicate prevention.** Only `ALLOW`ed outbound asks
   (`send_follow_up`, `send_photo_request`, `ask_for_missing_info`) execute. Two
   layers prevent double-sends: (a) a per-case sent-set in the service — a repeat of
   the same ask within the cooldown is skipped and audited
   `FOLLOW_UP_RATE_LIMITED` (tested: `test_duplicate_followup_prevented`); (b)
   `CompletionLoop.send_followup` re-checks the full anti-spam policy (`can_touch`)
   before sending, auditing `followup.suppressed` with the concrete reason when
   refused, `followup.sent` when it goes out.
7. **Invariant assert.** The tick ends with
   `assert case.next_best_action is not None` and
   `assert case.next_action_due_at is not None`.

The tick report returned to the scheduler:
`{case_id, state, actions, skipped, promises: {bucket: count}, stuck, selected_action,
gate}`.

## The never-drop-a-case guarantee

**Every active case leaves the tick with a next action and a due time.** Enforced at
three points, all tested:

- at birth: `CaseGraphService.create_case` seeds `next_best_action` +
  `next_action_due_at` (tested: `test_create_case_writes_audit`);
- per tick: the step-7 assertion above — a violation is a crash, not a warning;
- fleet-wide: `CompletionLoop.check_invariants(cases)` returns a violation string for
  any active case missing either field, so the nightly sweep fails loudly (tested:
  `test_active_case_without_next_action_is_flagged`; final/terminal cases are exempt —
  `test_terminal_case_needs_no_next_action`).

This is doc 03 §2 invariant 1 / JSON `INV-1` made executable.

## Anti-spam rules (hard guarantees)

Policy object: `FollowUpPolicy(max_attempts=3, min_interval=20h,
quiet_hours=(21, 8), cadence=(24h, 48h, 72h))` — the doc 09 §2 defaults, tunable per
tenant. `can_touch(case, now)` refuses with an explicit reason; every refusal is
audited. All rules are **Implemented and tested**:

| Rule | Behavior | Test |
|---|---|---|
| Cooldown (min interval) | No two touches within 20 h; 10 rapid send attempts yield exactly 1 send | `test_rate_limit_10_sends_yield_1` |
| Max attempts | Hard cap 3 attempts, then the follow-up state flips `exhausted` and audits `followup.exhausted` | `test_max_attempts_then_exhausted` |
| Quiet hours | No contact 21:00–08:00 local (wrap-around handled) | `test_quiet_hours_blocked` |
| Opt-out | `case.opted_out` blocks all touches permanently (and the ActionGate independently BLOCKs outbound actions) | `test_optout_blocked`, gate: `test_block_on_optout` |
| Exhaustion → RECOVERY_LATER | `park_exhausted` transitions the case to RECOVERY_LATER with a +30-day wake action — parked, never spammed, never dropped | `test_exhausted_parks_to_recovery_later` |
| Duplicate ask | One outstanding ask per item per cooldown at the service layer | `test_duplicate_followup_prevented` |

Cadence: after each send the next follow-up is scheduled at the policy step
(24h → 48h → 72h), written into `next_best_action` / `next_action_due_at` — so the
schedule itself lives on the case row.

## Nightly sweep vs event-driven recompute

Per doc 09 §1 the loop has two triggers, and the scaffold implements the primitives
for both:

- **Event-driven recompute**: any inbound event (message, document, voice payload)
  should re-run the case's scoring + NBA immediately. In the scaffold this is simply
  calling `run_case(case, now=event_time)` — the tick is idempotent-safe thanks to
  the duplicate-prevention and cooldown layers, so eager recomputes cannot cause
  spam.
- **Nightly stuck sweep**: iterate all active cases — `stuck_sweep` recomputes and
  audits scores and produces the prioritized work queue; `check_invariants` fails
  loudly on any active case without a future action; exhausted cases are parked via
  `park_exhausted`; and due `RECOVERY_LATER` cases are woken via
  `transition(..., scheduled_wake=True)` into FOLLOW_UP_ACTIVE (the single documented
  final-state exception — see `state-machine.md`).

The wiring of these triggers to a real scheduler is part of the durability plan below
(**Designed**); the per-case behaviors they invoke are Implemented and tested.

## Durability plan

**Now (Implemented and tested)**: simulated clock. No wall time anywhere in the loop —
every method takes `now: datetime`, so tests are deterministic and restart survival is
*provable*: the scheduler's entire state (`FollowUpState` per case, next actions and
due times on the case rows) is plain data that can be dropped and rebuilt from case
rows, exactly like a durable queue would (tested:
`TestDurability::test_restart_survival_scheduler_state_rebuildable`).

**Later (Designed, doc 18)**: a durable substrate so a follow-up scheduled 72 h out
survives restarts — **Temporal** as the primary choice for durable follow-ups/loops,
with Celery+Redis / APScheduler over a Postgres-backed queue as the lighter MVP
alternative; LangGraph checkpointing for resumable case-graph execution. Doc 18 §
open-decisions item 4 (Temporal vs Celery+Redis) is an unresolved team-familiarity vs
guarantees trade-off. Because the loop's state already lives on the case rows and every
tick is re-derivable, swapping the in-memory driver for Temporal changes the scheduler,
not the contract documented here.
