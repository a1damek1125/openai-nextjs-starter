# Finalis AI — Voice E2E Readiness Report

> Reviewer report on branch `claude/finalis-ai-enterprise-e2e-autofix` (scaffold: 102 passing
> tests). Companion to `06-voice-architecture.md` (pipeline + targets) and
> `28-voice-verification-and-test-plan.md` (verification harness design).

## Verdict

**Real-time voice = DESIGNED/PLANNED. Transcript-level conversation logic = Scaffolded and
tested.**

No real-time voice code exists in this repository: no audio transport, no STT/TTS
integration, no VAD, no turn-taking loop. What exists and passes is a **transcript-level
simulation** of the post-STT pipeline: the E2E test `test_e2e_hvac_quote_flow` in
`tests/test_e2e_mvp_flow.py` ingests a mock inbound call transcript fixture (`TRANSCRIPT`,
channel `phone`, 3 utterances) and drives the full
transcript → intake extraction → promise creation → missing-info → case/task flow at the
logic level. This is exactly Stage A of the two-stage plan in `28` §1 — deliberately ordered
so conversational logic is verified before any audio infrastructure exists — minus the
fixture breadth and the real extraction model.

## What the transcript simulation PROVES (tested, cite: `tests/test_e2e_mvp_flow.py::test_e2e_hvac_quote_flow`)

1. **Transcript ingestion contract** — a structured call transcript (`channel`,
   `utterances[]` with speaker/text) enters the system and produces a
   `contact.inbound_received` audit event bound to a new `Case`.
2. **Intent-level extraction contract (shape, not model)** — the fixture's `extracted`
   block (`client_name`, `phone`, `address`, `service_type`, `urgency`, `preferred_date`)
   is the exact output shape the Intake Worker must produce; the test asserts the
   quote-critical keys (`address`, `service_type`) are present before the case may advance.
3. **Promise extraction shape** — "I'll send photos later today" becomes a `Promise` row
   (promisor/what/due_at/importance/dependency_impact), which the completion loop later
   marks `fulfilled` when the photo arrives.
4. **Missing-info shape** — the call yields `MissingItem` rows (`room_photos` with
   `blocks_quote=True`, `device_info` without), MIS is computed (`mis_score == 1.0` while
   everything is missing), and the blocking item forces `WAITING_FOR_CLIENT_INFO`.
5. **Task / next-action creation** — the call produces
   `next_best_action = send_missing_info_request` with a due time; the follow-up is
   actually sent and audited (`followup.sent`).
6. **Autonomy gating of the inbound-answer action class** — `gate(case,
   "send_missing_info_request")` allows at L3, while the riskier
   `send_rule_covered_quote` is blocked pending human approval; the frozen-autonomy variant
   (`test_e2e_escalation_and_recovery_paths`) proves an escalated call drops to
   prepare-only (`effective_autonomy == 2`, `send_reminder` denied).

This validates the five mandatory post-call outputs of `06` §5 as **data contracts**
(summary-equivalent facts, Promise rows, MissingItem rows, next-action proposal,
ExtractedField updates with confidence) — with mocked extraction.

## What it does NOT prove

- **Latency** — there is no audio path, so nothing about TTFA is measurable. Not one
  latency number in this repo has been measured on Finalis.
- **Barge-in** — no TTS to interrupt, no VAD, no stop/flush semantics.
- **Turn-taking / end-of-utterance detection** — no interim transcripts, no semantic turn
  model, no silence handling.
- **ASR accuracy** — the "extraction" is a fixture; WER, accent robustness, and repair
  behavior on ASR ambiguity are untested.
- **Multilingual operation** — the fixture is monolingual; per-utterance language
  detection and mid-call STT/TTS switching (`06` §4) are unexercised.
- **Real human handoff** — warm transfer, live summary passing, and handoff timing exist
  only as design (`06` §4, `28` S7/S10).

## Targets restated — all UNMEASURED (`06` §3)

| Metric | Target | Status |
|---|---|---|
| P50 first response (TTFA, simple turn) | ≤ 800 ms | **UNMEASURED — no audio path** |
| P95 first response | ≤ 1500 ms (repeated breach → shorten/scripted turns) | UNMEASURED |
| Barge-in stop-speaking latency | ≤ 200 ms after detected speech onset | UNMEASURED |
| Perceived round trip | ≤ 1 s P50; > 2.5 s sustained → offer human handoff | UNMEASURED |
| Tool-augmented turn | ≤ 1200 ms P50, filler phrase on soft-deadline breach | UNMEASURED |
| Silence handling | semantic end-of-utterance, no dead air > ~1.5 s without backchannel | UNMEASURED |
| Multilingual switching | per-utterance detection, mid-call voice switch | UNTESTED |
| Fallback phrases | holding phrase on soft deadline; callback/handoff on hard deadline or low confidence | UNTESTED |

## Implementation backlog to reach measurable voice

1. **Transcript fixture suite** (`36` §2): 20 transcript fixtures paired with the 20 call
   scripts — JSON `turns[]` with timing + `asr_confidence`, golden labels for promises,
   missing items, summary facts, next actions. Ships first on the scaffold branch; CI runs
   without audio.
2. **Extraction pipeline vs golden labels**: replace the fixture `extracted` block with the
   real Intake Worker extraction and score it against the golden labels (intent accuracy,
   slot accuracy, promise/missing-info recall — `15` §2.2 gates).
3. **LiveKit/Pipecat staging pipeline with TTFA metrics**: stand up the cascaded
   STT→LLM→TTS pipeline (`06` §1) in staging; Pipecat 1.5 ships built-in TTFA metrics
   (exactly the instrumentation `15` needs), LiveKit provides turn-timing hooks — first
   real P50/P95 numbers come from here (Stage B of `28`).
4. **The 13-scenario harness** (`28` §2, S1–S13): each scenario in Stage A (behavioral,
   mock STT/TTS) then Stage B (timed, synthesized/recorded audio incl. mandatory human
   recordings for accent/anger scenarios S5/S7), driven by a deterministic caller bot.
5. **Latency regression gate in CI**: TTFA P50/P95 and barge-in stop latency asserted
   against the `06` §3 table on every release; breach fails the build the same way the
   logic tests do today.

Until items 3–5 exist, every voice latency claim must be labeled a target, not a property.
