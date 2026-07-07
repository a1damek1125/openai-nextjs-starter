# Finalis AI — State Machine Autofix & Test Report

> Follow-up to `27-state-machine-verification.md` (which audited the *specification*, with the
> ground truth "nothing is implemented and no tests exist"). That is no longer true: the state
> machine is now executable in `finalis/state_machine.py` and tested in
> `tests/test_state_machine.py` on branch `claude/finalis-ai-enterprise-e2e-autofix`
> (part of the **102-test passing** suite).

---

## 1. What was verified / implemented

| Doc-27 acceptance criterion | Status in scaffold | Executable evidence (`tests/test_state_machine.py`) |
|---|---|---|
| 17 states implemented 1:1 with 03 §1 | Done — `CaseState` enum, partitioned into `ACTIVE_STATES` (12), `CLOSED_REOPENABLE_STATES` (WON/LOST), `TERMINAL_STATES` (COMPLETED/ABANDONED), `PARKED_STATES` (RECOVERY_LATER) | `test_17_states`, `test_partition_is_complete_and_disjoint` |
| Transition table transcribed from 03 §4 | Done — `TRANSITIONS` dict, one row per state, incl. the HUMAN_REVIEW_REQUIRED → any-active + WON/LOST/ABANDONED expansion | `test_legal_happy_path`, `test_illegal_transition_rejected` (typed `IllegalTransition`) |
| Two global edges with guards | Done — `is_legal()` takes `escalation_interrupt` (any active → HRR) and `hard_opt_out` / `followup_exhausted` (any non-terminal → ABANDONED\|LOST) | `test_escalation_interrupt_from_any_active_state`, `test_escalation_interrupt_not_from_terminal`, `test_stop_optout_closure_edge_from_any_non_terminal`, `test_followup_exhaustion_closure_edge` |
| Invariant: entering HRR freezes autonomy at L2, exit restores | Done — `transition()` sets/clears `case.autonomy_frozen_at` | `test_human_review_freezes_autonomy_at_2` (asserts effective 4→2→4) |
| Invariant: hard opt-out is permanent | Done — `case.opted_out = True` on the closure edge; completion loop refuses all future touches | `test_hard_optout_suppresses_permanently` (+ `test_optout_blocked` in `tests/test_completion_loop.py`) |
| Invariant: one AuditEvent per transition | Done — every `transition()` appends `case.state_changed` to the hash-chained log | `test_legal_happy_path` asserts event count == path length and `audit.verify_chain()` |
| Reachability (doc 27 §1, criterion 6) | Proven by an executable BFS from NEW_CONTACT | `test_all_states_reachable_from_new_contact` (asserts `seen == set(CaseState)`); `test_every_non_terminal_has_an_exit` |
| Terminals reject everything | Tested exhaustively — every (terminal, target) pair, all 17 targets each | `test_terminal_states_reject_everything`, `test_terminals_have_no_exits` |
| Property test (criterion 5, scaled down) | 50 random walks × 20 steps of legal transitions; audit chain must verify after every walk | `test_random_walk_never_violates_invariants` (seeded `random.Random(42)` for determinism) |
| JSON ↔ Python consistency (criterion 1, CI-drift guard) | Done — `TestJsonConsistency` loads `docs/finalis-ai/state-machine.finalis.json`, expands the `ANY_ACTIVE` wildcard, and asserts exact pair-set equality plus both global edges present | `test_same_state_set`, `test_same_transitions`, `test_global_edges_present` |

Note on criterion 1's stronger form ("JSON is the single source of truth, loaded at startup"):
the scaffold keeps a hardcoded Python table *validated against* the JSON by test rather than
loading the JSON at import time. Functionally equivalent for drift detection (the test fails CI
on any divergence), but the production module should flip to load-from-JSON per the criterion.

## 2. Doc-27 issues A–F — status in the scaffold

