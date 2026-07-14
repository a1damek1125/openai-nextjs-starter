# Case Graph — State Machine (module-authoritative)

This is the authoritative state-machine document for the case-graph module. It refines
`docs/finalis-ai/03-case-lifecycle-state-machine.md` (canonical lifecycle spec) and
documents the executable form in `finalis/state_machine.py`, validated 1:1 against the
machine-readable spec `docs/finalis-ai/state-machine.finalis.json` **v1.1** by
`tests/test_state_machine.py::TestJsonConsistency` (same state set, same transitions,
global edges present). Status: **Implemented and tested** — 19 tests, including a
random-walk invariant test and reachability/exit checks for every state.

## The 17 states

`CaseState` partitions into four disjoint kinds (tested:
`test_partition_is_complete_and_disjoint`):

| State | Kind | Final? | Purpose |
|---|---|---|---|
| NEW_CONTACT | active | no | First inbound contact; classify intent, dedup, create Case |
| INTAKE_IN_PROGRESS | active | no | Industry-playbook intake questions; instantiate MissingItems; initial LeadScore/MIS |
| QUALIFIED | active | no | Qualification passed; route downstream ("no dwell" — see open issue F) |
| WAITING_FOR_CLIENT_INFO | active | no | A non-document MissingItem blocks progress; targeted ask + follow-up cadence |
| WAITING_FOR_DOCUMENTS | active | no | A document/photo MissingItem blocks quote/analysis |
| DOCUMENT_ANALYSIS | active | no | Document Intelligence extracts fields with evidence refs; DocRisk |
| QUOTE_PREPARATION | active | no | Draft quote (variants, assumptions, blockers); approval if uncertain |
| OFFER_SENT | active | no | Offer delivered; watch replies, start follow-up sequence |
| FOLLOW_UP_ACTIVE | active | no | Completion-loop-driven cadence while awaiting client response |
| NEGOTIATION | active | no | Objections/counters within authority bounds; DecisionBriefs |
| HUMAN_REVIEW_REQUIRED | active | no | Escalation parking; **autonomy capped at L2** (invariant 2); a pause, not a closure |
| SCHEDULED | active | no | Appointment booked; confirmations and reminders |
| WON | closed_reopenable | **final** | Offer accepted / job committed |
| LOST | closed_reopenable | **final** | Client declined; loss reason captured |
| COMPLETED | terminal | **final** | Service delivered; only spawn linked cases, never reopen |
| ABANDONED | terminal | **final** | Spam / hard opt-out / exhausted with no recovery potential |
| RECOVERY_LATER | parked | **final** | Warm lead parked with a `wake_at`; silent until woken |

Code sets: `TERMINAL_STATES` = {COMPLETED, ABANDONED} (no exits at all — tested:
`test_terminals_have_no_exits`), `CLOSED_REOPENABLE_STATES` = {WON, LOST},
`PARKED_STATES` = {RECOVERY_LATER}, `FINAL_STATES` = the union of those three
(5 states), `ACTIVE_STATES` = the remaining 12.

## The v1.1 transition table — 71 edges

`state-machine.finalis.json` v1.1 carries **71 transition rows** (the
`HUMAN_REVIEW_REQUIRED → ANY_ACTIVE` wildcard row counts as one and expands to the 11
other active states at load time). Per-state summary (targets as transcribed into
`TRANSITIONS` in `finalis/state_machine.py`):

