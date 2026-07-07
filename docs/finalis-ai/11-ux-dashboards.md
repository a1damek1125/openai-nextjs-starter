# Finalis AI — UX & Dashboards

> **Design north star:** the owner of a small HVAC/plumbing/electrical/renovation business must
> **understand a case in 20 seconds** and act on it in one tap. Finalis is a *worker*, not a
> chatbot, so every screen answers three questions: *what changed, what it's worth, and what to
> do next* — with the AI's **evidence and confidence always in view**. This document specifies
> the five MVP screens, their components, the exact entities and scores they render (from
> `04-data-model.md` and `05-algorithms-and-scoring.md`), primary actions, and empty/loading/
> error states, then recommends a concrete Next.js/React implementation.

**Framing.** The product's headline promise is **Revenue Recovery**: money that a normal shop
leaks — hot leads that go cold, offers nobody followed up, cases stuck on a missing photo,
promises the client (or the shop) forgot. Every screen is built to make that leaked money
*visible and recoverable*, so the top-level KPI is **recovered pipeline value**, not "messages
sent".

---

## 0. Cross-cutting UX rules (apply to all screens)

These rules are non-negotiable and should be enforced by shared components, not per-screen code.

| Rule | Implementation contract |
|---|---|
| **Every AI claim shows evidence** | Any rendered assertion sourced from a `RiskFlag`, `DecisionBrief`, `ExtractedField`, `Comparison`, `Promise`, or `MissingItem` MUST render an `<EvidenceChip>` that opens the `EvidenceReference` (message, `Call` segment ts-range, `Document` page+bbox, or web `Source`). No evidence ref → the claim is styled as *unverified*. |
| **Every score shows confidence + band** | Scores render via `<ScoreBadge score={…} kind="LeadScore" />` which shows the number, its **band** (Hot/Warm/Cool/Cold for `LeadScore`), and a confidence dot. If the underlying `Confidence < θ_conf` (0.6) or the score is `low_confidence` (cold-start), the badge is muted and labelled *"unverified"*. |
| **Abstention is visible, not hidden** | Below-threshold facts render in an *"Unverified / needs a clearer scan"* zone (per §6 Abstention rule). Never present a low-confidence value as fact. |
| **Three action verbs everywhere** | Case-level actions are always **Approve**, **Call**, **Send follow-up** (plus overflow). These map to `HumanApproval.decision`, an outbound `Call` `Action`, and advancing the `FollowUpSequence`. |
| **Mobile-first** | Owners work from a phone in a van. All layouts are single-column-first, thumb-reachable primary buttons, and every table degrades to a stacked card list < 768px. |
| **20-second comprehension** | Each case surface leads with one line: *value range → next best action → why*. Detail is progressive-disclosure below the fold. |

**Shared components (used across screens):** `<ScoreBadge>`, `<EvidenceChip>`, `<ConfidenceDot>`,
`<StatusPill>` (renders `Case.status` from the state machine), `<ActionBar>` (Approve/Call/Follow-up),
`<AutonomyBadge>` (shows `Case.autonomy_level` 1–5), `<EmptyState>`, `<SkeletonRow>`, `<ErrorState>`.

---

## 1. Home Dashboard — Case Command Center

### Purpose
The owner's morning screen. Turns the pile of open `Case`s into a prioritized, self-updating work
queue and quantifies **Revenue Recovery**. Answers: *"Where is money leaking right now, and what
are the 5 things I (or the AI) should do about it before lunch?"*

### Layout (top → bottom, single column on mobile)

**A. Revenue Recovery banner (hero).** The emotional and financial anchor.
- **Estimated pipeline** — Σ `Case.value_estimate` over active states, risk-adjusted by
  `LeadScore/100` (mirrors NBA `Value`). Shown as a range.
- **Recovered leads / recovered pipeline value** — value of cases that re-engaged out of
  `RECOVERY_LATER`/`FOLLOW_UP_ACTIVE` (from `WON`/`SCHEDULED` transitions whose prior state was a
  parked/stalled state). This is the "money Finalis got back" number.