| Issue | Status | Detail and recommended fix | Backlog landing (doc 35) |
|---|---|---|---|
| **A. HRR has no terminal timeout** (High) | **OPEN — design gap, not code.** The scaffold enforces the freeze-to-L2 invariant but nothing moves a case out of HRR on human silence; `stuck_sweep` sees HRR as active with a next action, so it never fails loudly. | Specify the escalation ladder (re-route → `max_review_dwell` → notify owner-of-owners → auto-park to RECOVERY_LATER with `review_timeout`; never auto-execute the pending client action). Add HRR `time_in_state` to sweep loud-failure checks. | Safety/orchestrator epic — decision item before production, config knob `max_review_dwell` in BusinessProfile |
| **B. Rescan loop counter** (Medium) | **OPEN.** WAITING_FOR_DOCUMENTS ↔ DOCUMENT_ANALYSIS cycles are legal and uncounted; `Case` has no `rescan_count`. | Add per-case, per-doc-type `rescan_count`; at `max_rescans` (default 3) force HRR with reason `repeated_unreadable_uploads`; internal timeout on DOCUMENT_ANALYSIS. | Data-model + document-intelligence epic (cheap now, migration later) |
| **C. Global case-age limit** (Low–Medium) | **OPEN.** OFFER_SENT/NEGOTIATION/FOLLOW_UP_ACTIVE cycles reset the per-sequence follow-up budget; nothing bounds total case age or offer revisions. | Tenant-configurable `max_case_age_days` / `max_offer_revisions` in BusinessProfile; breach raises StuckScore to force the escalation interrupt (reuses existing machinery, no new edge). | Completion-loop epic, config-only change |
| **D. WON → RECOVERY_LATER semantics** (Medium) | **OPEN — design decision.** The scaffold transcribes the edge as documented (and tests it as legal), so it inherits the spec's contradiction: COMPLETED spawns a linked case for renewals, WON reopens in place. | Adopt the §3.15 pattern uniformly: WON spawns a linked child case born in RECOVERY_LATER (`recovery_reason=upsell`); keep direct reopen only for LOST. This changes the transition table + case-linking model — decide before the executor is coded. | Blocks-implementation decision ticket (doc 27 flags it "decision required") |
| **E. Transition atomicity / rollback** (High) | **PARTIALLY ADDRESSED.** In the scaffold a transition is atomic in-memory: legality check → state write → invariant side-effects → audit append happen in one call, and illegal requests raise before any mutation. What is *not* addressed: coupling with real side-effecting actions across a process/DB boundary. | Production needs the doc-27 protocol: side effects before state commit with idempotency keys; state write + AuditEvent in one DB transaction (transactional outbox / saga); `action_failed` events with no state change on failure. | Executor core-loop epic — blocks production implementation |
| **F. QUALIFIED transience** (Low) | **OPEN.** QUALIFIED is a full persisted enum member in the scaffold (tests route through it); the "no dwell" convention has no `due_at` rule or timeout. | Doc 27's option (ii): keep it persisted with `next_action=route_case, due_at=now` + short timeout (1h) escalated by the stuck sweep. Less invasive than removing it from the enum, crash-safe. | Invariant-checker ticket; must be resolved before the production invariant checker ships |

## 3. One real autofix found during test-writing

The JSON-consistency test **initially failed** against
`docs/finalis-ai/state-machine.finalis.json`: the JSON compresses HUMAN_REVIEW_REQUIRED's exits
as a single wildcard row (`"to": "ANY_ACTIVE"`), while the Python table stores the expanded set.
The naive pair-set comparison reported the wildcard row as json-only and eleven expanded edges
as py-only. The fix (in `TestJsonConsistency::test_same_transitions`) expands `ANY_ACTIVE` to
`ACTIVE_STATES − {HUMAN_REVIEW_REQUIRED}` before comparing, and the assertion prints both
difference sets on failure.

This is exactly the class of drift the test now permanently guards against: any future edit to
either artifact — a new edge in the JSON, a removed target in Python, a change to what counts as
"active" — breaks CI with a named diff instead of silently forking the spec from the code.

## 4. Verdict

The state machine is **implemented, exhaustively edge-tested, property-tested, and
consistency-locked to the machine-readable spec**. Doc 27's acceptance criteria 2, 3 (freeze +
opt-out portions), 4 (audit-per-transition), 5 (scaled), and 6 are executable and green;
criterion 1 is met in drift-guard form; criterion 7 (issues A–F) remains the gating list above —
D and E are the two that must be decided before production executor code is written.
