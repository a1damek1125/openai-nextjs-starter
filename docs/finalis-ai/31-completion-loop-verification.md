# Finalis AI — Completion Loop Verification Plan

> **Status: ARCHITECTURE SPECIFIED, NOT IMPLEMENTED.** The completion loop is fully
> specified across `09` (loop engine), `03` (state machine + invariants), `05` (scores +
> §12 daily loop), and `22` (event model + delivery semantics). **No scheduler, no durable
> workflow, and no application code exist in this repository.** Nothing in this document is
> executable today; it defines what "the loop works" *means* as testable assertions, so the
> first line of implementation code is written against a verification contract, not a vibe.

This document is the acceptance test specification for the Completion Loop Engine. Every
assertion below maps to an invariant already stated in `03` §2, a hard guarantee in `05` §4,
or a delivery-semantics rule in `22` §2.3. When implementation begins (`17`), these become
the CI gate for the loop.

---

## 1. Verification checklist — testable assertions

Conventions for all tests:

- **Simulated clock.** All tests run against an injectable clock (`now()` is a dependency,
  never a syscall). Time advances only by explicit `clock.advance(Δt)` calls. This is
  non-negotiable — the loop is *about* time, and wall-clock tests are flaky and slow.
- **In-memory or ephemeral-Postgres store** seeded with fixture cases per test.
- **Event capture.** Tests assert on the emitted event stream (envelopes per `22` §2.1) and
  the `AuditEvent` table, not on internal state, wherever possible.
- Thresholds (`θ_stuck`, `θ_escalate`, quiet hours, `max_attempts`, cadences) come from a
  fixture `BusinessProfile`/`IndustryPlaybook`, mirroring production configurability (`03` §5).

### A1. Every active case has a next action (invariant 1a, `03` §2)

- **Assertion**: for every case in an *active* state (all states except `WON`, `LOST`,
  `COMPLETED`, `ABANDONED`, `RECOVERY_LATER`, per `03` §1), `next_best_action != null` at
  all times observable between transitions.
- **Test design**: property-based invariant check. Drive N randomly generated cases through
  randomized legal transition sequences (fuzz over the `03` §4 transition table) with random
  inbound events interleaved. After *every* applied transition and every sweep tick, scan
  all cases and assert the invariant. Separately: hand-craft a corrupted case (active,
  `next_best_action = null`) directly in the store, run one sweep tick, and assert the sweep
  **fails loudly** — emits `escalation.triggered{trigger: hard_rule, rule: "no_next_action"}`
  (`22` §2.3, "Nightly stuck sweep" row) rather than silently repairing or skipping.
- **Acceptance criterion**: zero invariant violations across ≥10,000 randomized
  transition/event steps; the corrupted-case probe produces exactly one `system`
  `escalation.triggered` AuditEvent naming the case.

### A2. Every next action has a due time (invariant 1b, `03` §2)

- **Assertion**: `next_best_action != null ⇒ next_action_due_at != null` and
  `next_action_due_at` is in the future at the moment it is set.
- **Test design**: same property harness as A1 with the additional predicate. Edge cases to
  pin explicitly: (a) NBA = `wait` still carries a concrete due time (the wait's re-evaluation
  time — a wait without a deadline is a stuck case wearing a costume); (b) a case entering
  `RECOVERY_LATER` must carry `wake_at` (its analogue, `03` §3.17); (c) after the due time
  passes without execution, the next sweep re-plans and sets a *new future* due time.
- **Acceptance criterion**: zero cases observed with an action and a null/past-at-assignment
  due time; every `RECOVERY_LATER` case has `wake_at`; a deliberately overdue case gets a
  fresh future `next_action_due_at` within one sweep tick.

### A3. Every promise has an owner (promisor) and a deadline (`04` `Promise`, `09` §3)

- **Assertion**: no `Promise` row can exist with `promisor_party_id = null` or
  `due_at = null`; every promise created from extraction (`call.transcribed` /
  `message.received` `detected_promises`) resolves the promisor to a `Party` and a concrete
  `due_at` before persistence.
