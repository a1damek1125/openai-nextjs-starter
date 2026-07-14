# Case Graph — E2E Test Plan

> **Ground truth:** branch `claude/finalis-case-graph-completion-loop`, 160 tests
> passing (`python3 -m pytest tests/ -q`). The mandated 23-step E2E is
> `tests/test_case_graph_services.py::TestE2EHvacLifecycle::test_full_lifecycle` —
> a single test that drives one HVAC case from voice intake to WON (and beyond, via
> human override) against a simulated clock (`T0 = 2026-07-07 10:00`), asserting every
> gate and audit along the way.

## 1. The 23-step E2E lifecycle — step-by-step mapping

Every row below is implemented and asserted in `TestE2EHvacLifecycle::test_full_lifecycle`
today. "Assertion" quotes what the test actually checks.

| # | Step | Code exercised | Assertion in the test |
|---|---|---|---|
| 1 | Case created from a voice extraction payload (`tenant_id="hvac-1"`, `source_channel="voice"`) | `CaseGraphService.create_case` | Case exists; `CASE_CREATED` audit verified at step 10 |
| 2 | Client party attached (Jan Kowalski) | `attach_entity(edge_type="PARTY")` | `PARTY_ATTACHED` audit verified at step 10; party appears in graph nodes (step 23 read) |
| 3 | Missing items detected against the HVAC profile, given known facts (contact, service_type, urgency) | `MissingInfoService.detect` / `open_blockers` | `{"address", "installation_photo"} <= open_blockers` |
| 4 | Promise recorded: client will "send photos" by T0+1d | `case.promises.append(Promise(...))` + audit | `PROMISE_CREATED` audit verified at step 10 |
| 5 | Legal transitions `NEW_CONTACT → INTAKE_IN_PROGRESS → WAITING_FOR_CLIENT_INFO` | `state_machine.transition` ×2 | No `IllegalTransition` raised; both counted in the 7 `case.state_changed` events at step 23 |
| 6 | Completion-loop tick 1 at T0 (`lead_score=72`, `value_estimate=10000`) | `CompletionLoopService.run_case` | Tick returns the §1.11 result dict (api-contracts.md) |
| 7 | Next Best Action selected deterministically from the open blockers | `NextBestActionService.select` | `tick1["selected_action"] in ("send_photo_request", "ask_for_missing_info")` |
| 8 | Action gate rules on the selected action | `ActionGateService.evaluate` | `tick1["gate"] == "ALLOW"` |
| 9 | Follow-up actually sent (anti-spam policy permits) | `CompletionLoop.send_followup` | `tick1["actions"]` non-empty ("allowed follow-up should be sent") |
| 10 | **Audit checkpoint** — everything so far is on the chain | `AuditLog.events` | Events exist for each of: `CASE_CREATED`, `PARTY_ATTACHED`, `MISSING_INFO_DETECTED`, `PROMISE_CREATED`, `NEXT_ACTION_CREATED`, `ACTION_CREATED`, `followup.sent` |
| 11 | Client sends the photo — missing item resolved | `MissingInfoService.resolve("installation_photo")` | Returns True; `MISSING_INFO_RESOLVED` audit written |
| 12 | The "send photos" promise fulfilled | `PromiseTrackerService.fulfill` | Promise status → `fulfilled`; `PROMISE_FULFILLED` audit written |
| 13 | Address still missing — case does **not** advance | (state unchanged; blocker check) | `case.state is WAITING_FOR_CLIENT_INFO`; `open_blockers == {"address"}` |
| 14 | Address arrives — last blocker resolved | `MissingInfoService.resolve("address")` | `open_blockers == []` |
| 15 | `→ QUALIFIED → QUOTE_PREPARATION` | `state_machine.transition` ×2 | Legal; counted in the 7 state changes |
| 16 | DecisionBrief produced (audit-event record in the scaffold — no entity yet) | `audit.append("DECISION_BRIEF_CREATED", ...)` | Payload carries summary / recommended_action / `requires_human_approval: True` |
| 17 | Offer send hits the gate | `ActionGateService.evaluate("send_offer_commitment")` | `gate_d.outcome == "REQUIRE_HUMAN_APPROVAL"` (offer commitments are never autonomous) |
| 18 | Human approves; offer goes out | `audit.append("HUMAN_APPROVAL_GRANTED")` + `transition(OFFER_SENT, actor="human")` | Transition applied |
| 19 | Two days pass with no client response (simulated clock; NBA/due primed for follow-up) | case fields `next_best_action` / `next_action_due_at` / `last_progress_at` | Setup for tick 2 (deterministic timeout, no wall clock) |
| 20 | Completion-loop tick 2 at T0+2d schedules the follow-up | `CompletionLoopService.run_case` | `tick2["selected_action"] == "send_follow_up"` |
| 21 | Client accepts → `WON` (human actor) | `transition(WON, actor="human")` | `case.state is WON` |
| 22 | **Final-state override rule enforced** | `transition(WON → SCHEDULED)` | Without override: `pytest.raises(IllegalTransition)`; with `actor="human", human_override=True`: succeeds |
| 23 | Timeline + tamper-evident chain | `get_case_graph` / `AuditLog.verify_chain` | `len(timeline) >= 15`; `audit.verify_chain()` is True; exactly **7** `case.state_changed` events — every transition audited, none missing, none extra |

## 2. The other 15 mandated test areas — mapping to test classes

All in `tests/test_case_graph_services.py` unless another file is named. All passing.

