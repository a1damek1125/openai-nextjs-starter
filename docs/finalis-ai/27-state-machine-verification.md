# Finalis AI — State Machine Verification & Audit

> Audit of the case lifecycle state machine specified in `03-case-lifecycle-state-machine.md`,
> cross-checked against `13-autonomy-and-safety.md` and `09-completion-loop-followup-promises.md`.
> Companion machine-readable spec: `state-machine.finalis.json` (this audit was computed against it).

**Status: ARCHITECTURE SPECIFIED.** No application code exists in this repository — the
17-state lifecycle exists only as documentation. **Nothing is implemented and no tests exist.**
This document verifies the *specification's* internal consistency and lists the issues an
implementation must resolve.

---

## 1. Reachability analysis (from `NEW_CONTACT`)

BFS over the explicit transition table (03 §4), **without** using the `HUMAN_REVIEW_REQUIRED → *`
wildcard or the two global edges (so this is the conservative walk — the wildcard and global
edges only add reachability, never remove it):

```
Depth 0: NEW_CONTACT
Depth 1: NEW_CONTACT → { INTAKE_IN_PROGRESS, SCHEDULED, HUMAN_REVIEW_REQUIRED, ABANDONED }
Depth 2: INTAKE_IN_PROGRESS → { QUALIFIED, WAITING_FOR_CLIENT_INFO, WAITING_FOR_DOCUMENTS }
         SCHEDULED          → { COMPLETED, WON, DOCUMENT_ANALYSIS, FOLLOW_UP_ACTIVE, LOST }
Depth 3: QUALIFIED               → { QUOTE_PREPARATION }
         FOLLOW_UP_ACTIVE        → { NEGOTIATION, OFFER_SENT }
         WAITING_FOR_CLIENT_INFO → { RECOVERY_LATER }   (also reachable via WON, LOST, WAITING_FOR_DOCUMENTS, FOLLOW_UP_ACTIVE)
```

- **All 17 states are reachable from `NEW_CONTACT`** within 3 hops, using explicit edges only.
  (With the `HUMAN_REVIEW_REQUIRED` wildcard expanded, everything except `RECOVERY_LATER` is
  reachable within 2 hops; `RECOVERY_LATER` at 3.)
- **Every non-terminal state has at least one exit**:
  - All 12 active states have explicit outgoing rows in the table.
  - `WON` → SCHEDULED | COMPLETED | RECOVERY_LATER; `LOST` → RECOVERY_LATER | ABANDONED.
  - `RECOVERY_LATER` → FOLLOW_UP_ACTIVE (on `wake_at`) — its only exit, which makes the
    nightly-sweep wake job a **liveness-critical dependency** (if the sweep dies, parked cases
    never exit; the doc's durability requirement in 09 §1 covers this, but the implementation
    must monitor it).
- No orphan states, no unreachable states, no state reachable only via a global edge.

Result was verified programmatically against `state-machine.finalis.json` (BFS over the 63
transition rows): `reachable: 17/17`, `unreachable: {}` both with and without wildcard expansion.

## 2. Dead-end (terminal) check

States with **zero outgoing transitions**: `COMPLETED`, `ABANDONED` — exactly the two states
03 §1 declares terminal. Confirmed correct:

- `WON` / `LOST` are *not* dead ends (closed-but-reopenable; both can reach `RECOVERY_LATER`,
  and `WON` can still progress to `SCHEDULED`/`COMPLETED`).
- `RECOVERY_LATER` is *not* a dead end (parked; single exit to `FOLLOW_UP_ACTIVE`).
- `COMPLETED` "may spawn a linked case" — that is case *creation*, not a transition, and is
  correctly absent from the transition table. The spawned case starts its own lifecycle.

## 3. Transition-count summary

| Metric | Count |
|---|---|
| States | **17** (12 active, 2 closed-reopenable, 2 terminal, 1 parked) |
| Explicit transition rows (03 §4, as transcribed in the JSON) | **63** |
| — of which the `HUMAN_REVIEW_REQUIRED → *` wildcard row | 1 (expands to 11 active targets → **73** fully-expanded edges) |
| Global edges | **2** (escalation interrupt → HUMAN_REVIEW_REQUIRED; closure edge → ABANDONED\|LOST) |
| Global invariants | **6** (03 §2) |
| Terminal states (no exit) | 2 (`COMPLETED`, `ABANDONED`) — as specified |