- **Test design**: schema-level test (NOT NULL constraints reject direct inserts) plus
  pipeline test: feed transcripts containing vague promises ("I'll send it over sometime",
  "the technician will call you back") through the promise-application path (ORCH applying
  worker proposals, `22` `promise.created`). Where the utterance carries no explicit
  deadline, the pipeline must either assign the playbook default fulfillment window or route
  the proposal to human confirmation — never persist a deadline-less promise.
- **Acceptance criterion**: 100% of persisted `Promise` rows have non-null
  `promisor_party_id` and `due_at`; direct inserts violating either fail at the constraint;
  each vague-promise fixture yields either a defaulted `due_at` (with the defaulting noted
  in the `promise.created` payload) or a pending proposal — zero silent nulls.

### A4. Every missing item has a weight and blocker severity (`04` `MissingItem`, `05` §2)

- **Assertion**: every `MissingItem` carries `weight (w_i) ∈ (0, 1]` and an explicit
  `blocks_quote` boolean, sourced from `IndustryPlaybook.required_fields` — never defaulted
  to an implicit "unknown".
- **Test design**: instantiate intake for a fixture playbook and assert every generated
  `MissingItem` matches the playbook's declared `(w_i, blocks_quote)` pairs exactly. Negative
  test: a playbook field missing its weight must fail playbook validation at load time (bad
  config fails at config time, not at 2 a.m. in the sweep). Verify `MIS` recomputation (`05`
  §2) reproduces `Σ w_i·m_i` from the stored rows bit-for-bit against a hand-computed value.
- **Acceptance criterion**: zero `MissingItem` rows with null/zero weight or null
  `blocks_quote`; malformed playbook rejected at load; `MIS_normalized` matches the
  hand-computed oracle to float tolerance on ≥20 fixture case configurations.

### A5. Stuck cases are detected (`05` §9)

- **Assertion**: when `StuckScore = DaysSinceProgress · LeadScore · MissingBlockerWeight`
  crosses `θ_stuck`, the case is surfaced within one sweep tick: a follow-up is enqueued or
  an owner alert is created (whichever autonomy permits), and the case appears in the
  stuck-cases projection.
