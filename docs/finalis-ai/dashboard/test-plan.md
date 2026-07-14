# Command Center — Test Plan

**Status: 13/13 mandated scenarios PASSING** in `tests/test_dashboard.py`, plus regression
tests in `tests/test_bugfix_regressions.py` and the cross-module proof in
`tests/test_full_product_e2e.py`. Command: `python3 -m pytest tests/ -q` → **212 passed**.

## Mandated scenarios → tests

| # | Scenario | Test |
|---|---|---|
| 1 | Summary renders correctly | `TestSummary.test_1_summary_correct` |
| 2 | Action queue sorts by urgency/value/risk/due | `TestActionQueue.test_2_sorted_by_urgency_value_risk_due` |
| 3 | Approvals show approve/reject/edit | `TestApprovals.test_3_pending_approvals_visible_with_options` |
| 4 | Stuck cases with blocker reason | `TestQueues.test_4_stuck_cases_with_blocker` |
| 5 | Missing-info queue shows required items | `TestQueues.test_5_missing_info_queue` |
| 6 | Overdue promises in tracker | `TestQueues.test_6_overdue_promises_in_tracker` |
| 7 | Offer board shows no-response cases | `TestQueues.test_7_offer_followup_board` |
| 8 | Pipeline groups by state | `TestQueues.test_8_pipeline_grouped_by_state` |
| 9 | Risk alerts show high-risk cases | `TestQueues.test_9_risk_alerts` |
| 10 | Activity timeline shows recent events | `TestQueues.test_10_activity_timeline` (+ cross-tenant exclusion) |
| 11 | Cannot approve another tenant's action | `TestApprovals.test_11_cannot_approve_other_tenant` (+ `ai_worker`/`viewer` role denials) |
| 12 | Empty state handled cleanly | `TestSummary.test_12_empty_state_clean` |
| 13 | Full render (loading/error = Designed) | `TestRenderAndE2E.test_13_render_contains_all_components` (all 11 component markers) |

## E2E approve flow (passing)

`TestRenderAndE2E.test_e2e_owner_approves_from_dashboard`: open dashboard → approval
visible → owner approves **with an edit** → status APPROVED → item leaves queue →
`HUMAN_APPROVAL_GRANTED` audit with `via: dashboard`, `edited: true` → hash chain verified
→ re-render shows empty approval state. The full-product E2E additionally proves the
approved offer continues into OFFER_SENT → follow-up → WON.

## Regression tests (bug-fix pass)

`tests/test_bugfix_regressions.py`: audit events carry tamper-protected `created_at`
(timestamp forgery breaks the chain); the daily send cap counts across action types,
per-case, and resets next day; an expired snooze returns the case to the action queue.

## Language rule

`test_explain_translates_scores_to_business_language` + in-queue assertions: no bare
decimals, no "score", money/value/days in plain words.

## Next stages (not implemented)

Playwright browser E2E once the Next.js UI exists (replaying the approve flow through real
clicks); RBAC tests against real auth sessions; pagination/performance against Postgres
with 10k cases; SSE update tests.