| From | # | To |
|---|---|---|
| NEW_CONTACT | 4 | INTAKE_IN_PROGRESS, SCHEDULED, HUMAN_REVIEW_REQUIRED, ABANDONED |
| INTAKE_IN_PROGRESS | 5 | QUALIFIED, WAITING_FOR_CLIENT_INFO, WAITING_FOR_DOCUMENTS, HUMAN_REVIEW_REQUIRED, ABANDONED |
| QUALIFIED | 5 | WAITING_FOR_DOCUMENTS, WAITING_FOR_CLIENT_INFO, QUOTE_PREPARATION, SCHEDULED, HUMAN_REVIEW_REQUIRED |
| WAITING_FOR_CLIENT_INFO | 7 | INTAKE_IN_PROGRESS, QUALIFIED, WAITING_FOR_DOCUMENTS, FOLLOW_UP_ACTIVE¹, RECOVERY_LATER, ABANDONED, HUMAN_REVIEW_REQUIRED |
| WAITING_FOR_DOCUMENTS | 5 | DOCUMENT_ANALYSIS, FOLLOW_UP_ACTIVE¹, RECOVERY_LATER, ABANDONED, HUMAN_REVIEW_REQUIRED |
| DOCUMENT_ANALYSIS | 4 | QUOTE_PREPARATION, NEGOTIATION, WAITING_FOR_DOCUMENTS (needs_rescan), HUMAN_REVIEW_REQUIRED |
| QUOTE_PREPARATION | 3 | OFFER_SENT, WAITING_FOR_CLIENT_INFO, HUMAN_REVIEW_REQUIRED |
| OFFER_SENT | 6 | FOLLOW_UP_ACTIVE, NEGOTIATION, WON, LOST, SCHEDULED, RECOVERY_LATER¹ |
| FOLLOW_UP_ACTIVE | 9 | NEGOTIATION, OFFER_SENT, WAITING_FOR_CLIENT_INFO¹, WAITING_FOR_DOCUMENTS¹, WON, LOST, SCHEDULED, RECOVERY_LATER, HUMAN_REVIEW_REQUIRED |
| NEGOTIATION | 6 | WON, LOST, OFFER_SENT, FOLLOW_UP_ACTIVE, RECOVERY_LATER¹, HUMAN_REVIEW_REQUIRED |
| HUMAN_REVIEW_REQUIRED | 6 rows | ANY_ACTIVE (wildcard, →11 states) + WON, LOST, ABANDONED, COMPLETED¹, RECOVERY_LATER¹ — i.e. code: all active states except itself, plus all 5 final states |
| SCHEDULED | 5 | COMPLETED, WON, DOCUMENT_ANALYSIS, FOLLOW_UP_ACTIVE, LOST |
| WON | 3 | SCHEDULED, COMPLETED, RECOVERY_LATER |
| LOST | 2 | RECOVERY_LATER, ABANDONED |
| RECOVERY_LATER | 1 | FOLLOW_UP_ACTIVE (scheduled wake — see below) |
| COMPLETED / ABANDONED | 0 | — (terminal) |

¹ = edge **added in v1.1** (8 edges; see "v1.1 deltas" below).

Guards live in the JSON per row (e.g. QUOTE_PREPARATION → OFFER_SENT requires human
approval OR autonomy ≥ L4 inside price rules below the high-value threshold with
Confidence ≥ θ_conf). The code enforces the shape (legal from→to pairs + the flag-based
rules below); guard *evaluation* is the caller's job via ActionGateService/autonomy —
per doc 03 §2 invariant 3, unauthorized transitions queue a HumanApproval instead.

## The two global edges

Both exist in code as flag-gated overrides in `is_legal(...)` and in the JSON's
`global_edges` (presence tested: `test_global_edges_present`):

1. **`escalation_interrupt`** — any *active* state → HUMAN_REVIEW_REQUIRED
   (`escalation_interrupt=True`). Guard: EscalationScore ≥ θ_escalate or a hard
   override (legal/notarial, safety emergency). Never fires from final/terminal states
   (tested: `test_escalation_interrupt_from_any_active_state`,
   `test_escalation_interrupt_not_from_terminal`).
2. **`closure_edge`** — any *non-terminal* state → ABANDONED or LOST
   (`hard_opt_out=True` or `followup_exhausted=True`). Hard opt-out additionally sets
   `case.opted_out = True` permanently (invariant 6 — tested:
   `test_stop_optout_closure_edge_from_any_non_terminal`,
   `test_hard_optout_suppresses_permanently`).

## The final-state rule (NEW in the case-graph spec)

There are **5 final states: WON, LOST, COMPLETED, ABANDONED, RECOVERY_LATER**
(`FINAL_STATES` in code; `final_states` in the JSON). The rule, enforced in
`is_legal` and tested (`test_final_states_require_human_override_to_exit`):

> **No case leaves a final state without explicit `human_override=True`** — even along
> edges that exist in the transition table (e.g. WON → SCHEDULED is a legal edge, but
> only a human may take it). Terminal states (COMPLETED, ABANDONED) have no edges at
> all, so not even an override exits them.

**The single documented deviation — the `scheduled_wake` exception**:
`RECOVERY_LATER → FOLLOW_UP_ACTIVE` is additionally legal with `scheduled_wake=True`
and no human override. Justification: RECOVERY_LATER is where the Completion Loop
*parks* exhausted-but-warm cases with a `wake_at`; the loop's nightly sweep must be
able to wake due cases automatically, **or recovery never happens** — requiring a human
to manually un-park every seasonal lead would defeat the point of parking them. The
exception is narrow (exactly that one from→to pair, exactly that one flag), transcribed
in the JSON's `final_state_rule`, and every wake still writes a `case.state_changed`
audit event like any other transition.

