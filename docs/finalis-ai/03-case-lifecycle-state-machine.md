# Finalis AI — Case Lifecycle State Machine

> The Completion Loop Engine treats every case as a **durable, resumable process**, not a
> conversation. A case has exactly one lifecycle state at any time, a `next_action`, a
> `due_at`, and an `owner`. State transitions are the only way a case changes; every
> transition writes an `AuditEvent` (see `04-data-model.md`).

This document is the authoritative specification of case states. It is designed to be
implemented directly as a LangGraph graph or an OpenAI Agents SDK workflow backed by a
durable store (see `18-technology-stack.md`). States map 1:1 to the `Case.status` enum.

---

## 1. State set

```
NEW_CONTACT
INTAKE_IN_PROGRESS
QUALIFIED
WAITING_FOR_CLIENT_INFO
WAITING_FOR_DOCUMENTS
DOCUMENT_ANALYSIS
QUOTE_PREPARATION
OFFER_SENT
FOLLOW_UP_ACTIVE
NEGOTIATION
HUMAN_REVIEW_REQUIRED
SCHEDULED
WON            (terminal-ish; can reopen to RECOVERY_LATER for upsell)
LOST           (terminal-ish; can reopen to RECOVERY_LATER)
COMPLETED      (terminal)
ABANDONED      (terminal)
RECOVERY_LATER (parked; wakes back to FOLLOW_UP_ACTIVE)
```

**Terminal states**: `COMPLETED`, `ABANDONED`. **Closed but reopenable**: `WON`, `LOST`.
**Parked**: `RECOVERY_LATER`. All other states are *active* and must always carry a
non-null `next_action` and `due_at`; a scheduler invariant check (the "stuck sweep",
see `09-completion-loop-followup-promises.md`) fails loudly if an active case has no future action.

---

## 2. Global invariants (enforced on every transition)

1. An **active** case MUST have `next_best_action != null` and `next_action_due_at != null` (referred to as `due_at` in shorthand throughout).
2. Any transition into `HUMAN_REVIEW_REQUIRED` freezes all outbound autonomous actions
   (autonomy is capped at Level 2 "Prepare" — see `13-autonomy-and-safety.md`).
3. A transition may only be executed by an actor allowed at the case's current autonomy
   level; otherwise the transition is queued as a `HumanApproval`.
4. Every transition writes `AuditEvent{from_state, to_state, actor, reason, evidence_refs}`.
5. `EscalationScore` is recomputed on every inbound event; crossing `θ_escalate` forces a
   transition to `HUMAN_REVIEW_REQUIRED` from any active state (a global "interrupt edge").
   (MVP note: until the full EscalationScore model ships (Phase 3, task S-ESC), this
   interrupt runs on the hard-override rules only — see 13 §2.)
6. A hard client opt-out (STOP/"don't contact me") forces `ABANDONED` (or `LOST` if a
   reason is captured) and suppresses all future outbound actions permanently.

---

## 3. Per-state specification

Legend for each state: **Entry** (how you get here) · **Required data** · **Allowed AI
actions** · **Prohibited AI actions** · **Next states** · **Escalation triggers** ·
**Follow-up timing** · **Metrics**.

### 3.1 `NEW_CONTACT`
- **Entry**: inbound call/WhatsApp/SMS/email/web-form/web-chat with no matching open case,
  OR a manually created case.
- **Required data**: at minimum a channel identity (phone/email/handle) and a raw first
  message or call recording.
- **Allowed AI actions**: greet, identify returning client via `Deal Memory`,
  create `Case`, classify intent, detect language, start `Conversation`.
- **Prohibited**: quoting a price, promising an appointment slot, making commitments.
- **Next states**: `INTAKE_IN_PROGRESS` (default), `HUMAN_REVIEW_REQUIRED` (angry/legal),
  `ABANDONED` (spam/wrong number), `SCHEDULED` (returning client asks to rebook a known job).
- **Escalation triggers**: legal threat, safety emergency (e.g. gas leak → give safety
  script + hand off/emergency route), abusive caller.
- **Follow-up timing**: n/a (synchronous). If contact drops before intake, immediate
  callback attempt policy is defined in `WAITING_FOR_CLIENT_INFO`.
- **Metrics**: answer rate, time-to-answer, intent-classification accuracy, dedup accuracy.

Note: *answering an inbound contact* (greeting, capturing the request) is a distinct action class: at autonomy L1–L2 the AI only captures a message/voicemail and notifies a human; conversational answering requires L3+ (see 13 §1). The MVP default for the inbound-answer action type is therefore L3.

