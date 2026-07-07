# Case Graph — API Contracts

> **Ground truth:** branch `claude/finalis-case-graph-completion-loop`, 160 tests passing
> (`python3 -m pytest tests/ -q`). Source of the internal contracts:
> `finalis/case_services.py`, `finalis/state_machine.py`, `finalis/audit.py`,
> `finalis/certainty_core.py`, exercised end-to-end by
> `tests/test_case_graph_services.py::TestE2EHvacLifecycle`.
>
> **Status legend** — *Implemented (scaffold)*: real, tested Python code exists behind
> this contract (in-memory MVP, no persistence, no HTTP server). *Designed*: contract
> specified here / in `openapi.finalis.yaml`; no code serves it yet.

There is **no HTTP server on this branch**. Every REST contract below is **Designed**.
What is Implemented (scaffold) is the service layer the REST layer will be a thin shell
over — the mapping REST → internal method is given per endpoint so the API layer adds
no business logic.

---

## 1. REST contracts (Designed — no server yet)

Conventions inherited from `openapi.finalis.yaml` / doc 22: bearer auth, tenant scoping
on every route, `Idempotency-Key` on mutating routes, cursor pagination
(`data / next_cursor / has_more`), error envelope with typed codes
(`409 invalid_transition`, `422 confidence_below_threshold`, `404`, `401/403`).

### 1.1 Endpoint inventory vs. `openapi.finalis.yaml`

| Endpoint | In `openapi.finalis.yaml` today? | Disposition |
|---|---|---|
| `POST /cases` | Yes (`/cases` post) | Exists — extend request with `tenant-implicit` industry default |
| `GET /cases/{id}` | Yes | Exists |
| `PATCH /cases/{id}` | Yes | Exists |
| `POST /cases/{id}/transition` | Partially — spec has `POST /cases/{id}/state` | Exists under old name; **fold in** `human_override` / `scheduled_wake` (and the other three trigger flags) at implementation time |
| `GET /cases/{id}/graph` | No | **NEW** — add to spec |
| `POST /cases/{id}/parties` | No (only top-level `POST /parties`) | **NEW** case-scoped attach |
| `POST /cases/{id}/missing-items` | No (`/missing-items` is GET-only; creation Orchestrator-only) | **NEW** |
| `POST /cases/{id}/promises` | No (only top-level `POST /promises`) | **NEW** case-scoped variant |
| `POST /cases/{id}/tasks` | No (only top-level `POST /tasks` with `case_id` in body) | **NEW** case-scoped variant |
| `POST /cases/{id}/actions` | No (`/actions` is a GET-only audit surface) | **NEW** — proposes an action into the gate; never executes directly |
| `POST /cases/{id}/evidence` | No (only `GET /evidence-refs/{id}`) | **NEW** |
| `POST /cases/{id}/decision-briefs` | No (`/decision-briefs` is GET-only) | **NEW** |
| `GET /cases/{id}/timeline` | No (derivable from `GET /audit-events?case_id=`) | **NEW** convenience projection |
| `GET /cases/{id}/audit-events` | Top-level `GET /audit-events?case_id=` exists | **NEW** case-scoped alias |
| `POST /completion-loop/run` | No | **NEW** |
| `POST /completion-loop/run-case/{id}` | No | **NEW** |
| `GET /completion-loop/status` | No | **NEW** |
| `POST /action-gate/evaluate` | No | **NEW** |

At implementation time the NEW paths (`/cases/{id}/graph`, `/completion-loop/*`,
`/action-gate/evaluate`, the case-scoped attach routes, `/cases/{id}/timeline`) must be
folded into `openapi.finalis.yaml`; nothing else may claim those paths (same reservation
discipline as the `/certainty/*` paths in doc 32 §2.10).

### 1.2 `POST /cases` — Designed (exists in spec)

Maps to `CaseGraphService.create_case`.

Request (per existing spec, `goal`/`industry_type` required; scaffold parameters shown
as they exist in code):

```json
{
  "goal": "Heat pump quote",
  "industry_type": "hvac",
  "source_channel": "voice",
  "autonomy_level": 3,
  "party": { "type": "client", "display_name": "Jan Kowalski", "phone": "+48600100200" }
}
```