## 4. Genuine issues found

Each issue below was verified against the source documents. Severity scale: Low / Medium / High.
"Blocks implementation" = the state-machine module cannot be built unambiguously without a decision.

### A. `HUMAN_REVIEW_REQUIRED` has no terminal timeout — infinite dwell possible

**Verified.** 03 §3.11 defines only "internal SLA on the human (e.g. remind owner at +2h, +1d)"
and 13 §2.3 gives `HumanApproval.deadline` with an `sla_breached` flag — but a breached SLA
only *flags*; no rule ever moves the case anywhere if the human never responds. 09 §1 explicitly
calls HRR "a pause … not a closure". Because HRR is an *active* state, it satisfies invariant
INV-1 with "remind the human" as its next action — so the stuck sweep never fails loudly, and
the case can dwell forever while autonomy is frozen at L2. The global closure edge does not help:
its guards (opt-out, follow-up exhaustion) don't fire on internal human silence.

- **Severity: High** (this is the escalation path — precisely the cases that matter most can silently rot).
- **Fix:** add an explicit escalation ladder after `sla_breached`: re-route to a fallback
  `UserRole` (03 §3.11 already hints "may re-route to a different human/role"), then after a
  configurable `max_review_dwell` (BusinessProfile), force a decision event — e.g. notify the
  owner-of-owners and auto-park to `RECOVERY_LATER` with reason `review_timeout` (never
  auto-execute the pending client-facing action). Add `time_in_state` to the nightly sweep's
  loud-failure checks for HRR specifically.
- **Blocks implementation? No** — the module can ship with dwell alerts, but the ladder must be
  specified before production, or the "SLA breach rate" metric will be the only witness.

### B. `WAITING_FOR_DOCUMENTS ↔ DOCUMENT_ANALYSIS` rescan cycle has no loop counter

