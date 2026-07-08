# Command Center Architecture

## 1. DashboardService is a projection layer

`finalis/dashboard.py::DashboardService` is a **read-side projection over domain objects**.
There is **no separate dashboard database** and no materialized aggregates: every section is
computed on demand from `Case` (with its attached `MissingItem`s and `Promise`s), the ACE
approval drafts, and the append-only `AuditLog`. If a case changes, the dashboard is correct
on the next call — nothing to sync, nothing to invalidate.

```
Case Graph ──register_case──▶ ┌────────────────────┐        ┌─────────────────────┐
Completion Loop (NBA, due) ──▶│  DashboardService  │──13──▶ │ contract objects     │──▶ render_dashboard (HTML, today)
ACE drafts ─register_approval▶│  (per-tenant       │sections│ (DashboardSummary,   │──▶ Next.js UI (Designed)
AuditLog ◀──decide()/assign()─│   projections)     │        │  OwnerActionItem, …) │──▶ print / email digest
                              └────────────────────┘        └─────────────────────┘
```

Tenant scoping is structural: every section method starts from
`_tenant_cases(tenant_id)` and approval reads filter on `a["tenant_id"]`, so one tenant's
data can never appear in another tenant's projection. Mutations (`decide`, `snooze`,
`assign`) re-verify tenant ownership and RBAC (`_check(role, perm)` against
`ROLE_PERMISSIONS`) and raise `PermissionDenied` otherwise.

## 2. Section-by-section computation logic (as coded)

All references below are to the actual code in `finalis/dashboard.py`.

### 2.1 `summary(tenant_id, *, now)` → `DashboardSummary`
- **active_cases_count** — cases whose `state ∈ ACTIVE_STATES` (all states except
  WON/LOST/COMPLETED/ABANDONED/RECOVERY_LATER).
- **overdue_promises_count** — open promises with `now > due_at`, counted across all tenant
  cases.
- **stuck_cases_count** — active cases with `_days_stalled(c, now) ≥ 5`
  (`(now - last_progress_at)` in days; `0.0` when `last_progress_at is None`).
- **pending_approvals_count** — approval drafts with `approval_status == "PENDING"`.
- **attention_required_count** — size of the *union* of case ids from {stuck} ∪ {cases with
  a pending approval} ∪ {active cases in `HUMAN_REVIEW_REQUIRED`} (a case counts once even
  if it qualifies three ways).
- **pipeline_value** — Σ `value_estimate` over active cases.
- **expected_close_value** — Σ `value_estimate × min(lead_score, 100)/100` over active cases
  (lead score as win probability), rounded to 2 decimals.
- **won_value_period / lost_value_period** — Σ `value_estimate` over cases in `WON` / `LOST`.

### 2.2 `action_queue(tenant_id, *, now)` → `list[OwnerActionItem]`
Includes each active, non-snoozed case (a case snoozed `until > now` is skipped). Urgency,
exactly as coded:

```
base    = (lead_score / 100) × max(value_estimate, 1)
urgency = base × (1 + 0.2 × days_stalled) × (1 + 0.5 × overdue_promise_count)
if next_action_due_at and next_action_due_at <= now:  urgency *= 1.5
```

i.e. **lead/100 × value × staleness multiplier × overdue-promise multiplier × 1.5
overdue-due boost**. `urgency` is the **internal sort key** (descending) and is **never
displayed raw** — the UI shows the `reason` from `explain()` instead. Also derived:

- `type` / `recommended_action` — `(next_best_action or {}).get("type", "review_case")`,
  underscores humanized for display.
- `risk_level` — `high` if state is `HUMAN_REVIEW_REQUIRED` or `risk_score ≥ 60`; else
  `medium` if `days_stalled ≥ 3`; else `low`.
- `confidence` — translated bands: `high` (`lead_score ≥ 60`), `medium` (`≥ 40`), `low`.

### 2.3 `approval_queue(tenant_id)` / `decide(...)`
`approval_queue` returns the tenant's drafts with `approval_status == "PENDING"` as
`ApprovalItem`s. `decide(approval_id, *, tenant_id, role, user, decision, edited_message)`
requires the `approve` permission, verifies the draft belongs to the tenant, sets the status
to `APPROVED`/`REJECTED`, stores `edited_message` when provided, and appends a
`HUMAN_APPROVAL_GRANTED`/`HUMAN_APPROVAL_REJECTED` audit event with payload
`{approval_id, edited: bool, via: "dashboard"}`.

### 2.4 `stuck_cases(tenant_id, *, now, min_days=5.0)`
Active cases with `days_stalled ≥ min_days` (**stuck threshold: ≥ 5 days**), sorted by days
descending. Each row names the **blocker**: the first open missing item's `field_key`, or
`"no client response"` when nothing is missing; plus the open missing-item keys, the
overdue-promise count, and a `next_action` text from `explain()`.

