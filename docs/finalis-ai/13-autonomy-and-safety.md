# Finalis AI — Autonomy & Safety

> Core stance (inherited from `02-multi-agent-architecture.md`): Finalis is **a supervised
> team of narrow workers over a durable case process**, not one open-ended agent. This
> document specifies *how much* the system is allowed to do on its own, *when* it must stop
> and ask a human, and *what* guardrails keep it honest. Autonomy is a **graded, per-tenant,
> per-action-type** setting — never a global on/off.

The design is a direct response to the evidence that general autonomy is still unreliable on
long, realistic business tasks:

- **TheAgentCompany (arXiv:2412.14161)**: best agent completed **~24% of consequential tasks
  fully autonomously** (~30–34% with partial credit). https://arxiv.org/abs/2412.14161
- **OSWorld (arXiv:2404.07972)**: on 369 real computer tasks, **humans ≈72.4%** vs. **best
  model ≈12.2%** at publication (SOTA has since risen; treat later numbers as UNVERIFIED).
  https://arxiv.org/abs/2404.07972

Takeaway baked into every level below: **do not sell "AI does the whole job unattended."**
The default posture is low autonomy that a tenant *earns up* per action type as their audit
history shows reliability.

---

## 1. The five autonomy levels

`Case.autonomy_level (1–5)` (see `04-data-model.md`) is the ceiling on what the Orchestrator
may execute without a `HumanApproval`. The **effective** ceiling for a given step is:

```
effective_level = min(
    Case.autonomy_level,                                  # per-case ceiling
    BusinessProfile.autonomy_defaults[action_type],       # per-tenant, per-action-type
    state_cap                                             # e.g. HUMAN_REVIEW_REQUIRED → 2
)
```

So a tenant can run **doc-requests at Level 4** while keeping **quotes at Level 2** and
**calls at Level 3**, all in the same case. `autonomy_defaults` is a JSON map keyed by
`Action.type` on `BusinessProfile`; the per-case `autonomy_level` can only ever *lower* the
effective ceiling below the tenant default, never raise it.

Levels are **cumulative** — Level *n* includes everything permitted at *n−1*.

### Level 1 — Observe

- **Allowed actions**: read-only. Ingest inbound calls/messages/docs, classify intent,
  detect language, compute all scores (`LeadScore`, `MIS`, `EscalationScore`, `DocRisk`,
  `Confidence`, etc.), build the Case Graph, surface `Task`s and `DecisionBrief`s to the
  Command Center. **Zero outbound client-facing `Action`s.**
- **Action types permitted**: none of {call, WhatsApp, SMS, email, doc-request, booking,
  quote-send}. All are proposal-only.
- **Approval**: every outbound step becomes a `HumanApproval` (or a `Task`). The human does
  the talking; the AI only recommends.
- **Risk controls**: nothing the client sees is machine-authored. Maximum safety, minimum
  leverage.
- **Audit**: full — scores + input vectors + weight-version to `AuditEvent`; every proposal
  logged even if never sent.
- **Home-services example**: A plumber's new tenant in week 1. Finalis transcribes the "burst
  pipe" call, scores it Hot, drafts "call back today, quote survey visit", and drops a `Task`
  in the plumber's queue. The plumber makes every call.

### Level 2 — Prepare

- **Allowed actions**: everything in L1 **plus** drafting *outbound content* held for human
  send: draft WhatsApp/SMS/email replies, draft `Offer`s (via Quote Builder), draft
  `MissingItem` requests, draft `DecisionBrief`s with a recommended next step. Nothing is
  transmitted.
- **Action types permitted**: draft-only for {WhatsApp, SMS, email, doc-request, quote}. No
  {call, booking} execution.
- **Approval**: a human presses "send" on each drafted `Action`; the approval writes
  `Action.approved_by`.
- **Risk controls**: the human is the transmit gate. This is the **cap imposed by
  `HUMAN_REVIEW_REQUIRED`** (see §2) regardless of the case's configured level.
- **Audit**: draft content + the recommendation + evidence refs; the human's edit distance
  from the draft is logged (feeds `15-evaluation-lab.md`).
- **Home-services example**: An HVAC lead needs a nameplate photo. Finalis writes "Could you
  send a photo of the boiler label, like this?" with an example image; the owner reviews the
  wording and taps send.

### Level 3 — Communicate

