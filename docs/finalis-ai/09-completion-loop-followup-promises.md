# Finalis AI — Completion Loop, Follow-up, Promise Tracker & Missing-Info Hunter

> This is what makes Finalis a *worker* and not a chatbot: the case never "ends" after a
> conversation. A durable loop drives every open case toward a closure path.

## 1. Completion Loop Engine

Every active `Case` always carries: `goal`, `status`, `next_best_action`, `next_action_due_at`,
`owner`, `risk_score`, `lead_score`, `mis_score`, and a `closed_reason` path. The loop
guarantees these invariants (see `03` §2).

**Two triggers:**
1. **Event-driven** — any inbound message/call/document/webhook re-runs the case's scoring +
   NBA (`05`) immediately.
2. **Nightly stuck sweep** — a scheduled job iterates all active cases and:
   - recomputes `LeadScore`, `MIS`, `StuckScore`, `PromiseBreachScore`, `EscalationScore`;
   - checks the invariant "active case has a future action" (fails loudly otherwise);
   - enqueues the next best action (execute if autonomy allows, else `HumanApproval`);
   - parks exhausted cases to `RECOVERY_LATER`, wakes due `RECOVERY_LATER` cases.

**Durability**: the loop runs on a durable substrate so a follow-up scheduled 72h out
survives restarts. Options (see `18`): LangGraph checkpointing for the case graph + a durable
scheduler (Temporal, or Postgres-backed queue/APScheduler for MVP) for time-based wakeups.
Because LangGraph "saves progress at checkpoints … to pause and later resume exactly where it
left off" (https://docs.langchain.com/oss/python/langgraph/durable-execution), multi-day cases
resume correctly.

**Closure paths** (the only ways a case leaves the loop): `WON`, `LOST`, `COMPLETED`,
`ABANDONED`, `HUMAN_REVIEW_REQUIRED` (temporary), or parked `RECOVERY_LATER`.

## 2. Follow-up Worker (anti-spam by design)

Chooses **next best channel + timing** using `FollowUpPriority = LeadScore · TimeDecay ·
IntentSignal − AnnoyanceRisk` (`05` §4).

**Cadence** (playbook default, tunable): post-offer `+24h → +72h → +7d → RECOVERY_LATER`;
missing-info `+24h → +48h → +72h`. Each step picks the channel maximizing expected reply per
unit AnnoyanceRisk, honoring learned client preference (Deal Memory) and quiet hours.

**Hard guarantees (never violated):**
- Never contact during quiet hours / outside allowed local window.
- Respect channel opt-outs and global STOP (STOP → suppress permanently; may → `ABANDONED`).
- Minimum inter-touch interval; **max total attempts** then park to `RECOVERY_LATER`.
- One consolidated ask per touch — never field-by-field pestering.

**Channel order default (home services)**: WhatsApp → SMS → email → call, overridden per party
by observed responsiveness.

**Deal Memory** informs every follow-up: prior interactions, preferred channel/time, past
objections, price sensitivity, and value potential — so a recovered lead gets a context-aware
opener ("Hi again — last spring you asked about AC install; want that quote refreshed?").

## 3. Promise Tracker

Tracks commitments by **any** party (client, company, technician, salesperson, notary, lawyer,
supplier, insurer). Promises are extracted from calls (`06` post-call) and messages, stored as
`Promise` rows with `who / what / due_at / importance / dependency_impact / status`.

**Breach detection**: nightly + on due-time, compute `PromiseBreachScore = Importance · Delay ·
DependencyImpact` (`05` §10).
- **Client promise overdue** → Missing-Info-style follow-up ("you mentioned you'd send the
  boiler photo — whenever's easy 🙂").
- **Company/technician/notary promise overdue** → owner alert / escalation (a broken *company*
  promise is a trust risk and often more damaging).
- Downstream dependencies (a broken promise that blocks other steps) raise the score and the
  urgency.

Examples handled: "client promised to send photos", "owner promised to call back", "technician
promised quote by Friday", "notary promised the missing document". Each is a first-class,
tracked, evidence-linked object — not a note someone forgets.

## 4. Missing-Information Hunter

Detects information/documents that block the case using `MIS` (`05` §2) and the playbook's
`required_fields` (each with weight `w_i` and `blocks_quote`).

**Behavior:**
- Instantiates `MissingItem` rows at intake; re-evaluates on every event.
- When `MIS_normalized ≥ θ_mis` or any `blocks_quote` item is missing → generates a single,
  specific, example-bearing request via the best channel ("a quick photo of the appliance
  label — like this 👇 — lets us quote accurately").
- Marks items `received` when satisfied by a `Document`/`Photo`/`Message`, runs a quality
  pre-check (`07`), and unblocks the relevant state transition.
- Hunts across: photos, VIN, address, dimensions, invoices, contracts, previous offers, ID,
  signatures, attachments, and pending client *decisions*.

## 5. Objection Handler (loop-invoked in NEGOTIATION/FOLLOW_UP)

Detects objections — *price too high, needs time, has a competitor offer, wants a discount,
deadline too long, doesn't trust, needs partner/landlord approval, missing docs* — and either
prepares a recommended response **within authorized bounds** or escalates.

- Pulls advantages from `BusinessProfile` + Offer Comparator (warranty, timeline, service,
  no-hidden-costs) and produces a concrete suggested reply.
- Discounts beyond authority, contract redlines, or partner-approval situations → escalate
  (raises `EscalationScore`).
- Output is a `DecisionBrief`-style suggestion the owner can send with one tap or edit.

## 6. Quote Builder (loop-invoked in QUOTE_PREPARATION)

Drafts a quote from intake + photos + documents + `price_rules` + similar past cases (Deal
Memory), producing: scope, **base + premium variants**, listed assumptions, remaining blockers,
risks, and sales arguments.

**Guardrail**: never finalizes/sends a binding price without price-rule coverage, or requires
human approval when pricing uncertainty is high (autonomy `≤ L2/L3`). A draft with high
uncertainty routes to `HUMAN_REVIEW_REQUIRED`.

## 7. Decision Worker (owner-facing output of the loop)

Turns case state into a short, actionable brief (not a report). Canonical shape:

> **Case**: bathroom renovation — Kowalski. **Value**: €8–12k. **Status**: comparing us vs. a
> competitor. **Problem**: competitor is €700 cheaper. **Our edge**: faster timeline, longer
> warranty. **Next step**: call today after 16:00, offer the faster-timeline variant.
> **Risk**: may walk if no reply by tomorrow. *(Sources/evidence linked.)*

Generated on meaningful state changes and surfaced in the Command Center; every claim is
evidence-linked and carries a confidence.

## 8. How the loop prevents "lost leads" (the value story)

Each nightly sweep converts a pile of open cases into a **prioritized work queue**:
hot-but-stuck cases float to the top; overdue promises trigger nudges; silent leads get
context-aware recovery instead of being forgotten; offers with no response get timed,
non-spammy follow-up. The Revenue Recovery view (`11`) quantifies leads/pipeline recovered —
the language the buyer actually cares about.
