# Case Graph — Architecture

Status: service layer **Implemented and tested** (`python3 -m pytest tests/ -q` →
`160 passed`; case-graph slice: 20 + 13 + 19 tests). Persistence and HTTP API:
**Designed** (docs 04, 22, 18).

## Layered picture

```
┌───────────────────────────────────────────────────────────────────────┐
│  Connected modules: Voice · OCR · WebScout · Dashboard · LGGT         │
└───────────────┬───────────────────────────────────────────────────────┘
                │ service contracts (finalis/case_services.py)
┌───────────────▼───────────────────────────────────────────────────────┐
│  SERVICE LAYER                                                        │
│  CaseGraphService · MissingInfoService · PromiseTrackerService        │
│  NextBestActionService · ActionGateService · CompletionLoopService    │
└───────────────┬───────────────────────────────────────────────────────┘
                │ wraps
┌───────────────▼───────────────────────────────────────────────────────┐
│  TESTED CORE                                                          │
│  state_machine.py (17 states, transition guards, invariants)          │
│  scoring.py (LeadScore, MIS, NBA utility, StuckScore, breach score)   │
│  completion_loop.py (invariants, anti-spam, stuck sweep)              │
│  autonomy.py (L1–L5, ALWAYS_HITL)  ·  audit.py (hash-chained log)     │
│  models.py (Case, Party, Promise, MissingItem, Document, ...)         │
└───────────────┬───────────────────────────────────────────────────────┘
                │ today: in-memory dicts/dataclasses (MVP)
                │ next:  PostgreSQL relational graph (doc 04) — Designed
└───────────────────────────────────────────────────────────────────────┘
```

Every service takes an `AuditLog` and writes an event for every observable decision;
the log is append-only and hash-chained (`AuditLog.verify_chain()` is asserted in the
23-step E2E).

## The six services — actual signatures

All signatures below are copied from `finalis/case_services.py`.

### CaseGraphService — create cases, attach entities, read the graph

```python
def create_case(self, *, tenant_id: str, title: str = "",
                industry: str = "hvac", source_channel: str = "unknown",
                autonomy_level: int = 3) -> Case
def attach_entity(self, case: Case, entity: Any, *, edge_type: str,
                  actor: str = "system") -> None
def get_case_graph(self, case_id: str, *, tenant_id: str) -> dict
```

- `create_case` seeds the never-drop invariant at birth: the new case gets
  `next_best_action={"type": "start_intake"}` and a due time immediately, and a
  `CASE_CREATED` audit event.
- `attach_entity` refuses cross-tenant attachments (`PermissionError`), records a typed
  edge (`{"from": case.id, "to": entity.id, "type": edge_type}`) in
  `CaseGraphService.edges`, and maps the edge type to an audit event
  (`PARTY_ATTACHED`, `DOCUMENT_ATTACHED`, `VOICE_SESSION_ATTACHED`,
  `MESSAGE_RECEIVED`, `EVIDENCE_CREATED`; anything else → `CASE_UPDATED`).
- `get_case_graph` returns `{case, nodes, edges, missing_items, promises, timeline}`
  where `timeline` is the case's audit events — the Dashboard read model. Cross-tenant
  reads raise `PermissionError`.

### MissingInfoService — industry-aware required-info profiles

```python
def detect(self, case: Case, known_facts: dict[str, Any],
           *, industry: str = "hvac", audit: AuditLog) -> list[MissingItem]
@staticmethod
def resolve(case: Case, field_key: str, *, audit: AuditLog,
            source: str = "client") -> bool
@staticmethod
def open_blockers(case: Case) -> list[MissingItem]
```

Profiles live in `MissingInfoService.PROFILES` (`"hvac"` → `HVAC_REQUIRED_INFO`, six
items: `client_contact`, `address`, `service_type`, `installation_photo`, `urgency`,
`preferred_date`, each with severity, recommended question in Polish, recommended
channel, and an optional `blocks_state`). `detect` diffs the profile against known
facts, creates `MissingItem`s with `weight = SEVERITY_WEIGHT[severity]`
(high 0.9 / medium 0.5 / low 0.2) and `blocks_quote=True` when the profile item blocks
`QUOTE_PREPARATION`; duplicates are never re-created (tested:
`test_no_duplicate_detection`). `resolve` marks an item `received`, audits
`MISSING_INFO_RESOLVED`, and advances `case.last_progress_at` (which lowers
StuckScore).

### PromiseTrackerService — commitments with a clock

```python
DUE_SOON_WINDOW = timedelta(hours=6)
def evaluate(self, case: Case, now: datetime, *, audit: AuditLog,
             theta_breach: float = 0.3) -> dict[str, list[Promise]]
@staticmethod
def fulfill(case: Case, what: str, *, audit: AuditLog) -> bool
```

`evaluate` buckets open promises into `DUE_SOON` (within 6 h of due), `OVERDUE`
(past due, breach score below θ), and `BREACHED` (past due with
`scoring.promise_breach_score(importance, delay_hours, dependency_impact) ≥ 0.3` —
the promise is marked `broken` and `PROMISE_BREACHED` audited).

### NextBestActionService — deterministic candidate evaluation

```python
def select(self, case: Case, *, now: datetime, audit: AuditLog) -> SelectedAction
```