- **Allowed actions**: L2 **plus autonomous *non-committal* outbound communication** —
  actually sending informational messages, follow-ups, `MissingItem` requests, receipt
  confirmations, and answering clarifying questions. May place/receive **AI voice calls**
  (Voice Worker) for intake and follow-up. **No commercial commitment**: no prices, no booked
  slots, no discounts.
- **Action types permitted (autonomous)**: {WhatsApp, SMS, email, doc-request, informational
  call}. **Gated**: {quote-send, booking, discount} → `HumanApproval`.
- **Approval**: none for the permitted set (subject to all §3 guardrails and the
  `FollowUpPriority`/`AnnoyanceRisk` anti-spam gates from `05-algorithms-and-scoring.md`);
  approval still required for anything that commits money or calendar.
- **Risk controls**: hard guarantees from `05` §4 always hold — quiet hours, min inter-touch
  interval, `max_attempts`, channel opt-outs, global STOP. Every outbound message passes the
  output validators (§3).
- **Audit**: each sent `Action` with `autonomy_level_used=3`, `utility_score`, chosen-over
  runner-ups, and the generated `Message`/`Call`.
- **Home-services example**: A renovation lead goes quiet after intake. Finalis runs the
  `WAITING_FOR_CLIENT_INFO` cadence (+24h → +48h → +72h) on WhatsApp, asks for the missing
  room dimensions, and confirms receipt — all without the owner, but it will **not** send the
  quote or book the survey.

### Level 4 — Execute Low Risk

- **Allowed actions**: L3 **plus executing bounded, reversible, low-value commitments**:
  **booking/rescheduling** survey or service appointments within available calendar slots
  (`SCHEDULED`), and **sending quotes that fall fully inside `BusinessProfile.price_rules`**
  and below `high_value_threshold`. "Low risk" = rule-covered, reversible, sub-threshold, and
  `Confidence ≥ θ_conf`.
- **Action types permitted (autonomous)**: {call, WhatsApp, SMS, email, doc-request,
  **booking**, **rule-covered quote-send**}. **Still gated**: quotes outside price-rule
  bounds, above `high_value_threshold`, any discount beyond authorized bounds, contract/legal
  terms.
- **Approval**: none for the low-risk set; automatic escalation to `HumanApproval` the moment
  a step leaves the rule box (price outside bounds, margin below floor, unusual scope — the
  same triggers `QUOTE_PREPARATION`/`NEGOTIATION` name in `03`).
- **Risk controls**: price-rule validator (§3) must pass; `high_value_threshold` check;
  no double-booking invariant; every commitment reversible/cancellable and re-confirmed with
  the client.
- **Audit**: `Action` records the rule set and bounds it satisfied; booking writes the
  calendar event id; quote sends snapshot the `Offer` content and the price-rule version.
- **Home-services example**: A boiler service is €180, squarely inside the price table.
  Finalis sends the fixed-price quote, and when the client accepts, books the next open
  Tuesday slot and sends confirmation + reminders — no human touch. A €14k full-system
  replacement (near `high_value_threshold`) is instead escalated.

### Level 5 — Conditional Autopilot

- **Allowed actions**: L4 **plus running the full completion loop end-to-end for cases that
  stay inside all guardrails** — intake → info/doc collection → rule-covered quote → follow-up
  → booking → close — with the human notified rather than asked. **"Conditional"** is literal:
  the moment *any* hard rule or `EscalationScore ≥ θ_escalate` fires, the case drops to
  Level 2 automatically.
- **Action types permitted (autonomous)**: all of the L4 set, chained without per-step
  approval, for standard, sub-threshold, high-confidence cases.
- **Approval**: none while conditions hold; **any** hard-override rule (§2) instantly caps the
  case at Level 2 and opens a `HumanApproval`. Autopilot never applies to legal/notarial
  signing, high value, low confidence, client emotion, or unusual requests.
- **Risk controls**: this is the *most constrained* level in terms of preconditions, not the
  least. It requires: action-type default of 5 for every step involved, `Confidence ≥ θ_conf`
  throughout, full price-rule coverage, value < `high_value_threshold`, no open `RiskFlag`
  with `requires_human=true`, and a clean recent audit history. Given the benchmark reality
  (~24% / ~12% autonomous success), Level 5 is offered **only for narrow, well-trodden case
  types** and is off by default; tenants opt in per action type after reviewing outcomes.
- **Audit**: identical granularity to lower levels — autopilot does not reduce logging. Each
  chained `Action`, score, and transition is still an `AuditEvent`; the *notify* to the owner
  is itself logged.