| # | Area | Test class :: test(s) |
|---|---|---|
| 1 | Case creation (audit + next-action invariant) | `TestCaseGraphService::test_create_case_writes_audit` |
| 2 | Legal transitions | `tests/test_state_machine.py::TestTransitions::test_legal_happy_path` (plus `TestStateSets` reachability and `TestJsonConsistency` against `state-machine.finalis.json`) |
| 3 | Illegal transition blocking | `tests/test_state_machine.py::TestTransitions::test_illegal_transition_rejected`, `::test_terminal_states_reject_everything` |
| 4 | Missing-info blocking | `TestMissingInfoService::test_detect_from_hvac_profile`, `::test_blockers_block_and_resolution_unblocks` (blocker set), `::test_no_duplicate_detection` |
| 5 | Missing-info resolution | `TestMissingInfoService::test_blockers_block_and_resolution_unblocks` (resolve unblocks; `MISSING_INFO_RESOLVED` count) |
| 6 | Promise creation + status evaluation (DUE_SOON / OVERDUE / BREACHED / fulfill) | `TestPromiseTracker::test_statuses`, `::test_fulfill` |
| 7 | Promise overdue/breach thresholds against the clock | `TestPromiseTracker::test_statuses` plus `tests/test_completion_loop.py::TestPromiseTracker` (`test_overdue_promise_breaches`, `test_slightly_overdue_low_impact_does_not_breach`, `test_promise_not_yet_due_untouched`) |
| 8 | Loop selects a next action and respects the gate | `TestCompletionLoopService::test_run_case_selects_action_and_respects_gate` |
| 9 | Duplicate prevention (one outstanding ask per cooldown) | `TestCompletionLoopService::test_duplicate_followup_prevented` (asserts `duplicate_followup` skip or `FOLLOW_UP_RATE_LIMITED`/`followup.suppressed` audit) |
| 10 | Gate ALLOW / BLOCK / ABSTAIN paths | `TestActionGate::test_allow_low_risk`, `::test_block_on_optout`, `::test_abstain_on_low_confidence` |
| 11 | Gate human-review paths (high-risk, frozen autonomy, unknown-action conservative default) | `TestActionGate::test_require_human_for_high_risk`, `::test_frozen_autonomy_requires_human`, `::test_unknown_action_conservative` |
| 12 | Audit written + chain integrity + tamper detection | Per-event asserts throughout `test_case_graph_services.py`; `tests/test_autonomy_audit.py::TestAuditChain` (`test_append_and_verify`, `test_tamper_detection`, `test_chain_links`, `test_filtering`) |
| 13 | Final-state override rule | `tests/test_state_machine.py::TestTransitions::test_final_states_require_human_override_to_exit`; re-verified in E2E step 22 |
| 14 | Tenant isolation — graph read | `TestCaseGraphService::test_tenant_isolation_on_graph_read` (`PermissionError`) |
| 15 | Tenant isolation — entity attach | `TestCaseGraphService::test_tenant_isolation_on_attach` (`PermissionError`) |

Plus the LGGT placeholder callability check —
`TestLGGTPlaceholderCallable::test_placeholder_certifies_without_runtime` (certify
without any runtime; `verdict == "heuristic"`, `audit_id` set, `certainty.stamped` on
the chain) — and the never-drop guarantee for closed cases:
`TestCompletionLoopService::test_final_case_skipped_never_dropped_silently`
(`skipped == ["final_state"]`, never a silent no-op).

Supporting depth outside this module's suite (same 160-test run):
`tests/test_completion_loop.py` (`TestInvariants`, `TestAntiSpam` — rate limit, max
attempts, quiet hours, opt-out, exhaustion parking; `TestStuckSweep`; `TestDurability`
restart-survival) and `tests/test_autonomy_audit.py::TestAutonomyGate`.

## 3. What the E2E does NOT cover — honest gaps and next stages

The 23-step E2E proves the **business logic** end to end. It deliberately does not
prove:

1. **Persistence.** Everything is in-memory dataclasses; no Postgres, no migrations, no
   row-level security, no transactional semantics, no restart with real data (the
   scheduler-state rebuild test simulates it with plain data, not a database).
   *Next stage:* repository layer + the same 23 steps against Postgres with RLS on
   `tenant_id`; kill-and-restart mid-lifecycle.
2. **The API layer.** No HTTP server exists; the REST contracts in `api-contracts.md`
   are Designed. Auth, idempotency keys, error envelopes, pagination, and 409/422
   semantics are untested.
   *Next stage:* thin FastAPI (or equivalent) shell over the services; contract tests
   generated from `openapi.finalis.yaml`; the E2E re-run through HTTP.
3. **Real channels.** `followup.sent` is an audit event, not an SMS/WhatsApp/voice
   call; no provider integration, delivery failure, inbound webhook, or opt-out
   keyword parsing is exercised.
   *Next stage:* channel adapters with sandbox providers; failure-injection tests
   (delivery failure must not lose the case's next action).
4. **Concurrency.** Single-threaded, one case, simulated clock. No concurrent loop
   ticks on the same case, no double-webhook races, no idempotency under retry, no
   lock contention.
   *Next stage:* per-case locking/serialization in the loop runner; property tests
   for "at most one outbound per item per cooldown" under parallel ticks.

Also out of scope of this E2E (covered elsewhere or not at all): voice/OCR/WebScout
pipelines (own suites), multi-case scheduling at scale, wall-clock time zones for
quiet hours, and any LGGT runtime behavior (Phase 2 — see
`lggt-certainty-core-placeholder.md`).