Response `201` — `Case` in state `NEW_CONTACT`, **with `next_best_action` and
`next_action_due_at` already set** (scaffold invariant: a freshly created active case is
never without a next action; asserted in
`TestCaseGraphService::test_create_case_writes_audit`). Emits `CASE_CREATED` audit event.
Errors: `400`, `401`. Idempotency-Key honored.

### 1.3 `GET /cases/{id}` — Designed (exists in spec)

Full case file: state, scores, autonomy, `next_best_action`, `next_action_due_at`,
embedded open `missing_items` and `promises`. `404` if not found **or wrong tenant**
(cross-tenant reads must 404, not 403 — no existence leak; scaffold raises
`PermissionError`).

### 1.4 `PATCH /cases/{id}` — Designed (exists in spec)

Mutable fields only: `owner_id`, `goal`, `value_estimate`, `autonomy_level` (1–5),
`wake_at` (RECOVERY_LATER only), `closed_reason`. **`state` is not patchable** — use
`/transition`. `400` on attempt to patch `state`.

### 1.5 `POST /cases/{id}/transition` — Designed (spec has it as `/cases/{id}/state`)

Maps 1:1 to `finalis.state_machine.transition`. The existing spec entry validates
against doc 03 §4 and returns `409 invalid_transition`; the case-graph state machine
adds five trigger flags that must be folded into the request body:

```json
{
  "to_state": "SCHEDULED",
  "reason": "human schedules install",
  "actor": "human",
  "human_override": true,
  "scheduled_wake": false,
  "escalation_interrupt": false,
  "hard_opt_out": false,
  "followup_exhausted": false,
  "evidence_ref_ids": []
}
```

Semantics (implemented and tested in `finalis/state_machine.py::is_legal`):

- **Final-state rule**: no FINAL state (`WON`, `LOST`, `COMPLETED`, `ABANDONED`,
  `RECOVERY_LATER`) may be exited without `human_override: true` — with exactly one
  exception: the Completion Loop's `scheduled_wake: true` for
  `RECOVERY_LATER → FOLLOW_UP_ACTIVE`. Verified in the E2E (steps 21–22) and
  `test_state_machine.py::TestTransitions::test_final_states_require_human_override_to_exit`.
- `escalation_interrupt`: global edge, any active state → `HUMAN_REVIEW_REQUIRED`
  (also caps effective autonomy at L2 on entry).
- `hard_opt_out` / `followup_exhausted`: global closure edge, any non-terminal state →
  `ABANDONED`/`LOST`; `hard_opt_out` permanently sets `opted_out`.
- Every applied transition writes a `case.state_changed` AuditEvent
  (`{from_state, to_state, reason}`, actor).

Responses: `200` updated Case; `409 invalid_transition` (illegal edge, or final-state
exit without override); `404`.

### 1.6 `GET /cases/{id}/graph` — Designed (**NEW**)

Maps to `CaseGraphService.get_case_graph(case_id, tenant_id=...)`. Response is the
serialized form of the dict the scaffold returns today:

```json
{
  "case": { "id": "…", "state": "OFFER_SENT", "...": "..." },
  "nodes": ["<case>", "<attached Party/EvidenceReference/Document/… entities>"],
  "edges": [ { "from": "<case_id>", "to": "<entity_id>", "type": "PARTY" } ],
  "missing_items": [ { "field_key": "address", "status": "received", "...": "..." } ],
  "promises": [ { "what": "send photos", "status": "fulfilled", "...": "..." } ],
  "timeline": [ "<AuditEvents for this case, chain order>" ]
}
```

Edge types in the scaffold: `PARTY`, `EVIDENCE`, `VOICE_SESSION`, `DOCUMENT`, `MESSAGE`
(anything else audits as `CASE_UPDATED`). Cross-tenant access → `404` at the API
(scaffold: `PermissionError`; tested in
`TestCaseGraphService::test_tenant_isolation_on_graph_read`).

### 1.7 Case-scoped attach routes — Designed (**NEW** except noted)

All map to `CaseGraphService.attach_entity(case, entity, edge_type=..., actor=...)` plus
the entity-specific service; all refuse cross-tenant entities (`404`/`409`, scaffold
`PermissionError`, tested) and write the typed audit event.

