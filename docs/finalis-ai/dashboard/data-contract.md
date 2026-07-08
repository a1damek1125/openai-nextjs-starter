# Command Center Data Contract

The five contract objects below are defined **as coded** in `finalis/dashboard.py`
(dataclasses). They are the stable boundary between the service layer and every view (the
server-rendered HTML today, the Next.js UI and REST responses later). Example JSON uses the
realistic HVAC tenant from `tests/test_dashboard.py::hvac_fixture` (tenant `hvac-1`,
`now = 2026-07-07T12:00`).

## 1. `DashboardSummary`

| Field | Type | Meaning (as computed) |
|---|---|---|
| `active_cases_count` | int | Cases in `ACTIVE_STATES` |
| `attention_required_count` | int | Union of stuck ∪ pending-approval ∪ `HUMAN_REVIEW_REQUIRED` case ids |
| `pending_approvals_count` | int | Drafts with `approval_status == "PENDING"` |
| `stuck_cases_count` | int | Active cases stalled ≥ 5 days |
| `overdue_promises_count` | int | Open promises past `due_at` |
| `pipeline_value` | float | Σ `value_estimate` over active cases |
| `expected_close_value` | float | Σ `value_estimate × min(lead_score,100)/100`, rounded 2dp |
| `won_value_period` | float | Σ value of `WON` cases |
| `lost_value_period` | float | Σ value of `LOST` cases |

```json
{
  "active_cases_count": 4,
  "attention_required_count": 3,
  "pending_approvals_count": 1,
  "stuck_cases_count": 1,
  "overdue_promises_count": 1,
  "pipeline_value": 41000.0,
  "expected_close_value": 28490.0,
  "won_value_period": 9000.0,
  "lost_value_period": 4000.0
}
```

## 2. `DashboardCaseCard`

> **Status note:** `DashboardCaseCard` is **defined in the contract but assembled implicitly
> by the section methods** — no current service method returns it directly; its fields are
> spread across `action_queue` / `stuck_cases` / `offers_followup` rows. Flag it as the
> **available shape** for the Next.js case-list/CaseQuickView card; a `case_card(case_id)`
> assembler is a small production addition, not a redesign.

| Field | Type | Meaning |
|---|---|---|
| `case_id` | str | Case id |
| `tenant_id` | str | Owning tenant |
| `title` | str | Job title (e.g. "Heat pump install") |
| `client_name` | str | Display name of the client |
| `state` | str | `CaseState` value |
| `priority` | str | `today` \| `this_week` \| `normal` |
| `estimated_value` | float | `Case.value_estimate` |
| `risk_level` | str | `high` \| `medium` \| `low` |
| `next_action` | str \| null | NBA type |
| `next_action_reason` | str | Business-language reason (`explain()`) |
| `due_at` | datetime \| null | Next-action due time |
| `last_activity_at` | datetime \| null | Last activity timestamp |
| `human_review_required` | bool | Case frozen for review |
| `missing_items_count` | int | Open missing items |
| `overdue_promises_count` | int | Open promises past due |

```json
{
  "case_id": "c-hot-1", "tenant_id": "hvac-1",
  "title": "Heat pump install", "client_name": "Jan Kowalski",
  "state": "OFFER_SENT", "priority": "today",
  "estimated_value": 12000.0, "risk_level": "medium",
  "next_action": "send_follow_up",
  "next_action_reason": "High-priority client; job worth ~€12,000; no response for 3 days.",
  "due_at": "2026-07-07T10:00:00", "last_activity_at": "2026-07-04T12:00:00",
  "human_review_required": false,
  "missing_items_count": 0, "overdue_promises_count": 0
}
```

## 3. `OwnerActionItem` (Today's Action Queue)

