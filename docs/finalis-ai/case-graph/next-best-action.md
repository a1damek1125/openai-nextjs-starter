# Case Graph — Next Best Action (NBA) Engine

> **Ground truth**: `finalis/case_services.py` (`NextBestActionService`) +
> `finalis/scoring.py` (§3 block: `ActionCandidate`, `nba_utility`,
> `next_best_action`), branch `claude/finalis-case-graph-completion-loop`,
> 160 tests passing. Spec: `docs/finalis-ai/05-algorithms-and-scoring.md` §3;
> defect history: `docs/finalis-ai/40-algorithm-autofix-and-test-report.md` (#4).

## 1. The utility model

For every candidate action `a` (doc 05 §3):

```
Utility(a) = P(close | a) · Value − Cost(a) − Risk(a) − DelayPenalty(a)
```

As implemented in `finalis/scoring.py`:

```python
def nba_utility(a: ActionCandidate, value: float) -> float:
    return _clamp(a.p_close) * max(0.0, value) - a.cost - a.risk - a.delay_penalty
```

- `p_close` is clamped to `[0,1]`; `value` is floored at 0 (doc 26/40 fix #4 —
  no mixed units, all terms currency-denominated).
- Selection is a deterministic argmax with a pinned tie-break policy —
  **ties break toward lower cost, then lower risk** (doc 05 §3):

```python
return max(candidates, key=lambda a: (nba_utility(a, value), -a.cost, -a.risk))
```

- Empty candidate list raises `ValueError` — the selector can never silently
  return nothing (`tests/test_scoring.py::TestNBA::test_empty_candidates_rejected`).

`Value` in the service layer is the risk-adjusted expected value from doc 05 §3
(`estimated_value · LeadScore/100`), computed in `NextBestActionService.select` as:

```python
value = max(case.value_estimate, 0.0) * max(case.lead_score, 1) / 100.0
```

Note the `max(case.lead_score, 1)` floor: a case with an unscored lead
(`lead_score = 0`) still carries 1% of its estimated value, so `do_nothing_wait`'s
delay penalty stays non-degenerate.

## 2. Candidate actions AS CODED

`NextBestActionService.select` enumerates candidates from **deterministic case-state
predicates** — each row below is a literal `ActionCandidate(...)` in the code:

| Action | Enumeration trigger (predicate on the case) | `p_close` | `cost` | `risk` | `delay_penalty` |
|---|---|---|---|---|---|
| `send_photo_request` | `installation_photo` among open (`status != "received"`) missing items | 0.25 | 0.1 | 1 | 0 |
| `ask_for_missing_info` | `address` among open missing items | 0.25 | 0.1 | 1 | 0 |
| `create_quote_task` | **no** open missing items AND state ∈ {`QUALIFIED`, `DOCUMENT_ANALYSIS`, `INTAKE_IN_PROGRESS`, `WAITING_FOR_CLIENT_INFO`} | 0.35 | 1 | 1 | 0 |
| `send_follow_up` | state ∈ {`OFFER_SENT`, `FOLLOW_UP_ACTIVE`} | 0.20 | 0.1 | 2 | 0 |
| `request_human_review` | `case.escalation_score >= 1.5` (θ_escalate, doc 05 §8) | 0.30 | 5 | 0 | 0 |
| `do_nothing_wait` | always a candidate (the baseline) | 0.0 | 0 | 0 | `0.02 · max(value, 1)` |

`do_nothing_wait` is the only candidate with a delay penalty — waiting is never
free, exactly per doc 05 §3 ("a *wait* action's whole cost is delay") and pinned by
`tests/test_scoring.py::TestNBA::test_wait_costs_delay`.

### 2.1 Honest gap: gate-registered but not yet NBA-scored

The full action space from the spec (doc 05 §3, doc 13, doc 22) is **registered in
the action gate** — `ActionGateService.AUTO_OK` / `ActionGateService.HIGH_RISK`
know these action types and will gate them correctly if proposed — but the NBA
enumerator **does not yet generate candidates for them**, so they can currently
only enter the system from a caller other than `NextBestActionService`:

| Action | Gate registration | NBA-scored? |
|---|---|---|
| `send_document_request` | `AUTO_OK` | **No** — no prior row coded |
| `call_client` | `AUTO_OK` | **No** |
| `analyze_document` | `AUTO_OK` | **No** (OCR pipeline triggers it directly, `finalis/documents.py`) |
| `compare_offer` | `AUTO_OK` | **No** |
| `schedule_visit` | `AUTO_OK` | **No** |
| `mark_recovery_later` | `AUTO_OK` | **No** (`CompletionLoop.park_exhausted` transitions directly) |
| `confirm_receipt` | `AUTO_OK` | **No** |
| `close_won` / `close_lost` | `HIGH_RISK` | **No** — closing is human-driven in the E2E |
| `send_offer_commitment` | `HIGH_RISK` | **No** — proposed by callers, always HITL |

Closing this gap = adding enumeration predicates + `(p_close, cost, risk)` prior
rows; the utility math, tie-break, gate, and audit plumbing already handle any
action name.

## 3. Policy: deterministic heuristics first, no fake ML

Per doc 05 §3's design note and §13, and doc 40 §3 (open item 1): the
`p_close`/`cost`/`risk` numbers above are a **rule/heuristic prior table per
(state, action)** — hand-set, versionable constants, not model outputs. The class
docstring states it directly: *"Deterministic candidate evaluation (05 §3). No
fake ML."* There is deliberately no pretend-calibrated probability: a logistic
model (later a contextual bandit) replaces the prior table only once logged
`(context, action, reward=closed?)` tuples exist, and `P(close|a)` calibration
(Brier/ECE in the Evaluation Lab, doc 15) is tracked as an open item that
"no amount of scaffold code substitutes for" (doc 40 §3).

## 4. Output contract

`select(case, *, now, audit)` returns a `SelectedAction` dataclass:

| Field | Value as coded |
|---|---|
| `action` | winning candidate's name |
| `reason` | `"utility={U:.2f} over {N} candidates"` — human-readable audit string |
| `confidence` | **0.8** for any real action, **0.6** for `do_nothing_wait` (heuristic constants; feed the gate's abstention check) |
| `requires_human_approval` | `action in ActionGateService.HIGH_RISK` (advisory pre-check; the gate is still the authority) |
| `utility` | the winning `nba_utility` value |

Side effects, every call:

1. `case.next_best_action = {"type": action}` and
   `case.next_action_due_at = now + 4h` — upholding the completion-loop invariant
   that **every active case always has a next action and a due time**
   (asserted at the end of `CompletionLoopService.run_case`).
2. One `NEXT_ACTION_CREATED` audit event (`actor="ai"`) with payload
   `{action, reason, utility}` on the tamper-evident chain (see
   `audit-events.md`).

The selection then flows into `ActionGateService.evaluate(...)` inside
`CompletionLoopService.run_case` — NBA proposes, the gate disposes (see
`action-gate.md`).

## 5. Test coverage

| What is pinned | Test |
|---|---|
| Utility math, clamping, argmax | `tests/test_scoring.py::TestNBA::test_hot_call_beats_cold_email` |
| Waiting costs delay | `tests/test_scoring.py::TestNBA::test_wait_costs_delay` |
| Tie-break to lower cost/risk | `tests/test_scoring.py::TestNBA::test_tie_breaks_to_lower_cost` |
| Empty candidates rejected | `tests/test_scoring.py::TestNBA::test_empty_candidates_rejected` |
| Missing photo/address → photo/info request wins, gate ALLOWs, follow-up sent | `tests/test_case_graph_services.py::TestCompletionLoopService::test_run_case_selects_action_and_respects_gate` |
| NBA inside the 23-step lifecycle (steps 6–9: request; steps 19–20: `send_follow_up` after `OFFER_SENT`) with `NEXT_ACTION_CREATED` asserted | `tests/test_case_graph_services.py::TestE2EHvacLifecycle::test_full_lifecycle` |