| Route | Body (created entity) | Internal call | Audit event |
|---|---|---|---|
| `POST /cases/{id}/parties` | `Party` | `attach_entity(edge_type="PARTY")` | `PARTY_ATTACHED` |
| `POST /cases/{id}/missing-items` | detection request `{known_facts, industry}` **or** explicit `MissingItem` | `MissingInfoService.detect` | `MISSING_INFO_DETECTED` |
| `PATCH /cases/{id}/missing-items/{field_key}` (companion) | `{status: "received", source}` | `MissingInfoService.resolve` | `MISSING_INFO_RESOLVED` |
| `POST /cases/{id}/promises` | `Promise` (`promisor, what, due_at, importance, dependency_impact`) | append to `case.promises` | `PROMISE_CREATED` |
| `POST /cases/{id}/tasks` | `{title, assignee_id, priority, due_at}` | *Designed only* — no Task entity in the scaffold (tasks exist as `next_best_action` dicts / `create_quote_task` action names) | `TASK_CREATED` (reserved) |
| `POST /cases/{id}/actions` | `{action_type, confidence, context}` — **proposal**, routed through the gate, never direct execution | `ActionGateService.evaluate` | `ACTION_CREATED` / `ACTION_BLOCKED` / `HUMAN_REVIEW_REQUESTED` / `ACTION_ABSTAINED` |
| `POST /cases/{id}/evidence` | `EvidenceReference` (`source_type, source_id, locator, snippet, confidence`) | `attach_entity(edge_type="EVIDENCE")` | `EVIDENCE_CREATED` |
| `POST /cases/{id}/decision-briefs` | `{summary, recommended_action, requires_human_approval}` | *Audit-event only in scaffold* (no DecisionBrief entity) | `DECISION_BRIEF_CREATED` |

### 1.8 `GET /cases/{id}/timeline` — Designed (**NEW**)

Projection of `AuditLog.events(case_id=...)` — the same list `get_case_graph` returns
as `timeline`. Ordered by chain position; filterable by `event_type`, `actor`, `from`,
`to`. The E2E asserts ≥ 15 events and exactly 7 `case.state_changed` events for the full
HVAC lifecycle.

### 1.9 `GET /cases/{id}/audit-events` — Designed (**NEW** alias)

Case-scoped alias of the existing `GET /audit-events?case_id=`. Returns hash-chained
`AuditEvent` rows (`id, event_type, actor, case_id, payload, hash_prev, hash_self`).
Append-only; **no mutation routes exist by design**. A `/verify` companion exposes
`AuditLog.verify_chain()`.

### 1.10 `POST /completion-loop/run` — Designed (**NEW**)

Runs one loop tick over **all active cases** of the tenant (final-state cases are
skipped with `skipped: ["final_state"]`, never silently dropped — tested in
`TestCompletionLoopService::test_final_case_skipped_never_dropped_silently`). Request:
`{ "now": "<ISO8601, optional — defaults to server clock>" }` (the scaffold loop is
simulated-clock, so `now` is an explicit parameter end to end). Response:

```json
{ "ticked": 12, "results": [ "<per-case run_case results, §1.11 shape>" ] }
```

### 1.11 `POST /completion-loop/run-case/{id}` — Designed (**NEW**)

Maps to `CompletionLoopService.run_case(case, now=...)`. The response JSON is exactly
the dict the implemented code returns:

```json
{
  "case_id": "…",
  "state": "WAITING_FOR_CLIENT_INFO",
  "actions": ["send_photo_request"],
  "skipped": [],
  "promises": { "DUE_SOON": 1, "OVERDUE": 0, "BREACHED": 0 },
  "stuck": false,
  "selected_action": "send_photo_request",
  "gate": "ALLOW"
}
```

- Final-state case: short-circuit shape `{ "case_id", "state", "actions": [],
  "skipped": ["final_state"] }` — the `promises/stuck/selected_action/gate` keys are
  absent.
- Duplicate outbound suppressed within the cooldown: `"skipped": ["duplicate_followup"]`
  plus a `FOLLOW_UP_RATE_LIMITED` audit event.
