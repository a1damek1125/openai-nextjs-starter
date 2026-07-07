# Finalis Case Graph + Completion Loop — Founder / CTO Report

**Date**: 2026-07-07 · **Branch**: `claude/finalis-case-graph-completion-loop`
**Test command**: `python3 -m pytest tests/ -q` → **160 passed** (20 case-graph service
tests incl. the 23-step E2E lifecycle; 11 conversation-intelligence tests; the rest are the
core/voice suites this module extends).

Wording: **Implemented and tested** = passing tests · **Scaffolded** = minimal code ·
**Mocked** = mocks behind production interfaces · **Designed** = docs only.

---

## The 23 direct answers

**1. What was implemented?**
The service layer over the already-tested core: `CaseGraphService` (create case, attach
typed-edge entities, tenant-guarded graph read with timeline), `MissingInfoService`
(HVAC required-info profile with Polish recommended questions, channel, auto_allowed;
detection, resolution, blockers), `PromiseTrackerService` (OPEN/DUE_SOON/OVERDUE/BREACHED/
FULFILLED with θ_breach scoring), `NextBestActionService` (deterministic utility over
candidate actions), `ActionGateService` (**ALLOW / BLOCK / REQUIRE_HUMAN_APPROVAL /
ABSTAIN_MISSING_DATA**, every decision audited with an audit_id), `CompletionLoopService.
run_case` (the per-case tick with duplicate-follow-up prevention and the leave-with-a-next-
action invariant asserted). Plus the **state machine upgrade to this spec**: new edges
(71 total in `state-machine.finalis.json` v1.1), **RECOVERY_LATER promoted to a final
state**, and the **final-state human-override rule** (no exit from WON/LOST/COMPLETED/
ABANDONED/RECOVERY_LATER without `human_override`, with the single documented exception of
the Completion Loop's scheduled RECOVERY_LATER wake). Plus the **Conversation Intelligence
Engine** (see 9 below). `Party` entity added; `Case` gained `stuck_score`/`escalation_score`.

**2. What was only documented?** Persistence (PostgreSQL schema/RLS), the REST API
(contracts designed, no server), Task/Action as first-class entities (tasks are dicts,
actions are audit-recorded gate decisions in the scaffold), DecisionBrief entity (audit
event only), observability metrics, PlaybookVersion.

**3. What is mocked?** Nothing in this module needs mocks — it is pure domain logic. The
inputs that would come from Voice/OCR (extraction payloads, documents) are fixtures in
tests; the engines behind them are mocked in their own modules.

**4. What is missing?** DB + API + the entity gaps in (2); event-name normalization (two
conventions coexist — UPPER_SNAKE and dotted lowercase; convergence mapping documented in
audit-events.md); NBA scoring for the full candidate list (6 of 14 candidates scored, the
rest are gate-registered but not utility-ranked yet).

**5. Does Case Graph work?** **Yes — implemented and tested**: create, attach (party/
evidence/typed edges), read graph with nodes/edges/missing/promises/timeline.

**6. Does the state machine work?** **Yes — implemented and tested**: 17 states, 71 edges,
2 global edges, reachability BFS, exhaustive terminal rejection, property walks, JSON↔code
consistency.

**7. Are illegal transitions blocked?** **Yes — tested**, including the new rule: WON →
SCHEDULED without override raises `IllegalTransition`; with `human_override=True` it
succeeds; `scheduled_wake` unlocks only RECOVERY_LATER→FOLLOW_UP_ACTIVE and nothing else.

**8. Does Completion Loop run?** **Yes — implemented and tested**: per-case tick evaluates
promises, sweeps stuck score, selects NBA, gates it, sends at most one follow-up
(duplicate-prevention tested), never silently drops a case (final states are explicitly
`skipped: final_state`; active cases must leave with a next action + due time — asserted).

**9. Does Promise Tracker work?** **Yes — tested**: DUE_SOON (6h window), OVERDUE
(low-impact stays open — 0.24 < θ 0.3), BREACHED (0.54 ≥ θ), FULFILLED; audit events for
each.

**10. Does Missing Information Hunter work?** **Yes — tested**: HVAC profile detection
against known facts, no duplicate detection, blockers gate QUOTE_PREPARATION, resolution
unblocks and bumps progress.

**11. Does Next Best Action work?** **Yes — tested** for the scored candidate set
(photo request/missing info/quote task/follow-up/human review/wait) with the doc-05 utility
formula; deterministic, no fake ML.

**12. Does Follow-up scheduling work?** **Yes — tested**: allowed follow-up sent once;
repeat within cooldown suppressed/rate-limited (FOLLOW_UP_RATE_LIMITED); quiet hours,
opt-out, max-attempts and exhaustion→RECOVERY_LATER inherited from the tested core loop.

**13. Does ActionGate work?** **Yes — tested**, all four outcomes: ALLOW (low-risk at L3+),
BLOCK (opt-out), REQUIRE_HUMAN_APPROVAL (high-risk incl. close_won/sign_contract/
take_payment even at L5; frozen autonomy; unknown actions default conservative),
ABSTAIN_MISSING_DATA (confidence < 0.5). Every decision writes an audit event and returns
its audit_id — the LGGT ProofGate hook.

**14. Are audit events written?** **Yes — tested**: hash-chained, tamper-evident,
verify_chain() green in every test; the 23-step E2E ends with ≥15 timeline events and
exactly 7 state-change audits.

**15. Is tenant isolation implemented or only designed?** **Service-level: implemented and
tested** (cross-tenant graph read AND cross-tenant entity attach both raise
PermissionError). **DB-level RLS: designed** (docs 04/37).

**16. Is this enterprise-ready?** **No — not production-ready.** The logic core is verified;
persistence, API, RLS, observability, and the enterprise gap list (doc 37) remain.

**17. What blocks production?** Persistence + API + RLS + observability + the doc-37 top-12
gaps. **18. What blocks MVP?** Only the persistence + API wrap around this tested logic
(Sprint 1 of doc 35) and one real channel.

**19. How should Voice Engine connect?** Via `ConversationAnalysis.case_update_payload`
(implemented): intent/facts/missing/promises/tasks/next_action → `CaseGraphService`
attach + `MissingInfoService.detect` + promise creation + `CompletionLoopService.run_case`.
The 23-step E2E starts exactly from a voice extraction payload.

**20. How should OCR Engine connect?** `Document`/`ExtractedField` with confidences →
attach as DOCUMENT edge → the confidence gate (07) resolves MissingItems
(installation_photo) and feeds evidence-bound facts; DocRisk feeds escalation.

**21. How should WebScout connect?** `Source` records attach as EVIDENCE edges; SourceTrust
feeds Evidence Confidence; research notes feed Offer Comparator and DecisionBriefs.

**22. Should LGGT be integrated now or later?** **Later, per Option B (docs 32/44) — and
Phase 1 is already done**: `CertaintyCoreAdapter`+`NullAdapter`+`Fact`+`Certificate` with
audit_id are implemented and tested here; `ActionGateService.evaluate` is the marked
ProofGate integration point. Phase 2 certifies transitions/follow-ups/missing-info validity.

**23. What exact next sprint should be done?**
Persistence + API sprint: PostgreSQL schema from doc 04 (+ Task/Action/DecisionBrief/
PlaybookVersion entities), FastAPI implementing `api-contracts.md` (incl.
`/cases/{id}/transition` with override flags, `/completion-loop/run-case/{id}`,
`/action-gate/evaluate`), RLS, and the existing 160 tests + new API contract tests as the
CI gate.

---

## Conversation Intelligence Engine (folded into this branch)

**Implemented and tested (11 tests)**: diarized time-stamped segments → speaker-attributed
transcript, facts with per-fact `EvidenceReference{call_segment, start/end ms, speaker,
snippet}`, promises, missing items, objections, risks, tasks, key decisions, summary, next
action, human-review flag, case-update payload, audit events. **The acceptance rule is
code**: a fact is *certain* only with a supporting segment AND `min(ASR, diarization)
confidence ≥ 0.6` — tested including the min-not-mean case (0.9/0.55 → uncertain) and the
critical-vs-non-critical review trigger. **Mocked/Designed**: the audio pipeline itself.
Production stack (research-verified): WhisperX (BSD-2) + faster-whisper large-v3 +
**pyannote community-1** (MIT code, CC-BY-4.0 gated weights) batch pipeline; streaming =
provisional (Sortformer v2, 4-speaker cap) with authoritative batch re-pass; **DiariZen
weights are CC-BY-NC — excluded**; Voxtral/Qwen3-Omni analysis lanes have **no Polish** —
PL analysis stays transcript-text-based. Details: `docs/finalis-ai/voice/conversation-intelligence.md`.