- **Closed cases** — count + value of `WON`/`COMPLETED` this period, with AI **close-assist rate**.
- Secondary line: *"€X at risk right now"* = Σ value of cases with high `StuckScore` or unanswered
  `Offer`s.

**B. Priority tiles (the work queue).** A responsive grid of count+value tiles; tapping filters the
list below. Each tile is a saved query over real entities:

| Tile | Backing query | Sort key |
|---|---|---|
| **Hot leads** | `Case` where `LeadScore ≥ 70` (Hot band) and status active | `lead_score desc` |
| **Stuck cases** | `Case` where `StuckScore ≥ θ_stuck` | `stuck_score desc` (highest-value stalls first) |
| **Offers without response** | `Offer.status = sent` with no inbound since `sent_at`; case in `OFFER_SENT`/`FOLLOW_UP_ACTIVE` | time since `sent_at` |
| **Missing documents** | `MissingItem.status ∈ {missing,requested}` and `blocks_quote=true` | `weight (w_i) desc` |
| **Promises due** | `Promise.status = open` and `due_at ≤ today+1`; ordered by `breach_score` | `PromiseBreachScore desc` |
| **Calls to make** | `Task` of type call OR `Case.next_best_action.type = call` due today | `next_action_due_at` |
| **AI actions requiring approval** | `HumanApproval` where `decided_at IS NULL` | `deadline asc`, `sla_breached` first |

