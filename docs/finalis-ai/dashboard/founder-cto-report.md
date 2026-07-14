# Finalis Case Command Center — Founder / CTO Report

**Date**: 2026-07-07 · **Branch**: `claude/finalis-case-command-center`
**Test command**: `python3 -m pytest tests/ -q` → **204 passed** (19 dashboard-specific).

Wording: **Implemented and tested** = passing tests · **Mocked** = fixtures/mocks ·
**Designed** = docs only.

---

## The 14 direct answers

**1. What was implemented?**
The complete dashboard **service layer** (`finalis/dashboard.py`) computing all 13 required
sections from real domain objects — executive summary (9 aggregates), Today's Action Queue
(urgency-sorted with business-language reasons), Human Approval Queue (approve/edit/reject
with tenant + RBAC checks and audit), Stuck Cases (≥5 days, blocker + missing items +
overdue promises), Missing Information Queue, Promise & Deadline Tracker (due-today/
overdue/breached/fulfilled buckets), Offer Follow-up Board (days-silent + losing-risk +
recommendation), Pipeline by State (count + value), Risk Alerts (human-review, high-risk,
high-value, breached-promise), Activity Timeline (tenant-filtered, newest-first), plus
snooze/assign case operations. And a **server-rendered HTML view**
(`finalis/dashboard_html.py`) with all 11 required components, badges, one-click
approve/edit/reject buttons, and clean empty states. The **`explain()` translator** enforces
the core UX rule in code: scores become sentences ("High-priority client; job worth
~€12,000; no response for 3 days"), and a test rejects any bare decimal or the word "score"
in user-facing reasons.

**2. What is mocked?** The data feed: cases and approvals are registered via
`register_case`/`register_approval` from realistic HVAC fixtures (six case situations —
hot silent offer, stuck-with-photos, fresh intake, won, lost, high-risk review). In
production these become DB queries over the same Case Graph objects — the section logic is
unchanged.

**3. What is only documented?** The Next.js interactive UI, the 15 REST endpoints, filters
and search, loading/error states for async fetching, evidence-link drill-downs, SSE live
updates.

**4. What is missing?** Real auth (roles are enforced by the service but identities are
strings, not sessions), persistence, pagination, per-user assigned-case filtering for the
operator role (permission model exists; the view filter is designed).

**5. Does the dashboard render?** **Yes — implemented and tested**: a self-contained HTML
page with all 11 components (asserted by marker), real fixture data, money formatting, and
the mission line.

**6. Does it show priority cases?** **Yes — tested**: the €20k human-review case and the
€12k three-days-silent offer rank in the top two; the fresh €3k intake ranks last;
snoozing removes a case from the queue.

**7. Does it show human approvals?** **Yes — tested**: pending items with draft text, risk
badge, and approve/edit/reject controls; empty state after decision.

**8. Does approval/rejection work or is it mocked?** The **decision logic is implemented
and tested** (status change, edited-message capture, queue removal, audit event with
`via: dashboard`); the delivery of the approved action is the ACE module's job (tested
there). No HTTP layer yet — calls are service-level.

**9. Does it connect to real Case Graph or mock data?** Both, precisely: it consumes **real
`Case`/`MissingItem`/`Promise` objects and the real hash-chained audit log** — fed by
fixtures rather than a database. Same objects the Case Graph tests use.

**10. Are tests passing?** **Yes — 19/19 dashboard, 204/204 repo-wide.** All 13 mandated
scenarios covered, plus the E2E approve flow and the language rule.

**11. Is tenant isolation implemented?** **At service level, yes — tested three ways**:
cross-tenant approval decision raises PermissionDenied; cross-tenant snooze/assign raise;
cross-tenant audit events are excluded from the activity feed. Also RBAC-tested: `ai_worker`
and `viewer` cannot approve. DB-level RLS remains Designed.

**12. Is this production-ready?** **No.** The decision logic and contracts are verified;
auth, persistence, the interactive UI, and RLS are not built.

**13. What blocks production?** Real auth/session + RBAC wiring, persistence + the REST
layer, the Next.js UI, RLS, pagination/performance for large tenants.

**14. What should be built next?**
The **UI sprint**: (1) FastAPI endpoints from api-contracts.md over the tested service;
(2) Next.js dashboard consuming them (the starter kit's stack), components 1:1 with
`COMPONENTS`; (3) auth + role wiring; (4) Playwright browser E2E replaying the tested
approve flow; (5) SSE updates. The service layer needs no changes for any of this.

---

**Verified**: all sections' computation, sorting, business-language rule, approval flow +
audit, tenant isolation ×3, RBAC ×2, empty states, full-page render with 11 components.
**Mocked**: data registration (fixtures). **Not verified**: browser behavior, auth,
concurrency, large-data performance.

## Top 10 next tasks
1. REST endpoints over DashboardService (contracts written).
2. Next.js dashboard app + the 11 components against those endpoints.
3. Auth (NextAuth) + role mapping to ROLE_PERMISSIONS.
4. Operator role: assigned-cases-only view filter.
5. Playwright E2E: login → dashboard → approve → audit visible.
6. SSE/live updates on approval + activity feeds.
7. Filters (state/risk/owner/value/due) + client search.
8. CaseQuickView: timeline + evidence links (EvidenceReference drill-down).
9. Pagination + query performance against Postgres.
10. Owner daily digest email reusing the HTML renderer.