- Post-condition (asserted in code): an active case leaves the tick with
  `next_best_action` and `next_action_due_at` set.

### 1.12 `GET /completion-loop/status` — Designed (**NEW**)

Loop health: last tick time, active-case count, invariant violations from
`CompletionLoop.check_invariants` (active cases missing a next action — must be `[]`),
stuck queue size from `stuck_sweep`, follow-up states (attempts / exhausted counts).

```json
{
  "last_tick_at": "…",
  "active_cases": 12,
  "invariant_violations": [],
  "stuck_queue": [ { "case_id": "…", "stuck_score": 62.5, "action": "followup_or_owner_alert" } ],
  "followups": { "exhausted": 1, "in_cadence": 4 }
}
```

### 1.13 `POST /action-gate/evaluate` — Designed (**NEW**)

Maps to `ActionGateService.evaluate`. Request:

```json
{ "case_id": "…", "action_type": "send_offer_commitment", "confidence": 0.9, "context": {} }
```

Response is the serialized `GateDecision` dataclass:

```json
{ "outcome": "REQUIRE_HUMAN_APPROVAL", "reason": "high_risk_action", "audit_id": "<AuditEvent.id>" }
```

`outcome ∈ { ALLOW, BLOCK, REQUIRE_HUMAN_APPROVAL, ABSTAIN_MISSING_DATA }`. Every
evaluation writes exactly one audit event (`ACTION_CREATED` / `ACTION_BLOCKED` /
`HUMAN_REVIEW_REQUESTED` / `ACTION_ABSTAINED`) and returns its id as `audit_id` — this
endpoint is also the future LGGT ProofGate hook (see
`lggt-certainty-core-placeholder.md`). Rule order as implemented: opt-out block →
high-risk (ALWAYS_HITL ∪ {close_won, close_lost, send_offer_commitment}) → confidence
< 0.5 abstain → effective autonomy ≤ 2 on outbound → AUTO_OK allowlist →
**conservative default REQUIRE_HUMAN_APPROVAL for unknown actions**.

---

## 2. Internal interfaces — as implemented

All signatures below are copied from the code on this branch. "Implemented (scaffold)"
means the method exists, is in-memory, and is covered by passing tests.

### 2.1 `CaseGraphService` — Implemented (scaffold) — `finalis/case_services.py`

```python
def create_case(self, *, tenant_id: str, title: str = "",
                industry: str = "hvac", source_channel: str = "unknown",
                autonomy_level: int = 3) -> Case

def attach_entity(self, case: Case, entity: Any, *, edge_type: str,
                  actor: str = "system") -> None
    # raises PermissionError on cross-tenant attachment

def get_case_graph(self, case_id: str, *, tenant_id: str) -> dict
    # keys: case, nodes, edges, missing_items, promises, timeline
    # raises PermissionError on cross-tenant read
```

### 2.2 `StateMachineService.transition` — Implemented (scaffold) — `finalis/state_machine.py`

There is no separate service class; the contract **is** the module function:

```python
def transition(case, to_state: CaseState, *, actor: str, reason: str,
               audit_log, escalation_interrupt: bool = False,
               hard_opt_out: bool = False, followup_exhausted: bool = False,
               human_override: bool = False, scheduled_wake: bool = False) -> None
    # raises IllegalTransition; writes case.state_changed AuditEvent;
    # enforces final-state override rule, HUMAN_REVIEW_REQUIRED autonomy freeze (L2),
    # opt-out latch, next-action clearing on WON/LOST/COMPLETED/ABANDONED
```

### 2.3 `MissingInfoService` — Implemented (scaffold)

```python
def detect(self, case: Case, known_facts: dict[str, Any],
           *, industry: str = "hvac", audit: AuditLog) -> list[MissingItem]
    # HVAC profile: client_contact, address, service_type, installation_photo,
    # urgency, preferred_date; idempotent (no duplicate items)

@staticmethod
def resolve(case: Case, field_key: str, *, audit: AuditLog,
            source: str = "client") -> bool

@staticmethod
def open_blockers(case: Case) -> list[MissingItem]
    # unresolved items with blocks_quote=True (block QUOTE_PREPARATION)
```