**C. HumanApproval queue (the AI's "outbox waiting on you").** A dedicated, always-visible strip —
this is where autonomy meets the human. Each row:
- What the AI wants to do (`HumanApproval.context` + `recommended_option`), the case it's on
  (`<StatusPill>`), the `Action.type`, the `autonomy_level_used`, and the `deadline` (red if
  `sla_breached`).
- The **why**: the `DecisionBrief.summary` snippet + `<EvidenceChip>`s.
- Inline **Approve / Edit / Reject** → writes `HumanApproval.decision`, unblocking the `Action`.

**D. Case list (filtered by active tile).** Each row is a 20-second case card:
`value_range · <StatusPill> · next_best_action one-liner · <ScoreBadge LeadScore> · owner avatar ·
time-in-state`, with the `<ActionBar>` (Approve/Call/Send follow-up) on hover/expand.

### Data shown
`Case` (status, value_estimate, lead_score, stuck_score, next_best_action, next_action_due_at,
owner_id), `Offer` (status, sent_at), `MissingItem` (weight, blocks_quote, status), `Promise`
(due_at, breach_score, status), `Task`, `HumanApproval`, `DecisionBrief` (summary), `LeadScore`
band, `StuckScore`, `PromiseBreachScore`.

### Primary actions
- Filter by tile; open a case; **Approve/Reject** a `HumanApproval` inline; **Call** or **Send
  follow-up** on any case card; snooze/reassign a `Task`; bulk-approve a batch of follow-ups.

### States
- **Loading:** hero shows skeleton numbers; tiles show `<SkeletonRow>` counts; list shows 5
  skeleton cards. Never block the whole screen — stream tiles as their queries resolve.
- **Empty (new tenant):** hero reads *"No pipeline yet — connect a channel to start recovering
  leads"* with a CTA to the AI Control Center integrations. Tiles render `0` with a one-line
  explainer, not blank.
- **Empty (all clear):** *"Inbox zero — the worker is on top of every case."* Still show the
  Revenue Recovery numbers.
- **Error:** per-tile `<ErrorState>` with retry; a failed tile never takes down the others.
- **Stale:** if the nightly stuck sweep / recompute is behind, show a *"scores updated Xh ago"*
  timestamp so the owner knows freshness.

---

## 2. Case Detail View

### Purpose
Everything about one `Case`, arranged so the owner grasps it in 20 seconds and can act or approve
without reading a transcript. This is the primary decision surface.

### Layout

**Header (the 20-second summary).** `<StatusPill status>` + `value_range` +
`<ScoreBadge LeadScore>` + `<AutonomyBadge>` + primary party name. One-line
`DecisionBrief.recommended_step` ("Call today after 16:00, offer premium variant"). Persistent
`<ActionBar>`: **Approve · Call · Send follow-up**.

**Left / main column — the Timeline (Timeline Worker).**
A unified, reverse-chronological event stream built from the append-only `AuditEvent` log +
`Message`/`Call`/`Document`/`Photo`/`Action`/state-transition entities. Each item shows actor
(`ai_worker`/`human`/`client`), channel icon, a one-line summary, and — for anything AI-asserted —
inline `<EvidenceChip>`s. State transitions render as labelled markers ("→ OFFER_SENT"). Filters:
All / Messages / Calls / Documents / AI actions / State changes.

**Right column (or below the fold on mobile) — the work panels:**

| Panel | Entities & fields | Notes |
|---|---|---|
| **Next Best Action** | `Case.next_best_action` (chosen `Action` + `utility_score` + `chosen_over` runner-ups) | Shows *why this over that* (NBA `Utility` breakdown). Buttons execute or approve it. |
| **Decision Brief** | `DecisionBrief` (summary, value_range, situation, recommended_step, rationale, risk_note, confidence, evidence_ref_ids) | Owner-facing recommendation with `<ConfidenceDot>` and evidence. Marked *superseded* if stale. |
| **Missing information** | `MissingItem` list (label, weight `w_i`, blocks_quote, status, channel_used) | `blocks_quote=true` items pinned + red. One-tap "Request now". |
| **Promises** | `Promise` list (what, due_at, promisor→promisee, status, breach_score) | Split *client promises* vs *company promises*; sorted by `PromiseBreachScore`. |
| **Offers** | `Offer` list (origin, price, status, offer_score, version) | Link to Offer Comparison (screen 4) when ≥2 offers. |
| **Documents & Photos** | `Document` (type, doc_risk_score, overall_confidence, status), `Photo` (vision_tags, quality) | Each links into Document Analysis (screen 3). `needs_rescan` flagged. |
| **Risk flags** | `RiskFlag` (category, severity, description, requires_human, status) | Sorted by severity; each has an `<EvidenceChip>`; `requires_human` badged. |
| **Follow-up history** | `FollowUpSequence` (steps, active_step_index, state, max_attempts) + past outbound `Action`s | Shows what was sent, when, on which channel, and the next scheduled touch (respecting quiet hours). |
| **AI confidence indicator** | Case-level roll-up of `DecisionBrief.confidence` + deciding-fact `Confidence` | If below `θ_conf`, the whole action bar defaults to *"needs your review"* rather than autonomous send. |

### Primary actions
- **Approve** the pending `HumanApproval` / the next best `Action`.
- **Call** (launch outbound `Call` via telephony; shows `VoiceProfile` in use).
- **Send follow-up** (advance `FollowUpSequence` / send a drafted `Message`).
- Request a `MissingItem`; resolve/acknowledge a `RiskFlag`; mark a `Promise` fulfilled/waived;
  change `Case.autonomy_level`; reassign owner; move state manually (guarded by the state machine's
  allowed transitions and invariants — illegal transitions are disabled with a tooltip).

### States
- **Loading:** header + skeleton timeline; panels lazy-load independently.
- **Empty:** brand-new `NEW_CONTACT` case shows only the intake timeline and a *"Finalis is
  gathering info"* banner; work panels render *"nothing yet"* copy, not blank boxes.
- **Error:** timeline and each panel fail independently with retry; the `<ActionBar>` stays usable
  from cached case header data.
- **Frozen (HUMAN_REVIEW_REQUIRED):** a banner explains autonomy is capped at Level 2 and all
  outbound actions are drafts awaiting approval (per state-machine invariant 2).

---

## 3. Document Analysis View

### Purpose
Make one `Document` trustworthy: what it says, what we extracted, what's risky, what we *couldn't*
verify — always side-by-side with the source so the owner can trust or challenge every field. Backs
the `DOCUMENT_ANALYSIS` state and the *"requires human before signing"* gate.

### Layout — split view
**Left: the document itself.** Rendered pages with highlight overlays. Clicking an
`ExtractedField` or `RiskFlag` scrolls to and boxes its `page`+`bbox` (the `EvidenceReference`
locator). This bidirectional link is the core trust mechanism.

**Right: the analysis, in stacked sections.**

1. **Summary** — plain-language `Document` summary + `<ScoreBadge DocRisk kind="DocRisk">` and
   overall `<ConfidenceDot>` from `overall_confidence`. If `DocRisk ≥ θ_docrisk` (60), a prominent
   **"Requires human review before signing"** banner (never framed as legal advice).
2. **Extracted fields** — table of `ExtractedField`:

   | Field | Value | Confidence | Evidence |
   |---|---|---|---|
   | `field_key` | `field_value` | `Confidence` (= OCR_q·Extraction_q·Source_q·Consistency_q) with `<ConfidenceDot>` | `<EvidenceChip>` → page+bbox |

   Rows below `θ_conf` drop into an **"Unverified — needs a clearer scan"** subsection (abstention
   rule §6). `verified_by_human` fields get a check.
3. **Risks** — `RiskFlag` list grouped by `category` (asymmetry, missing_element, contradiction,
   payment, clause, quality, legal), each with `severity` bar, description, `requires_human` badge,
   and evidence.
4. **Contradictions** — the `contradiction`-category flags called out separately, each showing
   *this doc says X* vs *prior agreement/other doc/call says Y* with **both** evidence refs
   (`Message`, `Call` segment, or other `Document` region).
5. **Questions to ask** — AI-generated clarifying questions the owner should put to the client
   (derived from missing standard elements `M` and low-confidence fields); each is one-tap
   *"Send as follow-up"* (creates a `MissingItem`/`Message`).
6. **Evidence references** — a consolidated `EvidenceReference` list for the whole document (audit
   view), each with snippet + locator + confidence.

### Data shown
`Document` (ocr_quality, doc_risk_score, overall_confidence, status, pages, layout_json),
`ExtractedField` (field_key/value, page, bbox, the four `_q` factors + product `confidence`),
`RiskFlag`, `EvidenceReference`, `DocRisk`, `Confidence`.

### Primary actions
- Verify/correct a field (`verified_by_human`, feeds calibration as training data).
- Acknowledge/resolve a `RiskFlag`; send a "questions to ask" item as a client follow-up.
- **Request a clearer scan** (creates/re-opens a document `MissingItem` → `WAITING_FOR_DOCUMENTS`).
- Escalate to `HUMAN_REVIEW_REQUIRED` for signing.

### States
- **Loading / processing:** `Document.status = processing` → progress view *"Reading page 2 of 5…"*
  with OCR quality preview; fields stream in as extracted.
- **Low quality:** `ocr_quality` low → banner *"Scan is hard to read — some fields unverified"* with
  a **Request clearer scan** CTA; low-confidence fields greyed.
- **Empty:** no extractable fields → *"We couldn't read structured data from this file."*
- **Error:** OCR/extraction failure → `<ErrorState>` with retry and manual-entry fallback; the
  original document still renders on the left.

---

## 4. Offer Comparison View

### Purpose
Turn two or more `Offer`s (ours, competitor, or client-provided) into a clear, value-based
recommendation with hidden risks exposed — the negotiation weapon for `NEGOTIATION`/`OFFER_SENT`.
Backed by a stored `Comparison`.

### Layout
**A. Comparison table (offers as columns, axes as rows).** Sticky first column of axes; each
`Offer` a column. On mobile this pivots to one card per offer with the axis list inside.

| Axis (weight) | Offer A | Offer B | Offer C |
|---|---|---|---|
| **OfferScore (total)** | badge | badge | badge |
| Price (0.25) | value + per-axis score | … | … |
| Scope (0.20) | | | |
| Warranty (0.15) | | | |
| Time (0.15) | | | |
| Payment (0.10) | | | |
| Risk (0.10) | | | |
| Service (0.05) | | | |

`OfferScore` and each per-axis score come from `Comparison.axis_scores` (§7); the best cell per row
is highlighted. Weights shown are the tenant's (from `IndustryPlaybook.offer_weights`,
`weights_version`) so the owner sees *why* a pricier offer can still win. Price is normalized within
the set (cheapest = 1.0 on the price axis) but the recommendation is **value-based, not cheapest**.

