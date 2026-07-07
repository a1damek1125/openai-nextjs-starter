# Case Graph — Promise Tracker

> **Ground truth**: `finalis/case_services.py` (`PromiseTrackerService`),
> `finalis/models.py` (`Promise`), `finalis/scoring.py`
> (`promise_breach_score`, doc 05 §10), `finalis/completion_loop.py`
> (`promise_check`), branch `claude/finalis-case-graph-completion-loop`,
> 160 tests passing. Spec: doc 05 §10, doc 09 §2,
> doc 40 (#2 — bounded breach score, θ_breach shipped).

## 1. Statuses — service vocabulary vs. model storage (honest mapping)

The service reports the doc-09 status vocabulary; the `Promise` dataclass
stores a smaller lowercase set (`status: "open" | "fulfilled" | "broken" |
"waived"`). The two coexist deliberately — report statuses are *derived*,
storage statuses are *persisted*:

| Service / doc status | Stored `Promise.status` | How it is derived |
|---|---|---|
| **OPEN** | `open` | default; due in the future, outside the due-soon window |
| **DUE_SOON** | `open` (unchanged) | `now >= due_at − 6h` (`DUE_SOON_WINDOW = timedelta(hours=6)`); report-only, no audit event |
| **OVERDUE** | `open` (unchanged) | past due but `PromiseBreachScore < θ_breach` — nagging territory, not breach; emits `PROMISE_DUE` |
| **BREACHED** | `broken` | past due and `PromiseBreachScore ≥ θ_breach = 0.3`; emits `PROMISE_BREACHED` |
| **FULFILLED** | `fulfilled` | `fulfill(case, what)` on an open promise; emits `PROMISE_FULFILLED` |
| **CANCELLED** | `waived` | model supports it; **no service method sets it yet** (honest gap — waiving is currently a direct status write) |

Once a promise leaves `open`, `evaluate()` skips it (`if p.status not in
("open",): continue`) — a breached promise is not re-scored or re-audited on
every tick.

## 2. `evaluate(case, now, *, audit, theta_breach=0.3)` semantics

For each open promise:

1. **Past due** (`now >= due_at`): compute delay in hours and
   `promise_breach_score(importance, delay_h, dependency_impact)`
   (doc 05 §10, bounded to [0,1] by normalizing delay against
   `expected_window_hours = 72` — the doc-26 CRITICAL #2 fix, see doc 40).
   - score ≥ `θ_breach` (0.3) → status `broken`, bucket `BREACHED`,
     audit `PROMISE_BREACHED` with `{what, score}`.
   - score < `θ_breach` → bucket `OVERDUE`, audit `PROMISE_DUE` (a reminder
     signal, not a breach).
2. **Inside the 6-hour window** (`now >= due_at − 6h`): bucket `DUE_SOON`.
3. Returns `{"DUE_SOON": [...], "OVERDUE": [...], "BREACHED": [...]}`.

### Test vectors (pinned)

| Vector | Computation | Outcome | Test |
|---|---|---|---|
| importance 0.9, 72 h late, impact 0.6 | `0.9 · (72/72 = 1.0) · 0.6 = 0.54 ≥ 0.3` | **breached**, status `broken`, `breach_score == 0.54` | `tests/test_completion_loop.py::TestPromiseTracker::test_overdue_promise_breaches` |
| importance 0.8, 36 h late, impact 0.6 | `0.8 · (36/72 = 0.5) · 0.6 = 0.24 < 0.3` | **stays `open`**, no nag/breach | `tests/test_completion_loop.py::TestPromiseTracker::test_slightly_overdue_low_impact_does_not_breach`; same 0.24 vector in `tests/test_scoring.py` (`test_typical`) |
| importance 1.0, 100 000 h late, impact 1.0 | clamps to exactly 1.0 (bounded) | no blowout | `tests/test_scoring.py` (`test_bounded_0_1`) |
| DUE_SOON / OVERDUE / BREACHED bucketing in one pass | 3 promises, T0 clock | one per bucket; 1×`PROMISE_BREACHED`, 1×`PROMISE_DUE` | `tests/test_case_graph_services.py::TestPromiseTracker::test_statuses` |

`θ_breach = 0.3`, `expected_window_hours = 72`, and the 6 h due-soon window are
**provisional** consumer-side parameters until Evaluation Lab data exists
(doc 40 §3.3).

## 3. Who promised — symmetric tracking

`Promise.promisor` records the party/role making the promise (`"client"`,
`"company"`, `"technician"`, ...). Scoring is deliberately symmetric — the same
`Importance · Delay · DependencyImpact` applies regardless of promisor; the
bucketing test breaches a **technician** promise ("prepare quote") alongside
client promises. What differs is the designed *consumer routing* (doc 05 §10,
doc 09): a breached **client** promise triggers a Missing-Info follow-up; a
breached **company/technician/notary/supplier** promise is trust-damaging and
escalates to an **owner alert**. In the scaffold both surface as
`PROMISE_BREACHED` on the timeline and via the loop tick's promise report —
the promisor-specific routing (owner alert channel) is a documented consumer
behavior, not yet a separate code path.

## 4. Audit events

| Event | Emitted by | When |
|---|---|---|
| `PROMISE_CREATED` | Voice Conversation Intelligence (`finalis/voice/conversation_intelligence.py`) and callers (E2E step 4 records it explicitly) — there is **no `create()` method** on the tracker; promises are appended to `case.promises` by the extractor/caller | promise detected/recorded |
| `PROMISE_DUE` | `PromiseTrackerService.evaluate` (`actor="system"`) | past due, below θ_breach |
| `PROMISE_BREACHED` | `PromiseTrackerService.evaluate` (`actor="system"`, payload `{what, score}`) | past due, score ≥ θ_breach |
| `PROMISE_FULFILLED` | `PromiseTrackerService.fulfill` (`actor="system"`) | open promise fulfilled |

**Naming duality note**: the older `CompletionLoop.promise_check`
(`finalis/completion_loop.py`) implements the same θ_breach rule but emits
dotted-lowercase `promise.breached`. `CompletionLoopService.run_case` uses the
`PromiseTrackerService` path (UPPER_SNAKE events). See `audit-events.md` for
the recommended normalization.

## 5. Integration points

- `CompletionLoopService.run_case` calls `evaluate()` on every tick and reports
  bucket counts in the tick result (`result["promises"]`).
- A fulfilled promise typically pairs with `MissingInfoService.resolve` (E2E
  steps 11–12: photo arrives → resolve `installation_photo` + fulfill
  "send photos").
- Promise deadlines are the durable-timer input for the production scheduler
  (doc 22 §2.4); the scaffold's simulated clock proves the logic restart-safe.