- **Home-services example**: A repeat HVAC customer's annual maintenance renewal. Known party,
  known job, fixed price, calendar open. Finalis reminds them, quotes the standard renewal,
  books it, confirms, and closes `WON` → `SCHEDULED`, posting a summary to the owner. If the
  customer replies "actually the boiler's making a banging noise now" (unusual request), the
  case drops to Level 2 and asks the owner.

### 1.1 Setting autonomy per tenant

- `BusinessProfile.autonomy_defaults` (jsonb, per action type) is the tenant's dial, editable
  in the Command Center by an `owner`/`manager` `UserRole`.
- Recommended onboarding path: start every action type at **L1–L2**, raise **doc-requests and
  informational follow-ups** to L3 first (lowest blast radius), then **rule-covered quotes and
  bookings** to L4 once the tenant has reviewed a batch of them, and reserve **L5** for a
  hand-picked, high-confidence case type.
- Any change to `autonomy_defaults` or a case's `autonomy_level` is itself an `AuditEvent`
  (`event_type=autonomy_changed`) with actor, old/new values, and reason (see §5).

---

## 2. Escalation to a human

Escalation is governed by the **`EscalationScore`** model from `05-algorithms-and-scoring.md`
§8 — an *additive severity accumulator*, not a weighted mean:

```
EscalationScore = Risk + ValueCriticality + LowConfidence + ClientEmotion
                  + LegalSensitivity + UnusualRequest              (each term ∈ [0,1])
```

Recomputed on **every inbound event** (state-machine invariant, `03` §2). Crossing
`θ_escalate` (default **1.5**) fires the **global interrupt edge**: any active state →
`HUMAN_REVIEW_REQUIRED`.

### 2.1 Hard-override rules (escalate regardless of the sum)

These bypass the threshold entirely — a single one forces `HUMAN_REVIEW_REQUIRED` even if the
accumulated score is low:

| Override | Trigger | Mapped term |
|---|---|---|
| **Legal / notarial signing** | any signing decision, contract redline, notarial content, `DocRisk ≥ θ_docrisk` "requires human before signing" | `LegalSensitivity = 1` |
| **Safety emergency** | gas leak, fire, flooding, electrical hazard, injury risk | `Risk = 1` (give safety script + emergency route, `03` §3.1) |
| **High value** | `value ≥ high_value_threshold` | `ValueCriticality = 1` |
| **Low confidence** | deciding fact `Confidence < θ_conf` | `LowConfidence = 1 − Confidence` |
| **Client emotion** | anger/distress detected in voice or text | `ClientEmotion` high |
| **Unusual request** | out-of-distribution vs. the `IndustryPlaybook` | `UnusualRequest` high |

### 2.2 The `HUMAN_REVIEW_REQUIRED` cap

Entering `HUMAN_REVIEW_REQUIRED` (`03` §3.11) **freezes all outbound autonomous actions and
caps effective autonomy at Level 2** ("Prepare") — the AI may summarize, draft, and recommend,
but **no client-facing action and no client-visible transition** happens without a human
decision. This cap is enforced as `state_cap = 2` in the `effective_level` formula (§1).

### 2.3 The HumanApproval flow

```
   trigger (θ_escalate crossed | hard override | action above effective_level)
        │
        ▼
   Orchestrator creates HumanApproval  ──────────────────────────────────────┐
        │  context (jsonb):      case summary, current state, scores          │
        │  options (jsonb):      candidate actions with Utility scores        │
        │  recommended_option:   the NBA a* (05 §3), plainly justified        │
        │  evidence_ref_ids:     every claim linked (message/call/doc/web)    │
        │  deadline:             SLA; sla_breached flips if missed            │
        ▼                                                                     │
   Human (UserRole) reviews in Command Center ── decides ────────────────────┘
        │  decided_by, decision, decided_at written to HumanApproval
        ▼
   Orchestrator applies the chosen transition/Action under normal autonomy rules
        │  Action.approved_by set; overrides logged as labeled training data (05 §13)
        ▼
   AuditEvent{event_type, from_state, to_state, actor=human, payload, evidence_ref_ids}
```

Every field above maps 1:1 to the `HumanApproval` entity in `04-data-model.md`
(`context`, `options`, `recommended_option`, `decided_by`, `decision`, `decided_at`,
`deadline`, `sla_breached`). The linked `Action` carries `approved_by`. A human override of a
score-driven recommendation is logged as a labeled example (`05` §13) — overrides are training
data, not failures.

---

## 3. Guardrails (parallel validators)