### 3.2 `INTAKE_IN_PROGRESS`
- **Entry**: from `NEW_CONTACT` once intent is a serviceable request.
- **Required data**: industry playbook selected (see `IndustryPlaybook`); intake checklist
  instantiated as `MissingItem` rows.
- **Allowed AI actions**: ask the industry intake questions (name, address, problem type,
  urgency, scope, timing, budget band, "do you already have another quote?"), request
  photos/documents, confirm contact preferences, compute initial `LeadScore` and `MIS`.
- **Prohibited**: final pricing; assuming unstated facts; over-asking (respect
  `AnnoyanceRisk`).
- **Next states**: `QUALIFIED`, `WAITING_FOR_CLIENT_INFO`, `WAITING_FOR_DOCUMENTS`,
  `HUMAN_REVIEW_REQUIRED`, `ABANDONED`.
- **Escalation triggers**: out-of-scope job, high `EscalationScore`, `LegalSensitivity`.
- **Follow-up timing**: if the client goes silent mid-intake → retry per `FollowUpPriority`
  (typically +2h same channel, then +24h alternate channel).
- **Metrics**: intake completion rate, fields captured per contact, drop-off point.

### 3.3 `QUALIFIED`
- **Entry**: `LeadScore ≥ θ_qualify` AND core required fields present AND fit-to-services
  `C > 0`.
- **Required data**: address/service area, job type, urgency, rough scope, decision-maker
  signal.
- **Allowed AI actions**: route to the correct downstream state, book a survey/visit if the
  playbook allows (L4), prepare a `DecisionBrief` stub for the owner.
- **Prohibited**: skipping required blocking `MissingItem`s.
- **Next states**: `WAITING_FOR_DOCUMENTS`, `WAITING_FOR_CLIENT_INFO`, `QUOTE_PREPARATION`,
  `SCHEDULED`, `HUMAN_REVIEW_REQUIRED`.
- **Escalation triggers**: value above owner-configured `high_value_threshold`.
- **Follow-up timing**: immediate progression; no dwell.
- **Metrics**: qualification precision/recall vs. human labels, false-qualify rate.

### 3.4 `WAITING_FOR_CLIENT_INFO`
- **Entry**: a non-document `MissingItem` blocks progress (dimensions, preferred time,
  budget, decision confirmation).
- **Required data**: the specific blocking `MissingItem`(s) with weights `w_i`.
- **Allowed AI actions**: send *one* targeted request via best channel; set a `Promise`
  ("client will send X"); schedule a follow-up.
- **Prohibited**: repeated pinging inside the AnnoyanceRisk cool-down; guessing the missing
  value.
- **Next states**: back to `INTAKE_IN_PROGRESS`/`QUALIFIED` when info arrives,
  `WAITING_FOR_DOCUMENTS`, `RECOVERY_LATER` (silent), `ABANDONED`.
- **Escalation triggers**: `StuckScore` high on a high-value case.
- **Follow-up timing**: cadence `+24h → +48h → +72h` (configurable), max N attempts before
  `RECOVERY_LATER`.
- **Metrics**: missing-info recovery rate, avg attempts to recover, days-to-unblock.

### 3.5 `WAITING_FOR_DOCUMENTS`
- **Entry**: a document/photo `MissingItem` blocks a quote or analysis (nameplate photo,
  VIN, floor plan, previous offer, invoice, contract, ID).
- **Required data**: list of required document types + acceptance criteria (min resolution,
  which pages).