**B. Pros / cons** per offer — short bulleted lists derived from the axis scores.

**C. Hidden risks** — `Comparison.hidden_risk_flags` (→ `RiskFlag`/`EvidenceReference`): missing
service, shorter warranty, exclusions, risky payment terms. Each with `<EvidenceChip>` pointing at
the exact clause in the source `Offer`'s `Document` (page+bbox). This is the "what the cheap quote
isn't telling you" section.

**D. Recommendation** — `Comparison.recommendation` in plain language + `<ConfidenceDot>`
(`Comparison.confidence`), phrased for the owner to relay to the client.

### Data shown
`Offer` (origin, price, currency, scope, deadline, warranty, payment_terms, exclusions,
hidden_costs, offer_score, status, version), `Comparison` (axis_scores, weights_version,
recommendation, hidden_risk_flags, confidence), `OfferScore`, `RiskFlag`, `EvidenceReference`.

### Primary actions
- Adopt the recommendation → draft a revised `Offer` (into `QUOTE_PREPARATION`) or a negotiation
  `Message`.
- Toggle/adjust weights for a what-if (recomputes `OfferScore`; writes a new `weights_version`
  scoped to the comparison — never silently mutates the playbook default).
- Open any offer's underlying `Document` (screen 3).
- Send the comparison summary to the client as a follow-up.