- **Test design**: simulated-clock scenario. Seed a Hot case (`LeadScore ≥ 70`) with a
  blocking `MissingItem` (`w_i = 0.9`), then advance the clock day by day running the
  nightly sweep each tick with no inbound events. Compute the expected day StuckScore
  crosses `θ_stuck`. Also test the ordering property: two stuck cases with different
  `LeadScore` must surface with the higher-value case ranked first (`09` §8, "hot-but-stuck
  cases float to the top").
- **Acceptance criterion**: on the first sweep tick after the threshold crossing — not
  before, not late — the case emits `scores.recomputed` with `stuck_score ≥ θ_stuck`
  followed by either `action.proposed` (follow-up) or an owner `Task`/alert; detection lag
  ≤ 1 sweep interval; ranking matches LeadScore order.

### A6. Follow-up is rate-limited (`05` §4 hard guarantees, `09` §2) — adversarial

- **Assertion**: the hard guarantees hold *regardless of scores or caller behavior*: never
  during quiet hours, never inside the minimum inter-touch interval, never beyond
  `max_attempts`.
- **Test design (adversarial)**: attempt to violate each guarantee on purpose.
  1. **Burst test**: enqueue 10 send-follow-up commands for the same party in a row (via
     direct scheduler calls, duplicated `followup.scheduled` events, and API calls) —
     **expect exactly 1 send**; the other 9 are rejected/coalesced with a logged reason
     (min-interval / AnnoyanceRisk gate), and the API path returns `403 autonomy_blocked`
     per `22` §1.4, not `429`.
  2. **Quiet-hours test**: schedule a follow-up due at 03:00 party-local time; assert it is
     deferred to the window edge, never sent early — including when the *score* says urgent.
  3. **Max-attempts test**: run a cadence to `max_attempts` unanswered touches; assert
     attempt `max_attempts + 1` is impossible from any code path (sweep, event replay, API)
     and the case parks (see A7).
  4. **Clock-skew test**: deliver a duplicated `followup.scheduled` event after a simulated
     restart; assert idempotent single send (dedup on `event_id`/`action_id`, `22` §2.3).
- **Acceptance criterion**: 10-in-a-row burst → exactly 1 outbound `message.sent`; zero
  sends inside quiet hours or the cool-down window across all adversarial fixtures; zero
  sends past `max_attempts`; every suppressed attempt leaves an AuditEvent naming the gate
  that blocked it.

### A7. No spam loops — exhaustion parks and never re-arms itself (`09` §1–2, `22` `followup.exhausted`)

- **Assertion**: an exhausted follow-up sequence transitions the case to `RECOVERY_LATER`
  (or `ABANDONED` via the global closure edge) exactly once, and nothing in the system —
  sweep, score recomputation, event replay, projection rebuild — re-arms the same sequence.
  A parked case contacts no one before `wake_at`.
- **Test design (loop detection)**: run a full cadence to exhaustion; assert
  `followup.exhausted` → `case.parked{to_state: RECOVERY_LATER, wake_at}` fires **once**.
  Then be hostile: run 30 more nightly sweeps, replay the entire event log from offset zero
  (at-least-once semantics say this must be safe), and emit a duplicate
  `followup.exhausted`. Assert: zero outbound actions before `wake_at`, zero new
  `FollowUpSequence` activations, no `RECOVERY_LATER → FOLLOW_UP_ACTIVE → exhausted →
  RECOVERY_LATER` ping-pong. On `wake_at`, the case wakes exactly once (`case.woken`), gets
  a *fresh* sequence with a reset attempt counter — and if that also exhausts, it parks
  again with a *later* `wake_at` or closes via the global closure edge (`03` §4): the
  park→wake→park cycle must be provably non-tightening (each `wake_at` strictly later,
  bounded number of recovery cycles per playbook).
- **Acceptance criterion**: exactly one park transition per exhaustion; zero outbound
  actions during park across sweeps + full replay + duplicate events; wake fires exactly
  once at `wake_at`; consecutive `wake_at` values strictly increase; recovery cycles capped
  at the playbook bound.

### A8. Human escalation works (`03` §2 invariant 5, `13` §2)

- **Assertion**: `EscalationScore ≥ θ_escalate` (or a hard-override rule) from *any* active
  state forces `HUMAN_REVIEW_REQUIRED`, creates a `HumanApproval`, and freezes effective
  autonomy at Level 2 — no outbound client-facing action executes until a human decides.
- **Test design**: parameterized over every active state: inject an inbound event engineered
  to push `EscalationScore` past `θ_escalate`; assert the transition fires from each state
  (the global interrupt edge is truly global). Then attempt outbound actions through every
  path — NBA executor, follow-up worker, direct API `POST .../messages` with `sent_by=ai` —
  and assert all are blocked (`403 autonomy_blocked` referencing the *existing* approval id,
  no second approval minted, per `22` §1.4). Verify hard overrides (LegalSensitivity=1 on a
  signing decision; safety emergency) escalate even with a low accumulated score (`13` §2.1).
  Verify release: `POST /approvals/{id}/decision {approve}` unfreezes and applies the chosen
  transition; a second decision returns `409 already_decided`.
- **Acceptance criterion**: 100% of active states escalate on threshold breach;
  `escalation.triggered` + `case.state_changed → HUMAN_REVIEW_REQUIRED` +
  `approval.requested` all present and hash-chained; zero outbound actions execute during
  the freeze across all attack paths; both hard overrides escalate score-independently;
  decision idempotency holds.

### A9. All closure paths are reachable (`03` §1, `09` §1)

- **Assertion**: each of `WON`, `LOST`, `COMPLETED`, `ABANDONED`, `RECOVERY_LATER` is
  reachable via at least one legal transition sequence from `NEW_CONTACT`, and no other
  state ever behaves as terminal (no absorbing states outside the declared set).
- **Test design**: model-based test. Encode the `03` §4 transition table as a graph;
  (1) graph reachability check: every closure state reachable from `NEW_CONTACT`; (2) for
  each closure state, execute one concrete end-to-end scenario through the real engine
  (e.g. offer accepted → `WON`; competitor chosen with reason → `LOST`; service delivered →
  `COMPLETED`; STOP received → `ABANDONED`; cadence exhausted → `RECOVERY_LATER`);
  (3) absorbing-state detection: from the random walks in A1, assert no case ever sits in a
  non-closure state with no legal outbound transition; (4) assert the engine *rejects*
  transitions not in the table (`409 invalid_transition`) — reachability must come from the
  spec'd edges, not from a permissive engine.
- **Acceptance criterion**: all five closure scenarios complete through the real engine with
  correct required data (`LOST` demands a loss reason; `RECOVERY_LATER` demands `wake_at`);
  graph analysis finds zero undeclared absorbing states; every off-table transition attempt
  is rejected.

### A10. Timeline updates after every action (`04` `AuditEvent`, `22` §2.1)

- **Assertion**: every executed `Action` (message sent, call placed, doc requested, booking
  made, follow-up sent) produces at least one AuditEvent, and the case timeline projection
  reflects it — no silent actions.
- **Test design**: instrument the executor with a spy; run the A1 random-walk corpus and the
  A6–A8 scenarios; for every executor invocation, assert a matching `action.executed` (or
  `action.failed`) AuditEvent exists with correct `causation_id`/`correlation_id` linkage,
  and that rebuilding the timeline projection from the event log alone reproduces the exact
  action list (event-sourced rebuild property, `22` §2.1). Diff `count(executor calls)`
  against `count(action AuditEvents)` — the numbers must match exactly.
- **Acceptance criterion**: executor-call count == action-event count on every run; replayed
  projection is byte-equivalent to the live projection; every event carries valid causation
  linkage back to a root inbound event or sweep tick.

### A11. Audit events on every transition, hash chain intact (`03` §2 invariant 4, `13` §5)

- **Assertion**: every state transition writes exactly one
  `AuditEvent{from_state, to_state, actor, reason, evidence_refs}` **in the same transaction**
  as the state change, and the per-tenant `hash_prev` chain verifies end-to-end.
- **Test design**: (1) count check: transitions applied == transition AuditEvents, over the
  full A1 corpus; (2) atomicity check: inject a fault (kill/abort) between state write and
  event write — assert both roll back together, never a transition without its event or vice
  versa; (3) tamper check: mutate one historical event's payload directly in the store, run
  the chain verifier (`GET /audit-events/verify`, `22`), assert it reports the break at
  exactly that event; (4) append-only check: UPDATE/DELETE on the audit table is rejected at
  the database layer (permissions/trigger), not merely unused by the app.
- **Acceptance criterion**: 1:1 transition-to-event mapping with zero orphans on either
  side under fault injection; verifier passes on untampered logs and pinpoints any single
  mutated event; direct UPDATE/DELETE against audit rows fails.

---

## 2. Durable-execution verification

The loop's core promise (`09` §1) is that a follow-up scheduled 72 hours out survives
anything short of losing the database. Two properties must be *proven*, not assumed from
the substrate's marketing page:

### D1. Restart survival

- **What must be proven**: a timer scheduled at `t+72h` fires after the process hosting the
  scheduler has been killed and restarted — including when the restart happens *after* the
  due time has already passed (late fire, never lost fire).
- **Test design (simulated clock)**: schedule a follow-up at `t+72h` against the durable
  store; hard-kill the scheduler process (SIGKILL, no shutdown hooks — a crash, not a
  graceful stop); restart with a fresh process against the same store; advance the simulated
  clock past `t+72h`; assert exactly one `followup.sent`. Variants: (a) kill *before* due
  time, restart before due time; (b) kill before due time, restart *after* due time — the
  overdue timer must fire immediately on recovery, once; (c) kill *mid-execution* of the
  fire (after the timer claim, before the send completes) — recovery must resolve to exactly
  one send via the `action_id` idempotency key (`22` §2.3). Same battery for promise
  deadlines, `wake_at` park timers, and approval SLA timers — all four timer families in
  `22` §2.3.
- **Acceptance criterion**: exactly-one-fire for every timer family across all three
  kill/restart variants; zero lost timers; zero double-fires; recovery lag for overdue
  timers ≤ one scheduler poll interval.

### D2. Idempotent consumers

- **What must be proven**: at-least-once delivery (`22` §2.3) is safe — the same event
  delivered twice produces **one** action.
- **Test design**: for each side-effecting consumer (send executor, call initiator,
  transition applier, promise-timer arm), deliver the identical envelope (same `event_id`)
  twice: back-to-back, interleaved with other events, and split across a process restart
  (delivered once before the kill, once after). Assert one side effect, and that the
  duplicate is acknowledged (not dead-lettered — duplicates are normal, not errors). Also
  verify per-case ordering under concurrency: two workers pulling the same case's lane must
  serialize (`SELECT ... FOR UPDATE SKIP LOCKED` on the case lane in the Postgres MVP).
- **Acceptance criterion**: one side effect per unique `event_id`/`action_id` across all
  duplication patterns including cross-restart; duplicates acked cleanly; per-case event
  order preserved under 2+ concurrent consumers; cross-case parallelism unaffected.

---

## 3. Implementation tasks (ordered)

The verification plan above deliberately does not require Temporal to be provable. Order of
work:

1. **T1 — Simulated-clock loop core (pure Python/TS, no infrastructure).** Implement the
   state machine (`03`), the scoring functions (`05` — they are deterministic and pure by
   design), the NBA selector, the follow-up gate, and a single-process scheduler whose only
   time source is an injected clock and whose only store is an in-memory/SQLite repository
   behind the same interface Postgres will implement. **Every assertion A1–A11 must pass
   here first.** This proves the *logic* — invariants, anti-spam gates, park/wake, escalation
   — with sub-second test runs and zero infrastructure. No Temporal needed to prove the loop.
2. **T2 — Durable store + transactional outbox on Postgres.** Swap the repository for
   Postgres; add the AuditEvent-as-outbox write (`22` §2.1), the hash chain, per-case lanes
   (`FOR UPDATE SKIP LOCKED`), and the `scheduled_at`-polling timer table. Re-run A1–A11
   unchanged (same tests, real store), then prove D1/D2 with process-kill harnesses.
3. **T3 — Temporal/queue adapter (optional upgrade, same contract).** Introduce a
   `DurableScheduler` interface with two implementations: the T2 Postgres poller (MVP) and a
   Temporal-backed one (timers as workflow sleeps, signals for events). The D1/D2 test
   battery runs against *both* via the shared interface — the substrate is swappable
   precisely because the acceptance criteria are substrate-agnostic.
4. **T4 — CI gating.** A1–A11 + D1/D2 become the merge gate for any change touching the
   Orchestrator, scheduler, follow-up worker, or state machine; the A1 fuzz corpus runs
   nightly with a larger step budget.

---

## 4. Traceability

| Assertion | Spec source |
|---|---|
| A1, A2 | `03` §2 invariant 1; `22` §2.3 sweep row |
| A3 | `04` `Promise`; `09` §3 |
| A4 | `04` `MissingItem`; `05` §2 |
| A5 | `05` §9; `09` §8 |
| A6 | `05` §4 hard guarantees; `09` §2; `22` §1.4 |
| A7 | `09` §1–2; `03` §3.17, §4 global closure edge; `22` `followup.exhausted`/`case.parked`/`case.woken` |
| A8 | `03` §2 invariants 2+5; `13` §2; `22` §1.4 202-vs-403 |
| A9 | `03` §1, §4; `09` §1 closure paths |
| A10 | `04` `AuditEvent`; `22` §2.1 event-sourcing |
| A11 | `03` §2 invariant 4; `13` §5 hash chain |
| D1, D2 | `09` §1 durability; `22` §2.3 delivery semantics |