- **Allowed AI actions**: request upload with an example ("photo of the boiler label like
  this"), accept via WhatsApp/email/upload link, run a *quality pre-check* on arrival.
- **Prohibited**: proceeding to analysis if the document quality check fails silently — must
  ask for a clearer scan (see `Evidence Confidence`, `07-document-intelligence.md`).
- **Next states**: `DOCUMENT_ANALYSIS` (docs received & pass quality gate), same as 3.4 for
  silence.
- **Escalation triggers**: repeated unreadable uploads; sensitive document types (notarial,
  legal) → prepare for human review.
- **Follow-up timing**: same cadence as 3.4.
- **Metrics**: document acquisition rate, re-scan request rate, upload-to-usable ratio.

### 3.6 `DOCUMENT_ANALYSIS`
- **Entry**: at least one usable document/photo present that the case needs analyzed.
- **Required data**: documents with OCR text, extracted fields, `Confidence`.
- **Allowed AI actions**: run Document Intelligence Worker → extract fields with evidence
  refs, compute `DocRisk`, compare to prior agreements/other offers, produce human-language
  summary + questions.
- **Prohibited**: asserting facts below the confidence floor; giving final legal advice;
  hiding low confidence.
- **Next states**: `QUOTE_PREPARATION`, `NEGOTIATION` (if analyzing a competitor offer for a
  live deal), `HUMAN_REVIEW_REQUIRED` (`DocRisk ≥ θ_docrisk` or legal doc),
  `WAITING_FOR_DOCUMENTS` (need clearer/more docs).
- **Escalation triggers**: high `DocRisk`, contradictions vs. prior agreement, legal/notarial
  content.
- **Follow-up timing**: internal (no client wait) unless clearer docs needed.
- **Metrics**: field-extraction F1, contradiction detection precision, human-override rate.

### 3.7 `QUOTE_PREPARATION`
- **Entry**: enough info + docs to draft a quote per the playbook's pricing rules.
- **Required data**: scope, quantities/dimensions, price rules or a human price input,
  `MIS` below the quote-blocking threshold.
- **Allowed AI actions**: build a *draft* quote (base + premium variants), list assumptions,
  list remaining blockers, prepare sales arguments; request approval if pricing uncertainty
  is high (L2/L3).
- **Prohibited**: finalizing/sending a binding price without business rules coverage or
  human approval when uncertainty is high.
- **Next states**: `OFFER_SENT` (approved/auto per autonomy), `HUMAN_REVIEW_REQUIRED`,
  `WAITING_FOR_CLIENT_INFO` (missing a pricing input).
- **Escalation triggers**: price outside rule bounds; margin below floor; unusual scope.
- **Follow-up timing**: internal; owner approval SLA tracked as a `Task`.
- **Metrics**: draft-to-approved edit distance, quote turnaround time, price-rule coverage.

### 3.8 `OFFER_SENT`
- **Entry**: a quote/offer has been delivered to the client.
- **Required data**: `Offer` record with sent timestamp, channel, and content snapshot.
- **Allowed AI actions**: confirm receipt, answer clarifying questions, start the follow-up
  sequence, watch for a competitor offer to compare.
- **Prohibited**: discounting without authority; pressuring; contacting outside allowed
  hours.
- **Next states**: `FOLLOW_UP_ACTIVE` (default after no immediate reply), `NEGOTIATION`,
  `WON`, `LOST`, `SCHEDULED`.
- **Escalation triggers**: client raises a legal/contractual objection; large discount ask.
- **Follow-up timing**: `+24h` gentle check → `+72h` value reminder → `+7d` last-chance →
  `RECOVERY_LATER`. Timing/channel chosen by `FollowUpPriority`.
- **Metrics**: offer response rate, time-to-first-response, win rate by follow-up step.

### 3.9 `FOLLOW_UP_ACTIVE`
- **Entry**: any active case awaiting a client response (post-offer or post-info-request)
  where the completion loop is driving cadence.
- **Required data**: `FollowUpSequence` with steps, channels, quiet hours, opt-out state.
- **Allowed AI actions**: send the next best follow-up (channel + timing from
  `FollowUpPriority`), detect and route objections, re-open dialogue.
- **Prohibited**: exceeding max attempts, ignoring quiet hours or channel preference,
  spamming (AnnoyanceRisk gate).
- **Next states**: `NEGOTIATION`, `WON`, `LOST`, `OFFER_SENT` (revised offer),
  `SCHEDULED`, `RECOVERY_LATER`, `HUMAN_REVIEW_REQUIRED`.
- **Escalation triggers**: repeated objections, emotional signals, high-value stall.
- **Follow-up timing**: driven by `FollowUpPriority`; hard cap on frequency & count.
- **Metrics**: follow-up success rate, reply-per-attempt, opt-out rate, recovered leads.

### 3.10 `NEGOTIATION`
- **Entry**: client is engaging on price/scope/terms or has produced a competitor offer.
- **Required data**: objection type(s), competitor `Offer` (if any) with `OfferScore`, our
  authority bounds.
- **Allowed AI actions**: run Objection Handler, prepare recommended responses within
  authorized discount/scope bounds, produce a `DecisionBrief` for the owner.
- **Prohibited**: agreeing to terms beyond authority; conceding warranty/legal terms without
  human sign-off.
- **Next states**: `WON`, `LOST`, `OFFER_SENT` (revised), `HUMAN_REVIEW_REQUIRED`,
  `FOLLOW_UP_ACTIVE`.
- **Escalation triggers**: discount beyond bound, contract redlines, partner/legal approval
  needed.
- **Follow-up timing**: tight cadence (hours–1 day) while momentum is high.
- **Metrics**: negotiation win rate, discount given vs. authorized, escalation precision.

### 3.11 `HUMAN_REVIEW_REQUIRED`
- **Entry**: `EscalationScore ≥ θ_escalate`, or any hard rule (legal, high value, low
  confidence, emotion, unusual request).
- **Required data**: a `HumanApproval` request with context, options, recommendation,
  evidence refs, and a deadline.
- **Allowed AI actions**: **Level ≤ 2 only** — prepare, summarize, draft; NO outbound
  client actions. Notify the assigned human; keep the case warm internally.
- **Prohibited**: any autonomous client-facing action, any state transition to a
  client-visible state without human decision.
- **Next states**: any active state (per human decision), `WON`/`LOST`/`ABANDONED`.
- **Escalation triggers**: n/a (already escalated); may re-route to a different human/role.
- **Follow-up timing**: internal SLA on the human (e.g. remind owner at +2h, +1d).
- **Metrics**: time-in-human-review, approval rate, decision reversal rate, SLA breach rate.

### 3.12 `SCHEDULED`
- **Entry**: an appointment/visit/service date is booked (survey, install, service call).
- **Required data**: calendar event, address, assigned technician/resource, confirmation.
- **Allowed AI actions**: send confirmations + reminders, handle reschedule requests,
  pre-collect anything needed before the visit.
- **Prohibited**: double-booking, moving appointments without confirmation.
- **Next states**: `COMPLETED`, `WON` (if scheduling *is* the win), `DOCUMENT_ANALYSIS`
  (post-visit report), `FOLLOW_UP_ACTIVE`, `LOST` (cancelled).
- **Escalation triggers**: repeated cancellations, no-show risk on high-value job.
- **Follow-up timing**: reminder `-24h` and `-2h`; post-visit follow-up `+1d`.
- **Metrics**: show rate, reschedule rate, on-time confirmation rate.

### 3.13 `WON`
- **Entry**: offer accepted / job booked-and-committed / contract signed (per playbook
  definition of "won").
- **Required data**: accepted `Offer`, value, agreed terms, next operational step.
- **Allowed AI actions**: send confirmation & onboarding info, create the delivery/service
  `Task`s, optionally schedule an upsell/recovery reminder.
- **Prohibited**: further sales pressure.
- **Next states**: `SCHEDULED`, `COMPLETED`, `RECOVERY_LATER` (future upsell/renewal).
- **Escalation triggers**: none by default.
- **Follow-up timing**: operational reminders only.
- **Metrics**: win rate, realized value vs. estimate, AI **close-assist rate**.

### 3.14 `LOST`
- **Entry**: client declined / chose a competitor / job cancelled.
- **Required data**: **loss reason** (required — captured for learning), competitor if known.
- **Allowed AI actions**: polite close, ask (once) for the reason, schedule
  `RECOVERY_LATER` if appropriate (seasonal, "maybe next year").
- **Prohibited**: repeated re-pitching after a clear no.
- **Next states**: `RECOVERY_LATER`, `ABANDONED` (hard no / opt-out).
- **Escalation triggers**: high-value loss (owner notification, not a block).
- **Follow-up timing**: none immediately; recovery handled by `RECOVERY_LATER`.
- **Metrics**: loss reasons distribution, competitor-loss share, recovery conversion.

### 3.15 `COMPLETED`
- **Entry**: service delivered / job finished / final decision executed. **Terminal.**
- **Required data**: completion confirmation, optional review/NPS request.
- **Allowed AI actions**: request feedback/review, schedule maintenance/renewal reminder as
  a *new* `RECOVERY_LATER`-linked case.
- **Prohibited**: reopening the same case for new work (spawn a linked new case instead).
- **Next states**: none (terminal). May *spawn* a new linked case.
- **Metrics**: completion rate, review capture rate, repeat-business rate.

### 3.16 `ABANDONED`
- **Entry**: spam, wrong number, hard opt-out, or exhausted all contact attempts with no
  engagement. **Terminal.**
- **Required data**: abandonment reason.
- **Allowed AI actions**: none outbound; archive.
- **Prohibited**: any further contact (especially after opt-out).
- **Next states**: none (terminal).
- **Metrics**: abandonment rate, false-abandon audit (were they recoverable?).

### 3.17 `RECOVERY_LATER`
- **Entry**: parked lead with future potential (silent lead, seasonal, lost-but-warm, won-
  with-upsell).
- **Required data**: a `wake_at` timestamp and a recovery reason/trigger.
- **Allowed AI actions**: none until `wake_at`; then re-enter `FOLLOW_UP_ACTIVE` with a
  fresh, context-aware opener.
- **Prohibited**: contacting before `wake_at`; ignoring opt-out.
- **Next states**: `FOLLOW_UP_ACTIVE` (on wake).
- **Follow-up timing**: single scheduled wake; re-evaluated by `FollowUpPriority` at wake.
- **Metrics**: recovery wake→reply rate, recovered pipeline value.

---

## 4. Transition table (summary)

| From | Allowed To |
|---|---|
| NEW_CONTACT | INTAKE_IN_PROGRESS, SCHEDULED, HUMAN_REVIEW_REQUIRED, ABANDONED |
| INTAKE_IN_PROGRESS | QUALIFIED, WAITING_FOR_CLIENT_INFO, WAITING_FOR_DOCUMENTS, HUMAN_REVIEW_REQUIRED, ABANDONED |
| QUALIFIED | WAITING_FOR_DOCUMENTS, WAITING_FOR_CLIENT_INFO, QUOTE_PREPARATION, SCHEDULED, HUMAN_REVIEW_REQUIRED |
| WAITING_FOR_CLIENT_INFO | INTAKE_IN_PROGRESS, QUALIFIED, WAITING_FOR_DOCUMENTS, RECOVERY_LATER, ABANDONED, HUMAN_REVIEW_REQUIRED |
| WAITING_FOR_DOCUMENTS | DOCUMENT_ANALYSIS, RECOVERY_LATER, ABANDONED, HUMAN_REVIEW_REQUIRED |
| DOCUMENT_ANALYSIS | QUOTE_PREPARATION, NEGOTIATION, WAITING_FOR_DOCUMENTS, HUMAN_REVIEW_REQUIRED |
| QUOTE_PREPARATION | OFFER_SENT, WAITING_FOR_CLIENT_INFO, HUMAN_REVIEW_REQUIRED |
| OFFER_SENT | FOLLOW_UP_ACTIVE, NEGOTIATION, WON, LOST, SCHEDULED |
| FOLLOW_UP_ACTIVE | NEGOTIATION, OFFER_SENT, WON, LOST, SCHEDULED, RECOVERY_LATER, HUMAN_REVIEW_REQUIRED |
| NEGOTIATION | WON, LOST, OFFER_SENT, FOLLOW_UP_ACTIVE, HUMAN_REVIEW_REQUIRED |
| HUMAN_REVIEW_REQUIRED | * (any active state), WON, LOST, ABANDONED |
| SCHEDULED | COMPLETED, WON, DOCUMENT_ANALYSIS, FOLLOW_UP_ACTIVE, LOST |
| WON | SCHEDULED, COMPLETED, RECOVERY_LATER |
| LOST | RECOVERY_LATER, ABANDONED |
| RECOVERY_LATER | FOLLOW_UP_ACTIVE |
| COMPLETED | — (terminal; may spawn linked case) |
| ABANDONED | — (terminal) |

Plus the **global interrupt edge**: any active state → `HUMAN_REVIEW_REQUIRED` when
`EscalationScore ≥ θ_escalate` or a hard rule fires.

Global closure edge: any non-terminal state → ABANDONED (or LOST if a reason is captured) on hard client opt-out (STOP) or on follow-up exhaustion where recovery is inappropriate. This edge is always legal and overrides the per-state transition table.

---

## 5. Implementation notes

- Model this as an explicit state machine persisted per case; drive it with a durable
  orchestrator (LangGraph checkpointing or OpenAI Agents SDK sessions + a Temporal/durable
  queue). See `18-technology-stack.md` for the trade-off and `02-multi-agent-architecture.md` for how workers
  attach to states.
- The **daily stuck sweep** iterates all active cases, recomputes `LeadScore`, `MIS`,
  `StuckScore`, `EscalationScore`, `PromiseBreachScore`, and `FollowUpPriority`, and enqueues the next action. This is the
  heartbeat that makes "the system never stops after one conversation" literally true.
- Thresholds (`θ_qualify`, `θ_escalate`, `θ_docrisk`, high-value, quiet hours, max attempts)
  live in `BusinessProfile`/`IndustryPlaybook` so each tenant tunes behavior without code
  changes.