### States
- **Single offer:** show one column with axis scores and hidden risks; comparison recommendation
  reads *"Add a competitor quote to compare."*
- **Loading:** skeleton table; recommendation last to resolve.
- **Low confidence:** if any offer's source `Confidence < θ_conf`, banner *"Some figures are
  unverified — confirm before deciding"* and those cells muted.
- **Empty:** no offers on the case → CTA to prepare a quote.
- **Error:** table renders from cached `Offer` rows even if the `Comparison` recompute fails.

---

## 5. AI Control Center

### Purpose
Where the owner sets *how much they trust the worker* and reviews what it wants to do. Governs
autonomy, escalation, voice, business profile, and playbooks. This screen is the safety and
configuration hub (ties to `13-autonomy-and-safety.md`).

### Sections

**A. Actions waiting for approval (HumanApproval).** The same queue as the Command Center strip,
here in full: each `HumanApproval` with `context`, `options`, `recommended_option`, `deadline`,
`sla_breached`, the source `Action` and its `autonomy_level_used`, evidence, and Approve/Edit/Reject.
Bulk actions supported.

**B. Autonomy level settings (Levels 1–5).** Global default (`BusinessProfile.autonomy_defaults`,
per action type) plus per-`Case` override (`Case.autonomy_level`). A clear ladder:

| Level | Name | What the AI may do without asking |
|---|---|---|
| **1** | Observe | Read/listen/summarize only; zero outbound client-facing actions. |
| **2** | Prepare | Drafts messages, quotes, briefs for human review — human sends everything. (This is the cap enforced in `HUMAN_REVIEW_REQUIRED`.) |
| **3** | Communicate | Autonomous low-risk informational sends — reminders, confirmations, missing-info requests, receiving/placing AI voice calls — no approval; no prices, bookings, or discounts. |
| **4** | Execute Low Risk | Autonomous bookings plus rule-covered standard sends (quotes inside `price_rules`, below `high_value_threshold`); anything outside the rule box escalates. |
| **5** | Conditional Autopilot | Full workflow end-to-end while it stays in-rules; escalates on thresholds/hard overrides (drops to Level 2). |