Following the Agents-SDK pattern cited in `02` — "run input validation and safety checks in
parallel… fail fast" — **input and output validators run alongside every worker turn**, not
inline after it. A validator can **fail-fast a proposal** before it becomes an `Action`.

| Validator | Runs on | Checks | On failure |
|---|---|---|---|
| **PII validator** | in + out | detects/handles PII; blocks PII leaking cross-party or into logs; enforces access logging | redact / block / route to human |
| **Scope validator** | in + out | is this within `BusinessProfile.services` + the case's authority bounds? (excessive-agency guard) | escalate; `UnusualRequest` ↑ |
| **Price-rule validator** | out | is the quote inside `price_rules` + below `high_value_threshold`? | drop below L4; `HumanApproval` |
| **Prompt-injection filter** | in (esp. WebScout web content, inbound docs) | strip/neutralize instructions embedded in fetched pages, emails, or documents | quarantine content; lower `Source_q` |

### 3.1 Standards alignment

**OWASP Top 10 for LLM Applications (2025)** —
https://owasp.org/www-project-top-10-for-large-language-model-applications/ :

- **LLM01 Prompt Injection (ranked #1)** — the prompt-injection filter above targets this
  directly. WebScout web content and inbound documents are treated as **untrusted data, never
  instructions**; `08-webscout-web-research.md` uses structured accessibility-tree browsing
  (not open pixel GUI agents) partly to reduce this surface.
- **LLM06 Excessive Agency** — the entire autonomy-level system + the scope validator exist to
  bound agency: least-privilege MCP scopes (`04` `IntegrationAccount`), per-action-type
  ceilings, and human approval for anything committing money, calendar, or legal terms.

**OWASP Top 10 for Agentic Applications** — published **Dec 9 2025**, items **ASI01–ASI10** —
https://genai.owasp.org/ . This spec's controls (bounded autonomy, human-in-the-loop
interrupts, tamper-evident audit, secondary-critic verification, untrusted-content handling)
are intended to map onto the agentic Top 10. **The specific ASI01–ASI10 ordering and titles
are TO BE CONFIRMED against the final published PDF** — do not cite exact item numbers until
verified.

### 3.2 Why guardrails, not trust

The benchmark evidence (§ intro; `02` §0) is the justification: with fully-autonomous task
completion around **24%** (TheAgentCompany) and computer-use around **12%** (OSWorld) vs.
**~72%** human, unguarded autonomy would be wrong most of the time on realistic long tasks.
Guardrails + human review convert "usually wrong alone" into "reliable under supervision."

---

## 4. Anti-hallucination controls

1. **Confidence abstention rule** (`05` §6). `Confidence = OCR_q · Extraction_q · Source_q ·
   Consistency_q`. If `Confidence < θ_conf` (default **0.6**) the system **MUST NOT assert the
   fact as certain** — it surfaces it as *unverified*, asks for a clearer scan (documents) or a
   second source (web), and cannot use that fact to trigger an autonomous client-facing action.
   A low-confidence input also raises `LowConfidence` in `EscalationScore` (§2).