`transition(...)` additionally enforces: invariant 2 (entering HUMAN_REVIEW_REQUIRED
sets `autonomy_frozen_at = 2`, leaving clears it — tested:
`test_human_review_freezes_autonomy_at_2`), invariant 6 (opt-out flag), invariant 4
(every transition writes an audit event), and drops `next_best_action`/
`next_action_due_at` on entering terminal/closed states (parked RECOVERY_LATER keeps a
wake action, set by `CompletionLoop.park_exhausted`).

## Timeout behaviors

Per-state timeout behavior is specified in the JSON (`timeout_behavior` per state):
e.g. WAITING_FOR_CLIENT_INFO/-DOCUMENTS cadence +24h → +48h → +72h then park;
OFFER_SENT +24h → +72h → +7d → RECOVERY_LATER; SCHEDULED reminders at −24h/−2h;
HUMAN_REVIEW_REQUIRED internal SLA reminders on the human.

**The open design decisions from doc 39 remain open.** The scaffold does not silently
resolve them:

- **A (High)** — HUMAN_REVIEW_REQUIRED has no terminal timeout: infinite dwell on
  human silence is possible; the escalation ladder (`max_review_dwell` → notify →
  auto-park) must be specified before production.
- **B (Medium)** — no rescan-loop counter: WAITING_FOR_DOCUMENTS ↔ DOCUMENT_ANALYSIS
  cycles are legal and uncounted; needs per-doc-type `rescan_count` with max → HRR.
- **C (Low–Medium)** — no global case-age limit: OFFER_SENT/NEGOTIATION/
  FOLLOW_UP_ACTIVE cycles reset the follow-up budget; needs tenant-configurable
  `max_case_age_days` / `max_offer_revisions`.
- **D (Medium)** — WON → RECOVERY_LATER reopening semantics are ambiguous (COMPLETED
  spawns a linked case, WON reopens in place); decision required before the executor
  is coded.
- **F (Low)** — QUALIFIED is "no dwell" by convention but is a persisted state with no
  timeout; doc 27's option (ii) (keep persisted, `due_at=now`, 1 h stuck-sweep
  escalation) is recommended but not yet ratified.

## Per-state allowed / prohibited AI actions

The canonical per-state catalog is **doc 03 §3**, transcribed field-for-field into the
JSON's `allowed_ai_actions` / `prohibited_ai_actions` / `escalation_triggers` per
state (e.g. NEW_CONTACT may greet/classify/create-case but must never quote a price;
DOCUMENT_ANALYSIS must never assert facts below the confidence floor;
HUMAN_REVIEW_REQUIRED allows L≤2 prepare/summarize/draft only and prohibits any
autonomous client-facing action; RECOVERY_LATER allows nothing before `wake_at`).
This module doc does not restate the catalog — read it from the JSON, which the
consistency tests keep honest against the code's state set.

### v1.1 deltas (new edges and why)

v1.1 added **8 edges** to the v1.0 table (verified by diffing the two spec versions);
all close cases where doc 03's own prose (timeout behaviors, cadence, human routing)
implied movements the v1.0 table could not express:

| New edge | Why |
|---|---|
| WAITING_FOR_CLIENT_INFO → FOLLOW_UP_ACTIVE | "silence → cadence takes over": the waiting states' documented follow-up cadence is *driven by* FOLLOW_UP_ACTIVE, but v1.0 had no edge into it |
| WAITING_FOR_DOCUMENTS → FOLLOW_UP_ACTIVE | same |
| FOLLOW_UP_ACTIVE → WAITING_FOR_CLIENT_INFO | client re-engages but info is still missing — the return path of the two edges above |
| FOLLOW_UP_ACTIVE → WAITING_FOR_DOCUMENTS | same, for documents |
| OFFER_SENT → RECOVERY_LATER | OFFER_SENT's documented timeout ladder ends "…+7d last-chance → RECOVERY_LATER", yet v1.0 had no such edge |
| NEGOTIATION → RECOVERY_LATER | stalled negotiation parks instead of being forced through LOST |
| HUMAN_REVIEW_REQUIRED → COMPLETED | human closure routing: the human must be able to close to *any* final outcome, not only WON/LOST/ABANDONED |
| HUMAN_REVIEW_REQUIRED → RECOVERY_LATER | same — human parks for recovery |

These add routes, not new AI permissions: every new edge into a final state still
falls under the final-state rule and the gate/autonomy checks, and the two
FOLLOW_UP_ACTIVE round-trips stay inside the anti-spam budget owned by the Completion
Loop.
