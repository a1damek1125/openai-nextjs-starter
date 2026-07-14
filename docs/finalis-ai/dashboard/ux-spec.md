# Command Center — UX Spec

## Layout (top to bottom, as rendered)

1. **Mission line** — "What should I do today to close more cases and lose fewer clients?"
2. **SummaryCards** — 8 priority cards (active, attention, approvals, stuck, overdue
   promises, pipeline €, expected close €, won €).
3. **TodayActionQueue** — first real section, max 10 items, one action button each.
4. **ApprovalQueue** — draft text shown in full, Approve / Edit / Reject buttons
   (`data-approve/edit/reject` attributes wired for the interactive UI).
5. **StuckCasesTable** — state, days, blocker, next step.
6. **MissingInfoQueue** — client + missing items, blocks-quote flagged.
7. **PromiseTracker** — four buckets with counts.
8. **OfferFollowUpBoard** — client, value, days silent, losing-risk badge, recommendation.
9. **PipelineByState** — table with count + value.
10. **RiskAlerts** — high badge + type + plain-language detail.
11. **ActivityTimeline** — recent audit events, actor-tagged.
12. **CaseQuickView** — hidden panel; opens on any case click with timeline, missing items,
    promises, evidence (Designed: evidence-chip drill-down to `EvidenceReference`).

## The recommendation-explanation rule

Every AI recommendation must answer: **why this action · why now · what happens if ignored
· what evidence supports it.** Today `explain()` covers *why/why-now* (lead band, value,
staleness, missing items) and the offer board covers *if-ignored* ("call before the client
books elsewhere"); evidence links land with CaseQuickView Phase 2. **No unexplained scores**
— enforced by test: no bare decimals, no "score" in any user-facing reason. Badges use
plain risk words (high/medium/low), never numbers.

## States

- **Empty**: every section renders a friendly line ("Nothing urgent — all cases
  progressing.") — implemented and tested.
- **Loading / error**: Designed for the async Next.js UI (skeleton cards; retry banner;
  never a blank screen).
- **Filters & search** (Designed): state, risk, owner, value band, due date; client/case
  search; operator role auto-filters to assigned cases.

## Interaction principles

One-click approve/edit/reject; one action button per queue item; case click → QuickView
(never navigate away from the queue); snooze returns the case automatically at expiry
(tested); everything the AI did autonomously is visible in the timeline — no hidden
actions.