Level names and semantics are canonical in `13-autonomy-and-safety.md` §1. **L5 is disabled
until post-MVP (`14` §1); the control renders but is locked.**

Per action type (call, WhatsApp/SMS/email, request-doc, prepare-quote, send-offer, schedule,
escalate) the owner sets the level. UI makes the trade-off explicit: higher autonomy = more
recovered revenue, fewer approvals, but more trust required.

**C. Escalation rules / thresholds.** Editors for the tenant thresholds in
`BusinessProfile.thresholds` / `IndustryPlaybook.escalation_rules`: `θ_qualify`, `θ_escalate`
(default 1.5, drives `EscalationScore` → `HUMAN_REVIEW_REQUIRED`), `θ_docrisk` (60), `θ_conf`
(0.6), `θ_mis` (0.25), `θ_stuck`, `θ_breach`, and `high_value_threshold`. Each shows plain-language
effect ("cases over €X always come to me") and the **hard overrides** that escalate regardless
(any legal-sensitivity on a signing decision, safety emergency) as non-editable, always-on rules.

**D. Voice settings (VoiceProfile).** `phone_numbers`, `tts_voice`, `stt_vendor`, `languages`,
`greeting_script`, `barge_in_enabled`, `max_latency_targets`, `handoff_rules`, `recording_enabled`
+ `consent_prompt`. Includes a *listen to sample* preview and the region call-recording-consent
config (`BusinessProfile.recording_consent_config`).

**E. Business profile (BusinessProfile).** `name`, `services`, `service_area`, `default_language`,
`timezone`, `quiet_hours`, `price_rules`, `high_value_threshold`, `data_region`, and connected
`IntegrationAccount`s (Calendar, Gmail/Outlook, WhatsApp Business, SMS, telephony, CRM, Drive) with
connection status — never secrets, only `status` and scopes.

**F. Playbook editor (IndustryPlaybook).** The vertical config: `vertical`, `intake_schema`,
`required_fields` (`{key, weight, blocks_quote}` — drives `MIS`), `scoring_weights` (LeadScore &
others), `offer_weights` (OfferScore axes), `followup_defaults` (cadence/quiet hours/max attempts),
`escalation_rules`, `templates`, `version`. Editing weights shows which scores it affects; changes
create a new `version` and are back-testable (shadow scoring per §13) before rollout.

### Primary actions
- Approve/reject queued `HumanApproval`s; set autonomy per action type + per case; edit thresholds;
  edit `VoiceProfile`; connect/disconnect integrations; edit and version a playbook; run a
  what-if / shadow back-test before applying weight changes.

### States
- **Loading:** section-by-section skeletons; the approval queue loads first (most time-sensitive).
- **Empty:** no pending approvals → *"Nothing needs you right now."* No integrations → onboarding
  checklist.
- **Error:** a config save failure is non-destructive (optimistic UI rolls back with an inline
  error); a threshold edit that would violate a hard override is rejected with an explanation.
- **Guardrail:** attempting to raise autonomy above what a threshold permits (e.g. Conditional
  Autopilot on legal docs) is blocked with a clear reason, not silently allowed.

---

## 6. Recommended Next.js / React implementation

This repo is a Next.js starter with no app code yet, so the recommendation is greenfield and
opinionated for an owner-first, mobile-friendly, evidence-heavy product.

**Framework & rendering**
- **App Router + React Server Components.** Dashboards are read-heavy and personalized — fetch
  `Case`/score projections on the server (RSC) for fast first paint and to keep tenant-filtered
  queries server-side (row-level security never leaks to the client). Interactive islands
  (`<ActionBar>`, approval buttons, weight sliders) are Client Components.
