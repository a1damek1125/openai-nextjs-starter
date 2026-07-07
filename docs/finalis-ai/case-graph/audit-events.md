# Case Graph — Audit Event Catalog

> **Ground truth**: `finalis/audit.py` (`AuditEvent`, `AuditLog`), emitters
> across `finalis/case_services.py`, `state_machine.py`, `completion_loop.py`,
> `documents.py`, `certainty_core.py`, `voice/*`, branch
> `claude/finalis-case-graph-completion-loop`, 160 tests passing.
> Spec: doc 04 (`AuditEvent` entity), doc 22 §2.2 (domain event catalog).

## 1. The spec's 29 required events — implementation status

### Implemented in the scaffold (emitter in code, exercised by tests)

| Spec event | As emitted (exact string) | Emitter | Test coverage |
|---|---|---|---|
| CASE_CREATED | `CASE_CREATED` | `CaseGraphService.create_case` (voice engine emits lowercase `case.created` — see §2) | `test_create_case_writes_audit` |
| CASE_STATE_CHANGED | **`case.state_changed`** | `state_machine.transition` (sole emitter) | `tests/test_state_machine.py`; E2E asserts exactly 7 |
| PARTY_ATTACHED | `PARTY_ATTACHED` | `CaseGraphService.attach_entity` (edge map) | `test_attach_entities_and_read_graph` |
| VOICE_SESSION_ATTACHED | `VOICE_SESSION_ATTACHED` | same edge map | same tested code path; not asserted by name |
| DOCUMENT_ATTACHED | `DOCUMENT_ATTACHED` | same edge map | same tested code path; not asserted by name |
| MESSAGE_RECEIVED | `MESSAGE_RECEIVED` | same edge map | same tested code path; not asserted by name |
| EVIDENCE_CREATED | `EVIDENCE_CREATED` | edge map + voice Conversation Intelligence | `test_attach_entities_and_read_graph`, `tests/test_conversation_intelligence.py` |
| MISSING_INFO_DETECTED | `MISSING_INFO_DETECTED` | `MissingInfoService.detect`, voice engine | `test_detect_from_hvac_profile` |
| MISSING_INFO_RESOLVED | `MISSING_INFO_RESOLVED` | `MissingInfoService.resolve` | `test_blockers_block_and_resolution_unblocks` |
| PROMISE_CREATED | `PROMISE_CREATED` | voice Conversation Intelligence; callers (E2E step 4) | `tests/test_conversation_intelligence.py`, E2E |
| PROMISE_DUE | `PROMISE_DUE` | `PromiseTrackerService.evaluate` | `TestPromiseTracker::test_statuses` |
| PROMISE_BREACHED | `PROMISE_BREACHED` (loop's older path: `promise.breached`) | `PromiseTrackerService.evaluate` / `CompletionLoop.promise_check` | `test_statuses`; `tests/test_completion_loop.py` |
| PROMISE_FULFILLED | `PROMISE_FULFILLED` | `PromiseTrackerService.fulfill` | `test_fulfill` |
| NEXT_ACTION_CREATED | `NEXT_ACTION_CREATED` | `NextBestActionService.select` | E2E step 10 |
| ACTION_CREATED | `ACTION_CREATED` | `ActionGateService` (ALLOW) | `test_allow_low_risk`, E2E |
| ACTION_BLOCKED | `ACTION_BLOCKED` | `ActionGateService` (BLOCK) | `test_block_on_optout` |
| ACTION_ABSTAINED | `ACTION_ABSTAINED` | `ActionGateService` (ABSTAIN) | `test_abstain_on_low_confidence` |
| HUMAN_REVIEW_REQUESTED | `HUMAN_REVIEW_REQUESTED` | `ActionGateService` (REQUIRE_HUMAN_APPROVAL) | `test_require_human_for_high_risk` |
| FOLLOW_UP_RATE_LIMITED | `FOLLOW_UP_RATE_LIMITED` | `CompletionLoopService.run_case` (duplicate-ask suppression) | `test_duplicate_followup_prevented` |
| FOLLOW_UP_SENT | **`followup.sent`** | `CompletionLoop.send_followup` | `tests/test_completion_loop.py`, E2E step 10 |
| FOLLOW_UP_SUPPRESSED | **`followup.suppressed`** | `CompletionLoop.send_followup` (quiet hours / interval / opt-out / exhausted) | `tests/test_completion_loop.py` |
| FOLLOW_UP_EXHAUSTED | **`followup.exhausted`** | `CompletionLoop.send_followup` (max attempts) | `tests/test_completion_loop.py` |
| HUMAN_APPROVAL_GRANTED | `HUMAN_APPROVAL_GRANTED` | caller-recorded (no service method yet) | E2E step 17–18 |
| DECISION_BRIEF_CREATED | `DECISION_BRIEF_CREATED` | caller-recorded ("via audit for the MVP scaffold") | E2E step 16 |
| CONVERSATION_ANALYZED | `CONVERSATION_ANALYZED` | voice Conversation Intelligence | `tests/test_conversation_intelligence.py` |
| SCORES_RECOMPUTED | **`scores.recomputed`** | `CompletionLoop.stuck_sweep` (per active case, every sweep) | `test_sweep_writes_score_audit_for_every_active_case` |
| CERTAINTY_STAMPED | **`certainty.stamped`** | `certainty_core.NullAdapter.certify` | `TestLGGTPlaceholderCallable` |

Also live in code (beyond the required 29): `document.analysis_completed`,
`document.needs_rescan`, `approval.requested` (`finalis/documents.py`), and
`case.created` (voice engine).

### Designed-only (in docs 04/22; no emitter in the scaffold yet)

| Spec event | Notes |
|---|---|
| CASE_UPDATED variants | `CASE_UPDATED` exists only as the `attach_entity` fallback for unmapped edge types; the doc-22 field-level update events are unimplemented |
| TASK_CREATED / TASK_COMPLETED | task objects not yet modeled |
| ACTION_SCHEDULED / ACTION_EXECUTED | scaffold executes inline; doc 22's `action.executed` needs the executor/outbox |
| FOLLOW_UP_SCHEDULED | cadence is computed, but no discrete scheduled event (doc 22 `followup.scheduled`) |
| HUMAN_APPROVAL_REJECTED | `HumanApproval.decision` supports `rejected`; no event emitted |
| CASE_STUCK_DETECTED | stuck sweep emits `scores.recomputed` + returns a queue; no discrete stuck event |
| CASE_CLOSED | closure is a `case.state_changed` to a final state; no dedicated event |
| LGGT_CERTIFICATE_PLACEHOLDER_CREATED | the placeholder emits `certainty.stamped` instead — rename or alias when LGGT lands |

## 2. Naming normalization needed (known debt)

Two conventions coexist: **UPPER_SNAKE** (Case Graph services, gate, voice CI)
and **dotted lowercase** (state machine, completion loop, documents, certainty
core — doc 22's style). Concrete collisions: `CASE_CREATED` vs `case.created`,
`PROMISE_BREACHED` vs `promise.breached`.

**Recommendation**: converge on **UPPER_SNAKE at the API boundary**
(`GET /audit-events`, SSE stream), with a mapping table applied at read time so
historical hash-chained rows are never rewritten (the chain is content-hashed —
renaming stored events would break `verify_chain`):

| Stored (lowercase) | API-normalized |
|---|---|
| `case.created` | `CASE_CREATED` |
| `case.state_changed` | `CASE_STATE_CHANGED` |
| `promise.breached` | `PROMISE_BREACHED` |
| `followup.sent` / `.suppressed` / `.exhausted` | `FOLLOW_UP_SENT` / `_SUPPRESSED` / `_EXHAUSTED` |
| `scores.recomputed` | `SCORES_RECOMPUTED` |
| `certainty.stamped` | `CERTAINTY_STAMPED` |
| `document.analysis_completed` / `.needs_rescan` | `DOCUMENT_ANALYSIS_COMPLETED` / `DOCUMENT_NEEDS_RESCAN` |
| `approval.requested` | `HUMAN_APPROVAL_REQUESTED` |

New emitters should write UPPER_SNAKE directly.

## 3. Hash-chain mechanics (append-only, tamper-evident)

`finalis/audit.py`:

- **Append-only**: `AuditLog` exposes `append`, `events` (filtered read),
  `verify_chain`, `__len__` — *"No update/delete API exists."*
- **Chain**: each event stores `hash_prev` (previous event's `hash_self`;
  genesis is 64 zeros) and `hash_self = sha256(canonical_json({id, event_type,
  actor, case_id, payload, hash_prev}))` with sorted keys.
- **Verification**: `verify_chain()` re-derives every digest and link;
  any payload mutation is detected
  (`tests/test_autonomy_audit.py::TestAuditChain::test_tamper_detection` flips
  a payload value and asserts the chain fails; `test_chain_links` pins the
  genesis link). `verify_chain()` is additionally asserted at the end of the
  E2E lifecycle, the MVP flow, voice engine, conversation intelligence, and
  state-machine suites. Doc 22 exposes this as
  `GET /audit-events/verify?case_id=`.

## 4. Actor attribution

Every event carries `actor` — in the scaffold a single string with the values
`"system"` (clock/sweep-driven), `"ai"` (agent decisions), `"human"`
(approvals, overrides), or a source label such as `"client"`
(`MissingInfoService.resolve(source=...)`). The doc-04 production schema splits
this into `actor_type` + `actor_id` (which specific user/agent); the scaffold's
single string collapses both — split it when persistence lands, keeping the
same append signature.

## 5. Retention & PII posture

The audit log is **long-lived** (it is the source of truth for timelines,
score reproduction, and future LGGT certification) and therefore
**PII-minimized by construction**: payloads carry ids, field *keys*, enum
reasons, and scores — e.g. `{"items": ["address", ...]}`,
`{"action": ..., "outcome": ..., "reason": ...}`, `{"what": ..., "score": ...}`
— never message bodies, transcripts, or extracted personal values (those live
in their own stores referenced by id, with their own retention/erasure rules).
Keep this discipline for new emitters: if a payload needs content, store a
reference, not the content.