### 2.4 `PromiseTrackerService` — Implemented (scaffold)

```python
def evaluate(self, case: Case, now: datetime, *, audit: AuditLog,
             theta_breach: float = 0.3) -> dict[str, list[Promise]]
    # keys: DUE_SOON (≤6h ahead), OVERDUE, BREACHED (breach score ≥ θ, status→"broken")

@staticmethod
def fulfill(case: Case, what: str, *, audit: AuditLog) -> bool
```

Status vocabulary note: the service docstring names
OPEN/DUE_SOON/OVERDUE/FULFILLED/BREACHED/CANCELLED; the persisted `Promise.status` field
uses `open | fulfilled | broken | waived` — DUE_SOON/OVERDUE are evaluation-report
buckets, not stored statuses.

### 2.5 `CompletionLoopService` — Implemented (scaffold)

```python
def run_case(self, case: Case, *, now: datetime) -> dict
    # result shape per §1.11; composes PromiseTracker.evaluate, CompletionLoop
    # stuck_sweep, NextBestActionService.select, ActionGateService.evaluate,
    # duplicate-prevention set, CompletionLoop.send_followup (anti-spam policy)
```

### 2.6 `NextBestActionService` — Implemented (scaffold)

```python
def select(self, case: Case, *, now: datetime, audit: AuditLog) -> SelectedAction
    # SelectedAction(action, reason, confidence, requires_human_approval, utility);
    # deterministic candidate set → scoring.next_best_action utility argmax;
    # sets case.next_best_action and next_action_due_at (+4h); audits NEXT_ACTION_CREATED
```

### 2.7 `ActionGateService` — Implemented (scaffold)

```python
def evaluate(self, case: Case, action_type: str, *,
             confidence: float = 1.0, audit: AuditLog,
             context: dict | None = None) -> GateDecision
    # GateDecision(outcome, reason, audit_id)
```

### 2.8 `AuditService.write` — Implemented (scaffold) — `finalis/audit.py`

The contract **is** `AuditLog.append`:

```python
def append(self, *, event_type: str, actor: str,
           case_id: Optional[str] = None,
           payload: Optional[dict[str, Any]] = None) -> AuditEvent

def verify_chain(self) -> bool
def events(self, *, case_id=None, event_type=None) -> list[AuditEvent]
```

Append-only, SHA-256 hash-chained (`hash_prev`/`hash_self`); no update/delete API exists.

### 2.9 `CertaintyCoreAdapter.certify` — Implemented (scaffold: `NullAdapter`) — `finalis/certainty_core.py`

```python
class CertaintyCoreAdapter(Protocol):
    def certify(self, decision_ref: str, facts: list[Fact],
                policy_version: str) -> Certificate: ...
```

`NullAdapter.certify` stamps `verdict="heuristic"`, `confidence = min(fact confidences)`,
writes a `certainty.stamped` AuditEvent and returns its id as `Certificate.audit_id`.
Tested in `TestLGGTPlaceholderCallable`. See `lggt-certainty-core-placeholder.md`.

### 2.10 Status summary

| Interface | Status |
|---|---|
| `CaseGraphService.create_case / attach_entity / get_case_graph` | Implemented (scaffold) |
| `StateMachineService.transition` (= `finalis.state_machine.transition`) | Implemented (scaffold) |
| `MissingInfoService.detect / resolve / open_blockers` | Implemented (scaffold) |
| `PromiseTrackerService.evaluate / fulfill` | Implemented (scaffold) |
| `CompletionLoopService.run_case` | Implemented (scaffold) |
| `NextBestActionService.select` | Implemented (scaffold) |
| `ActionGateService.evaluate` | Implemented (scaffold) |
| `AuditService.write` (= `AuditLog.append`) | Implemented (scaffold) |
| `CertaintyCoreAdapter.certify` (`NullAdapter`) | Implemented (scaffold) |
| All REST endpoints (§1) | Designed — no server |
| Task entity / TaskService | Designed (doc 04 `Task`; scaffold has no Task class) |
| DecisionBrief entity | Designed (scaffold records `DECISION_BRIEF_CREATED` audit events only) |
| Persistence (Postgres + RLS), idempotency store, authn/z | Designed |