### 2.5 `missing_info(tenant_id)`
Active cases with any missing item whose `status != "received"`; each row lists
`{type: field_key, blocks_quote}` per open item, with the client name.

### 2.6 `promises(tenant_id, *, now)`
Buckets every promise: `fulfilled`; `breached` (`status == "broken"`); `overdue` (open and
`now > due_at`); `due_today` (open and `due_at.date() == now.date()`).

### 2.7 `offers_followup(tenant_id, *, now)`
Cases with a registered `offer_sent_at` in state `OFFER_SENT`, `FOLLOW_UP_ACTIVE`, or
`NEGOTIATION`. `days_without_response = now - offer_sent_at`. **Risk bands as coded:**
`losing_risk = high` at `≥ 5` days, `medium` at `≥ 2` days, else `low` (the 2d/5d bands).
The recommendation is `explain()` with context `"call before the client books elsewhere"`
when `days ≥ 3`, otherwise `"light follow-up appropriate"`. Sorted by days silent, descending.

### 2.8 `pipeline(tenant_id)`
Groups all tenant cases by `state.value` into `{count, value}` buckets (final states
included, so WON/LOST show alongside active stages).

### 2.9 `risk_alerts(tenant_id, *, now)`
Four rule-based alert types per case: `human_review` (state is `HUMAN_REVIEW_REQUIRED`),
`high_risk_case` (`risk_score ≥ 60`), `high_value` (`value_estimate ≥ 15000` and active —
"handle personally"), and `breached_promise` (one per broken promise, naming promisor and
what was promised).

### 2.10 `activity(tenant_id, *, limit=20)`
Walks the shared `AuditLog` newest-first, keeps events whose `case_id` belongs to the tenant
(or has no case id), and emits `ActivityEvent`s with a humanized `summary` derived from the
event type.

### 2.11 Case ops: `snooze` / `assign`
`snooze(case_id, *, tenant_id, role, until)` (permission `snooze`) hides the case from the
action queue until `until`. `assign(case_id, *, tenant_id, role, assignee)` (permission
`assign`) records the assignment and appends a `CASE_ASSIGNED` audit event.

## 3. `explain()` — the business-language translator

The **core UX rule of the module: no raw scores, ever.** Every recommendation carries a
`reason` built by `explain(case, *, days_no_response=0, context="")`, which translates
numbers into owner language:

- `lead_score ≥ 70` → *"high-priority client"*; `≥ 45` → *"warm client"* (the number itself
  never appears);
- `value_estimate > 0` → *"job worth ~€12,000"* (money formatting is the only number shown);
- `days_no_response ≥ 3` → *"no response for 3 days"*; `≥ 1` → *"waiting N day(s)"*;
- up to three open missing items → *"missing: installation photo, …"*;
- optional `context` appended; fallback: *"Needs review."*

The bad/good example from the module docstring is the contract:

> **Never** `"LeadScore 0.81"` — **always** *"High priority: client is responsive, offer
> value is high, and no response after 3 days"*.

This is enforced by tests: `test_2_sorted_by_urgency_value_risk_due` asserts no bare decimal
(`0.81`-style) and no word "score" in any queue reason, and
`test_explain_translates_scores_to_business_language` checks the full translation.

## 4. HTML renderer — the MVP view and print/email digest

`finalis/dashboard_html.py::render_dashboard(svc, *, tenant_id, now)` is a dependency-free
renderer that calls all ten read sections and emits one self-contained HTML page (inline
CSS, no JS framework) with all 11 components, each delimited by a
`<!-- component:Name -->` marker. It proves the view layer end-to-end today and **doubles as
the print/email digest** (self-contained page, no external assets). Approve/Edit/Reject and
"Do it" buttons carry `data-approve`/`data-edit`/`data-reject`/`data-case` attributes — the
hooks the interactive UI wires up. All dynamic text passes through `html.escape`.

## 5. Production plan

- **Next.js UI on the same contracts.** The React Command Center (per
  `../11-ux-dashboards.md` §1 and §6: App Router, RSC for tenant-scoped reads, Server
  Actions for approve/snooze/assign) consumes the exact `DashboardService` section contracts
  — the service is the single source of section shapes, so HTML view and React view cannot
  drift.
- **Live updates via SSE** per `../22-api-and-event-model.md`: `GET /v1/stream`
  (`text/event-stream`, WebSocket upgrade optional) pushes tenant-scoped domain events so
  approvals and queue changes appear without polling.
- **REST endpoints** — the 15 endpoints in [api-contracts.md](api-contracts.md), each a thin
  HTTP wrapper over one implemented service method; folded into the existing
  `../openapi.finalis.yaml`.
- **Data feed** — `register_case`/`register_approval` replaced by tenant-scoped DB queries
  (see README); section methods and contracts unchanged.