Builds `scoring.ActionCandidate`s from case facts (open photo/address blockers →
`send_photo_request` / `ask_for_missing_info`; no blockers in an eligible state →
`create_quote_task`; `OFFER_SENT`/`FOLLOW_UP_ACTIVE` → `send_follow_up`;
`escalation_score ≥ 1.5` → `request_human_review`; always a `do_nothing_wait` baseline
whose delay penalty scales with case value), ranks them with `scoring.nba_utility`
(doc 05 §3) against `value = value_estimate · max(lead_score, 1) / 100`, writes the
winner into `case.next_best_action` with `next_action_due_at = now + 4h`, and audits
`NEXT_ACTION_CREATED`. Returns `SelectedAction(action, reason, confidence,
requires_human_approval, utility)`. No fake ML — the scoring is the documented formula.

### ActionGateService — four-outcome gate

```python
def evaluate(self, case: Case, action_type: str, *,
             confidence: float = 1.0, audit: AuditLog,
             context: dict | None = None) -> GateDecision
```

`GateDecision(outcome, reason, audit_id)` with outcome one of `ALLOW`, `BLOCK`,
`REQUIRE_HUMAN_APPROVAL`, `ABSTAIN_MISSING_DATA`. Rule order (first match wins):

1. opted-out client + outbound action (`send_*`/`call_*`/`ask_*`) → `BLOCK`
2. `HIGH_RISK` (= `autonomy.ALWAYS_HITL` ∪ {`close_won`, `close_lost`,
   `send_offer_commitment`}) → `REQUIRE_HUMAN_APPROVAL`
3. `confidence < 0.5` → `ABSTAIN_MISSING_DATA`
4. `case.effective_autonomy ≤ 2` + outbound action → `REQUIRE_HUMAN_APPROVAL`
   (this is how the HUMAN_REVIEW_REQUIRED autonomy freeze bites)
5. action in `AUTO_OK` allowlist → `ALLOW`
6. anything else → `REQUIRE_HUMAN_APPROVAL` (conservative default for unknown actions —
   tested: `test_unknown_action_conservative`)

Every decision writes an audit event (`ACTION_CREATED` / `ACTION_BLOCKED` /
`HUMAN_REVIEW_REQUESTED` / `ACTION_ABSTAINED`) and returns its id. Phase-1 rule-based;
the LGGT ProofGate strengthens it later behind the same signature (Designed, doc 32).

### CompletionLoopService — the per-case tick

```python
def __init__(self, audit: AuditLog) -> None   # owns CompletionLoop, PromiseTracker,
                                              # NBA, ActionGate, duplicate-send memory
def run_case(self, case: Case, *, now: datetime) -> dict
```

Returns a tick report: `{case_id, state, actions, skipped, promises, stuck,
selected_action, gate}`. Full contract in `completion-loop.md`.

## Event flow of one loop tick (`run_case`)

1. **Load state** — if `case.state in FINAL_STATES`, record `skipped=["final_state"]`
   and return; final cases are skipped *visibly*, never mutated (tested:
   `test_final_case_skipped_never_dropped_silently`).
2. **Promises evaluate** — `PromiseTrackerService.evaluate(case, now)`; breaches flip
   status and audit.
3. **Stuck sweep** — `CompletionLoop.stuck_sweep([case], now)`: recomputes StuckScore
   from days-since-progress, lead score, and the max open blocker weight; audits
   `scores.recomputed`; returns a prioritized queue if above θ_stuck (default 40).
4. **NBA select** — `NextBestActionService.select` picks the action and re-arms
   `next_best_action` / `next_action_due_at`.
5. **ActionGate evaluate** — the selected action goes through the four-outcome gate
   with the NBA's confidence.
6. **Execute-if-allowed with duplicate prevention** — only if the gate said `ALLOW`
   and the action is an outbound ask (`send_follow_up`, `send_photo_request`,
   `ask_for_missing_info`): a per-case sent-set suppresses duplicate asks within the
   cooldown (audited as `FOLLOW_UP_RATE_LIMITED`), otherwise
   `CompletionLoop.send_followup` applies the anti-spam policy (quiet hours, min
   interval, max attempts) before actually sending.
7. **Invariant assert** — the tick ends with
   `assert case.next_best_action is not None` and
   `assert case.next_action_due_at is not None`: an active case cannot leave the tick
   without a future action.

## Persistence: in-memory MVP → PostgreSQL relational graph

Today the services hold plain dicts (`CaseGraphService.cases`, `.edges`,
`.attachments`; `CompletionLoop.followups`) over dataclasses whose field names match
doc 04 — deliberately, so the production schema is generated from the same shapes
(`finalis/models.py` module docstring). The persistence plan (**Designed**, doc 04):

- **PostgreSQL relational graph**: one table per entity plus the typed `graph_edges`
  table (`from_node`, `to_node`, `edge_type`, `weight`, `evidence_ref_id`), traversed
  with recursive CTEs for MVP-scale questions ("what blocks this quote?").
  `CaseGraphService.edges` is the in-memory realization of exactly that table.
- **Neo4j optional later**: doc 04 sets the migration trigger — typical queries
  exceeding 3–4 hop traversals across >10⁵ edges with latency issues. Not before.
- **Durable scheduling**: Temporal, or a Postgres-backed queue/APScheduler for the
  lighter MVP (doc 18). The loop's scheduler state is plain data proven rebuildable
  from case rows (`TestDurability::test_restart_survival_scheduler_state_rebuildable`).

Persistence lands **behind these same signatures** — the service contracts above are
the stable surface other modules build against.
