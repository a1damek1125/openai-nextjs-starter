# Command Center — API Contracts

**Status: Designed** — no HTTP server exists yet. Every endpoint maps 1:1 to an
**implemented and tested** `DashboardService` method, so the API layer is a thin wrapper.
All endpoints are tenant-scoped (from the session), RBAC-gated per the role matrix in
`data-contract.md`, and fold into the existing `openapi.finalis.yaml` under `/v1/dashboard`.

## Read endpoints

| Endpoint | Service method | Response |
|---|---|---|
| `GET /dashboard/summary` | `summary(tenant_id, now)` | `DashboardSummary` (9 aggregates) |
| `GET /dashboard/action-queue` | `action_queue(tenant_id, now)` | `OwnerActionItem[]`, urgency-sorted |
| `GET /dashboard/approval-queue` | `approval_queue(tenant_id)` | `ApprovalItem[]` (PENDING only) |
| `GET /dashboard/stuck-cases` | `stuck_cases(tenant_id, now, min_days=5)` | rows: state, days, blocker, missing, overdue promises, next step |
| `GET /dashboard/missing-info` | `missing_info(tenant_id)` | rows: client, items[{type, blocks_quote}] |
| `GET /dashboard/promises` | `promises(tenant_id, now)` | buckets: due_today/overdue/breached/fulfilled |
| `GET /dashboard/offers-follow-up` | `offers_followup(tenant_id, now)` | rows: client, sent_at, value, days silent, losing_risk, recommendation |
| `GET /dashboard/pipeline` | `pipeline(tenant_id)` | `{state: {count, value}}` |
| `GET /dashboard/risk-alerts` | `risk_alerts(tenant_id, now)` | `[{case_id, type, detail}]` |
| `GET /dashboard/activity?limit=20` | `activity(tenant_id, limit)` | `ActivityEvent[]` newest-first, with `created_at` |

## Mutating endpoints (idempotency-key required)

| Endpoint | Service method | Notes |
|---|---|---|
| `POST /dashboard/actions/{id}/approve` | `decide(id, ..., decision="approve")` | body: `{edited_message?}`; 403 cross-tenant / non-approver role; writes `HUMAN_APPROVAL_GRANTED` |
| `POST /dashboard/actions/{id}/reject` | `decide(id, ..., decision="reject")` | body: `{reason}`; writes `HUMAN_APPROVAL_REJECTED` |
| `POST /dashboard/actions/{id}/edit` | `decide(..., edited_message=...)` | edit-then-approve; both texts retained |
| `POST /dashboard/cases/{id}/snooze` | `snooze(case_id, ..., until)` | roles: owner/manager/operator |
| `POST /dashboard/cases/{id}/assign` | `assign(case_id, ..., assignee)` | roles: owner/manager; writes `CASE_ASSIGNED` |

Errors: RFC-7807 problem+json (per doc 22); `PermissionDenied` → 403; unknown id → 404.
Approving an approval triggers the **ACE send path** (`decide_approval` in the Action &
Communication Engine) — the dashboard never sends messages itself.