2. **Evidence-linking requirement**. Every AI assertion carries an `EvidenceReference` to a
   `Message`, `Call` segment, `document_region`, or web `Source` (`04` design principle #1).
   A claim with no evidence ref is treated as unverified and cannot drive an autonomous action.
3. **Quality/Eval verifier — the "secondary LLM critic"** (`02` §4). A dedicated verifier runs
   after high-stakes outputs (document analysis, offer comparison, decision briefs) and asks:
   *is every claim evidence-linked? is confidence honest? is anything missing?* It emits
   pass/fail + hallucination flags; a fail blocks the downstream action and, if unresolved,
   escalates. This mirrors the recommended agentic defense pattern.
4. **Never final legal advice**. Document and offer analysis always **separates *what we found*
   (with evidence refs) from *what we couldn't verify*** and is labeled non-advisory. Legal /
   notarial / signing content is a hard override (§2) — the system prepares and flags but a
   human decides. `DocRisk ≥ θ_docrisk` carries the label "requires human before signing".

---

## 5. Audit & trust

The `AuditEvent` log is the **event-sourced source of truth** (`04` design principle #2): every
state transition, score computation, `Action`, `HumanApproval`, and data change writes exactly
one immutable event.

- **Immutable, tamper-evident**. `AuditEvent.hash_prev` chains each event to its predecessor
  (a hash chain): any retroactive edit or deletion breaks the chain and is detectable. Events
  are append-only and never edited (`04` `AuditEvent` notes; retention e.g. 7y config).
- **Reproducible scores**. Each score persists with its **input vector** and **weight-set
  version** (`05` §0), so any number can be recomputed and back-tested.
- **PII access logged**. Every read of PII-heavy data (`Party`, `Message`, `Call` recordings,
  `Document`, `Photo`) writes an `AuditEvent` (`04` retention summary). Data region is
  tenant-pinned (`BusinessProfile.data_region`); erasure/export (DSAR) are first-class.
- **Autonomy changes audited**. Any change to `BusinessProfile.autonomy_defaults` or a case's
  `autonomy_level`, and every `HumanApproval` decision and override, is an `AuditEvent` with
  actor, before/after, and reason.
- **What each event captures**: `event_type`, `actor (ai_worker|human|system)`, `actor_id`,
  `from_state`/`to_state`, `payload (inputs, scores, weight_version)`, `evidence_ref_ids`,
  `hash_prev`.

Trust proposition: a tenant (or auditor, or regulator) can reconstruct **exactly why the system
did what it did** for any case — which score crossed which threshold, what evidence backed each
claim, who approved what, and that no record was altered after the fact.

---

## 6. Summary table — action-type × autonomy-level

Cell = whether the action executes **autonomously** at that level. `HITL` = requires a
`HumanApproval` before it happens. `—` = not applicable / draft-only.

| Action type (`Action.type`) | L1 Observe | L2 Prepare | L3 Communicate | L4 Execute Low Risk | L5 Cond. Autopilot |
|---|---|---|---|---|---|
| Inbound ingest / score / classify | Auto | Auto | Auto | Auto | Auto |
| Draft message / quote / brief | — (propose) | Auto (draft, held) | Auto | Auto | Auto |
| Send WhatsApp / SMS / email (informational) | HITL | HITL (human sends) | Auto¹ | Auto¹ | Auto¹ |
| Doc / photo request (`MissingItem`) | HITL | HITL | Auto¹ | Auto¹ | Auto¹ |
| AI voice call (intake / follow-up) | HITL | HITL | Auto¹ | Auto¹ | Auto¹ |
| Follow-up cadence step | HITL | HITL | Auto¹ | Auto¹ | Auto¹ |
| Booking / reschedule appointment | HITL | HITL | HITL | Auto² | Auto² |
| Quote send — **inside** `price_rules`, `< high_value_threshold` | HITL | HITL | HITL | Auto² | Auto² |
| Quote send — **outside** price rules / high value | HITL | HITL | HITL | HITL | HITL |
| Discount beyond authorized bounds | HITL | HITL | HITL | HITL | HITL |
| Contract / warranty / legal / notarial / signing | HITL | HITL | HITL | HITL | HITL (hard override) |
| Any step while `HUMAN_REVIEW_REQUIRED` | — | cap = draft only | HITL | HITL | HITL |

¹ Subject to all `05` §4 hard guarantees (quiet hours, min interval, `max_attempts`, opt-outs,
STOP) **and** the §3 output validators. ² Subject to price-rule validator, `high_value_threshold`,
no-double-booking, reversibility, and `Confidence ≥ θ_conf`; leaving the rule box auto-escalates.

### Audit level per action

| Action class | Audit level |
|---|---|
| Read / score / classify | Full: inputs + weight-version + scores → `AuditEvent` |
| Draft (held) | Draft content + recommendation + evidence refs + human edit distance |
| Autonomous outbound | `Action` (`autonomy_level_used`, `utility_score`, `chosen_over`) + produced `Message`/`Call` + validator results |
| Gated (`HumanApproval`) | `HumanApproval` (context/options/recommendation/evidence/decision) + `Action.approved_by` |
| Autonomy / config change | `AuditEvent(autonomy_changed)`: actor, before/after, reason |

All rows above additionally chain via `hash_prev` and log any PII access.

---

## 7. Open items (marked uncertain)

- **ASI01–ASI10 exact ordering/titles** — TO BE CONFIRMED against the final OWASP Agentic
  Top 10 PDF (published Dec 9 2025). https://genai.owasp.org/
- **Level 5 eligibility criteria** are deliberately conservative given the benchmark reality;
  the exact set of case types cleared for autopilot should be revisited as the Evaluation Lab
  (`15`) accumulates per-tenant outcome data.
- **OSWorld post-publication SOTA numbers** remain UNVERIFIED (`02` §0) and must not be cited
  as fact.