**Verified.** 03 §4 allows `WAITING_FOR_DOCUMENTS → DOCUMENT_ANALYSIS` (quality gate passed) and
`DOCUMENT_ANALYSIS → WAITING_FOR_DOCUMENTS` ("need clearer/more docs"). The follow-up cadence
"max N attempts" in §3.4/§3.5 caps *client-silence* attempts within one waiting episode — the
attempt counter is per follow-up sequence, and each re-entry into `WAITING_FOR_DOCUMENTS`
plausibly restarts it. "Repeated unreadable uploads" is listed only as an escalation *trigger*
with no defined count, and `DOCUMENT_ANALYSIS` itself has no timeout ("internal … no client
wait"). A cooperative client sending endless blurry photos cycles indefinitely.

- **Severity: Medium.**
- **Fix:** persist a per-case `rescan_count` (per document type); at `max_rescans` (playbook
  default, e.g. 3) force the escalation trigger concretely: → `HUMAN_REVIEW_REQUIRED` with
  reason `repeated_unreadable_uploads`. Also give `DOCUMENT_ANALYSIS` an internal processing
  timeout (worker stall → retry N, then HRR).
- **Blocks implementation? No** — but the counter should be in the initial data model
  (cheap now, migration later).

### C. `NEGOTIATION ↔ OFFER_SENT ↔ FOLLOW_UP_ACTIVE` cycles have no global case-age limit

**Verified.** The table permits full cycles: OFFER_SENT → FOLLOW_UP_ACTIVE → OFFER_SENT (revised),
OFFER_SENT → NEGOTIATION → OFFER_SENT, NEGOTIATION ↔ FOLLOW_UP_ACTIVE. Guards are per-sequence:
`FollowUpSequence` has `max_attempts` (09 §2 "max total attempts then park"), but every revised
offer or negotiation re-entry starts a *new* sequence with a fresh budget. Nothing in 03, 09, or
13 bounds total case age or total offers-per-case. AnnoyanceRisk dampens frequency, not duration.

- **Severity: Low–Medium** (client engagement gates each cycle, so this is bounded by the client's
  patience in practice — but a pathological or adversarial counterparty burns AI actions forever,
  and metrics like "win rate by follow-up step" get polluted by zombie cases).
- **Fix:** add tenant-configurable `max_case_age_days` and/or `max_offer_revisions` to
  `BusinessProfile`; on breach, the nightly sweep raises `StuckScore` to force the escalation
  interrupt (owner decides: park, close LOST, or extend). This reuses existing machinery — no
  new edge needed.
- **Blocks implementation? No.**

### D. `WON → RECOVERY_LATER` reopening semantics are ambiguous (upsell reuses a sale-context wake)

**Verified.** `RECOVERY_LATER`'s only wake target is `FOLLOW_UP_ACTIVE` (03 §3.17, §4), and
`FOLLOW_UP_ACTIVE` presumes a live sale awaiting client response ("post-offer or post-info-request",
requires a `FollowUpSequence`). For a **won** case parked for upsell/renewal, waking into
`FOLLOW_UP_ACTIVE` puts a *closed, won* deal back into a state whose invariants (offer context,
follow-up sequence, win/lose exits) don't match — and its `WON` outcome would double-count the win.
Meanwhile 03 §3.15 (`COMPLETED`) *prohibits* reopening and mandates spawning "a *new*
RECOVERY_LATER-linked case" for renewals. So the spec has two contradictory patterns for the
same business event (future upsell): COMPLETED spawns, WON reopens. Which applies to a case that
went WON → RECOVERY_LATER without ever completing is unspecified.

- **Severity: Medium** (semantic/data-integrity ambiguity, corrupts win-rate and pipeline metrics).
- **Fix:** adopt the §3.15 pattern uniformly: `WON → RECOVERY_LATER` should be replaced by (or
  implemented as) WON spawning a **linked child case** that starts life in `RECOVERY_LATER` with
  `recovery_reason=upsell`, waking into the child's `FOLLOW_UP_ACTIVE` with Deal Memory context;
  the parent proceeds WON → SCHEDULED/COMPLETED untouched. Keep direct reopen only for `LOST →
  RECOVERY_LATER` (same deal, genuinely resumable).
- **Blocks implementation? Yes (decision required)** — the transition table and the case-linking
  data model differ depending on the choice; deferring it means a schema/metric migration later.

### E. Rollback behavior on failed transitions is unspecified (transition/action atomicity)

**Verified.** Invariant INV-4 says every transition writes an `AuditEvent`, and 13 §2.3 shows
"Orchestrator applies the chosen transition/Action" as one arrow — but no document specifies
ordering or failure semantics when the transition and its side-effecting action are coupled.
Example: `QUOTE_PREPARATION → OFFER_SENT` where the send fails mid-way. Is the case now
`OFFER_SENT` with no offer delivered (state lies), or still `QUOTE_PREPARATION` with a client
who half-received something (action leaked)? The append-only, hash-chained AuditEvent log
(13 §5) cannot be rolled back, so a naive "write event then act" leaves a permanent record of a
transition that didn't really happen. Durable-execution notes in 09 §1 cover *resumption*, not
compensation.

- **Severity: High** (correctness of the core module; also an audit-integrity question).
- **Fix:** specify the protocol: (1) side-effecting actions execute **before** the state commit,
  with an idempotency key; (2) transition commit + AuditEvent write are one DB transaction;
  (3) on action failure, no state change — instead write `AuditEvent(event_type=action_failed)`
  and schedule retry per next_action; (4) for actions that cannot confirm success (timeout after
  send), enter a `pending_confirmation` sub-status on the *same* state, never guess. Alternatively
  a saga/outbox pattern; either way it must be written down.
- **Blocks implementation? Yes** — the executor's core loop cannot be coded without this decision.

### F. `QUALIFIED` requires "immediate progression; no dwell" but is a persisted state

**Verified.** 03 §3.3 says follow-up timing is "immediate progression; no dwell", yet `QUALIFIED`
is a full member of the `Case.status` enum (03 §1, "states map 1:1"), is a legal *target* of five
transitions including human-decision routing from `HUMAN_REVIEW_REQUIRED`, and as an active state
must carry `next_action`/`due_at` (INV-1). A crash, a queued `HumanApproval` on the outbound
routing step (INV-3), or an orchestrator backlog can and will leave cases persisted in QUALIFIED
with real dwell — the spec gives no `due_at` convention or timeout for that situation.

- **Severity: Low** (mostly a spec-precision gap, but it breaks the "no dwell" claim and the
  stuck-sweep semantics for this state).
- **Fix:** pick one and document it: **(i)** make QUALIFIED a *transient/pseudo-state* — the
  routing decision executes synchronously inside the transition out of INTAKE/WAITING/HRR and
  QUALIFIED never persists (then remove it from `Case.status` or mark it non-persistable); or
  **(ii)** keep it persisted with a convention `next_action=route_case, due_at=now`, plus a short
  timeout (e.g. 1h) after which the stuck sweep escalates. Option (ii) is less invasive and
  crash-safe; recommended.
- **Blocks implementation? No** — but must be resolved before the invariant checker is written,
  since option (i) changes the enum.

### Non-issues checked and cleared

- The `HUMAN_REVIEW_REQUIRED → *` wildcard cannot smuggle a case into terminal states other than
  the three listed (WON/LOST/ABANDONED): "*" is scoped to *active* states. Correct as written.
- The global closure edge targeting `LOST` "if a reason is captured" is consistent with LOST's
  required loss-reason field. Consistent.
- `NEW_CONTACT → SCHEDULED` skipping intake is intentional (returning client rebooking a known
  job, backed by Deal Memory). Legitimate.

## 5. Acceptance criteria for the state-machine module

The implementation is acceptable when all of the following hold:

1. **JSON is the single source of truth.** The module loads `state-machine.finalis.json` at
   startup, validates it (17 states, kinds partition, every transition endpoint exists,
   `ANY_ACTIVE` expansion well-defined), and exposes the state/transition sets from it — no
   hardcoded duplicate tables. A CI check fails if code and JSON drift.
2. **Illegal transitions are rejected.** `transition(case, to_state, actor, reason, evidence_refs)`
   throws/returns a typed error for any (from, to) pair not in the table, the wildcard expansion,
   or the two global edges. Terminal states reject all outgoing transitions. Attempts are
   themselves audit-logged (`event_type=transition_rejected`).
3. **Invariants are enforced, not assumed.** INV-1..INV-6 run as guards inside the transition
   commit: active-state post-condition requires non-null `next_best_action`/`next_action_due_at`;
   entering HRR sets `state_cap=2`; actors above their effective autonomy level get their
   transition converted to a queued `HumanApproval` (INV-3); hard opt-out force-routes via the
   closure edge regardless of requested target (INV-6). Violations abort the transaction.
4. **One `AuditEvent` per transition, atomically.** The state write and the
   `AuditEvent{from_state, to_state, actor, reason, evidence_refs, hash_prev}` append commit in a
   single transaction (per issue E's protocol); side effects execute with idempotency keys and
   failures write `action_failed` events without a state change.
5. **Property test — random walks never violate invariants.** A generative test drives ≥10k
   random walks from `NEW_CONTACT` (random legal transitions, random interleaved global-edge
   fires, random actor autonomy levels, injected action failures) and asserts after every step:
   case is in a declared state; active ⇒ future action present; HRR ⇒ effective level ≤ 2;
   terminal ⇒ no further transitions accepted; audit chain unbroken (`hash_prev` verifies);
   every walk terminates in {COMPLETED, ABANDONED} or in a live state with a due future action.
6. **Reachability regression.** A unit test recomputes §1's BFS from the loaded JSON and asserts:
   17/17 reachable, exactly {COMPLETED, ABANDONED} have out-degree 0, `RECOVERY_LATER` out-degree 1.
7. **Issues A–F resolved or ticketed.** D and E (marked "blocks implementation") have recorded
   decisions before the executor is coded; A, B, C, F have configuration knobs
   (`max_review_dwell`, `max_rescans`, `max_case_age_days`, QUALIFIED timeout) with playbook
   defaults, or explicit deferral tickets.

---

*Verification method: full read of 03/09/13; transition table transcribed to
`state-machine.finalis.json`; reachability, exit, and terminal checks computed by BFS over the
JSON (63 explicit rows, 73 expanded edges, +2 global edges); each issue A–F confirmed against
specific sections cited above.*