- **Route structure:**
  - `app/(dashboard)/page.tsx` — Case Command Center (screen 1)
  - `app/(dashboard)/cases/[caseId]/page.tsx` — Case Detail (screen 2)
  - `app/(dashboard)/documents/[documentId]/page.tsx` — Document Analysis (screen 3)
  - `app/(dashboard)/cases/[caseId]/offers/page.tsx` — Offer Comparison (screen 4)
  - `app/(dashboard)/control-center/*` — AI Control Center (screen 5)
- **Streaming with `<Suspense>`** per tile/panel so a slow query (e.g. `StuckScore` sweep) never
  blocks the hero — matches the per-tile loading states above.
- **Server Actions** for mutations (approve `HumanApproval`, send follow-up, set autonomy, verify a
  field). They keep the write path server-side, are trivially auditable (write an `AuditEvent`), and
  pair with optimistic UI via `useOptimistic`.

**Data & real-time**
- **TanStack Query** on the client for the interactive queues (approval queue, work tiles) with
  polling or a WebSocket/SSE channel so new inbound events and score recomputes appear live.
- **Zod** schemas mirroring the data-model entities as the single source of truth for both API
  boundaries and form validation (playbook/threshold editors).

**UI system**
- **Tailwind CSS + shadcn/ui (Radix primitives)** for accessible tables, dialogs, tabs, and the
  split-view document reader. Mobile-first utility classes; every `<table>` wrapped so it degrades
  to stacked cards below `md`.
- **Design-system components** implementing the cross-cutting rules once: `<ScoreBadge>`,
  `<EvidenceChip>` (opens an evidence popover/drawer), `<ConfidenceDot>`, `<StatusPill>`,
  `<AutonomyBadge>`, `<ActionBar>`, `<EmptyState>`, `<SkeletonRow>`, `<ErrorState>`. Centralizing
  these is what guarantees *"every AI claim shows its evidence/confidence"* holds across screens.
- **Document viewer:** render pages to canvas/SVG and overlay `bbox` highlight rectangles from
  `ExtractedField`/`EvidenceReference.locator` for the click-to-source behavior (screen 3).
- **Charts** (Revenue Recovery trend, pipeline) via a lightweight lib (e.g. Recharts) — see the
  `dataviz` guidance before building; keep them glanceable, not busy.

**Cross-cutting concerns**
- **Error boundaries** per panel/tile (React Error Boundary) so isolated failures match the "one
  tile fails, the rest live" state spec.
- **Auth/tenancy:** every server fetch carries `tenant_id`; never expose PII (`Party`) beyond what a
  card needs; respect `UserRole.permissions` for who can approve/change autonomy.
- **Accessibility & thumb-reach:** primary actions are ≥44px targets, color is never the only signal
  (bands and confidence also carry text/icon), and the whole app is keyboard- and screen-reader-
  navigable via Radix.

---

## 7. Screen → entity/score traceability

| Screen | Primary entities | Primary scores |
|---|---|---|
| 1 Command Center | `Case`, `Offer`, `MissingItem`, `Promise`, `Task`, `HumanApproval`, `DecisionBrief` | `LeadScore`, `StuckScore`, `PromiseBreachScore` |
| 2 Case Detail | `Case`, `AuditEvent` (timeline), `Message`, `Call`, `Document`, `Photo`, `Offer`, `MissingItem`, `Promise`, `RiskFlag`, `DecisionBrief`, `FollowUpSequence`, `Action`, `HumanApproval`, `EvidenceReference` | `LeadScore`, `Confidence`, NBA `Utility`, `StuckScore` |
| 3 Document Analysis | `Document`, `ExtractedField`, `RiskFlag`, `EvidenceReference` | `DocRisk`, `Confidence` |
| 4 Offer Comparison | `Offer`, `Comparison`, `RiskFlag`, `EvidenceReference` | `OfferScore`, `Confidence` |
| 5 AI Control Center | `HumanApproval`, `BusinessProfile`, `IndustryPlaybook`, `VoiceProfile`, `IntegrationAccount`, `Action` | `EscalationScore` + all thresholds (`θ_*`) |