| Field | Type | Meaning |
|---|---|---|
| `id` | str | `act-` + case-id prefix |
| `case_id` | str | Case id |
| `type` | str | NBA type (`send_follow_up`, `review_case`, …) |
| `title` | str | `"<title> — <client>"` |
| `reason` | str | **Business language, always filled** (`explain()`) |
| `recommended_action` | str | Humanized action ("send follow up") |
| `urgency` | float | **Internal sort key — never displayed raw** |
| `risk_level` | str | `high` \| `medium` \| `low` |
| `value_impact` | float | `Case.value_estimate` |
| `confidence` | str | **Translated band: `high` \| `medium` \| `low`** (from lead score ≥60 / ≥40 / else) — never the underlying number |
| `due_at` | datetime \| null | Next-action due time |
| `status` | str | Default `"open"` |

```json
{
  "id": "act-c-hot-1", "case_id": "c-hot-1", "type": "send_follow_up",
  "title": "Heat pump install — Jan Kowalski",
  "reason": "High-priority client; job worth ~€12,000; no response for 3 days.",
  "recommended_action": "send follow up",
  "urgency": 23616.0,
  "risk_level": "medium", "value_impact": 12000.0,
  "confidence": "high", "due_at": "2026-07-07T10:00:00", "status": "open"
}
```
(`urgency` appears in the JSON contract for sorting/debugging only; UIs MUST NOT render it.)

## 4. `ApprovalItem` (Human Approval Queue)

| Field | Type | Meaning |
|---|---|---|
| `id` | str | `ap-1`, `ap-2`, … |
| `case_id` | str | Case the draft belongs to |
| `action_type` | str | ACE action (`send_price_negotiation`, …) |
| `draft_message` | str | The AI-drafted outbound message |
| `reason` | str | Why approval is needed |
| `risk_level` | str | `high` \| `medium` \| `low` |
| `approval_status` | str | `PENDING` \| `APPROVED` \| `REJECTED` |
| `created_at` | datetime | Draft creation time |
| `expires_at` | datetime \| null | Optional expiry |

```json
{
  "id": "ap-1", "case_id": "c-hot-1",
  "action_type": "send_price_negotiation",
  "draft_message": "[SZKIC] wracam do tematu oferty...",
  "reason": "high-value negotiation", "risk_level": "high",
  "approval_status": "PENDING",
  "created_at": "2026-07-07T12:00:00", "expires_at": null
}
```

## 5. `ActivityEvent` (Activity Timeline)

| Field | Type | Meaning |
|---|---|---|
| `id` | str | Audit event id |
| `case_id` | str \| null | Case scope (null = tenant-level) |
| `event_type` | str | Audit event type (`CLIENT_REPLIED`, `MESSAGE_SENT`, …) |
| `actor_type` | str | `ai` \| `human` \| `provider` \| `system` |
| `summary` | str | Humanized event type ("Client replied") |
| `created_at` | str | Timestamp (currently empty string — audit event timestamps are not yet projected) |

```json
{
  "id": "ev-42", "case_id": "c-hot-1", "event_type": "CLIENT_REPLIED",
  "actor_type": "provider", "summary": "Client replied", "created_at": ""
}
```

## 6. RBAC — role-permission matrix (`ROLE_PERMISSIONS`, as coded)

| Role | `view_all` | `view_assigned` | `approve` | `assign` | `snooze` |
|---|:-:|:-:|:-:|:-:|:-:|
| `owner` | ✅ | — | ✅ | ✅ | ✅ |
| `manager` | ✅ | — | ✅ | ✅ | ✅ |
| `operator` | — | ✅ | — | — | ✅ |
| `viewer` | ✅ | — | — | — | — |
| `ai_worker` | — | — | — | — | — |

**`ai_worker` has NO UI permissions** — the empty set is deliberate: the AI never approves
its own drafts via the dashboard (enforced; see
`tests/test_dashboard.py::TestApprovals::test_ai_worker_cannot_approve`). Any missing
permission raises `PermissionDenied`. Mutations additionally verify the target belongs to
the caller's tenant.

## 7. PII-safe display

The contracts expose only what a card needs: **client display name, job title, case state,
money values, and business-language reasons**. No phone numbers, emails, addresses, message
bodies (other than the specific draft awaiting approval), or document contents cross this
boundary — the dashboard renders projections, not the underlying `Party`/`Message` records
(per `../11-ux-dashboards.md` §6: "never expose PII beyond what a card needs"). All strings
are HTML-escaped by the renderer.
