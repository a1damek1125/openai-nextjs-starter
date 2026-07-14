# Finalis AI — Voice Verification & Test Plan (QA Audit)

**Status: DOCUMENTED ONLY / ARCHITECTURE SPECIFIED. No executable code, no fixtures, no measurements exist in this repository. Every latency/accuracy number in docs 06/07/08 is a target or a cited external result — none has been measured on Finalis itself.**

> Companion to `06-voice-architecture.md` (pipeline + targets) and `15-evaluation-lab.md`
> (metric definitions). This document specifies *how the voice worker will be verified once it
> exists*, and what must be built to make the first measurement possible.

---

## 1. Voice Evaluation Harness — design

Two stages, deliberately ordered so that most conversational logic is verified **before any
audio infrastructure exists**.

### Stage A — Transcript-driven simulation (no real audio)

The cascaded architecture (`06` §1: STT → LLM → TTS) means everything between STT-out and
TTS-in is a **text-to-text system**: intent/slot detection, dialogue policy, tool calls,
repair phrases, handoff decisions, and all post-call extraction (`06` §5). All of that is
testable by feeding scripted transcripts through the pipeline with STT and TTS mocked.

- **Fixture format**: a YAML/JSON "conversation script" per scenario — a sequence of user
  turns (final transcript text + optional interim-transcript sequence + timing annotations
  like `pause_ms`, `barge_in_at_token`), plus gold labels: expected intent per turn, expected
  slot values, expected promises, expected `MissingItem`s, expected end state
  (resolved / scheduled / warm-handoff), expected task proposals.
- **Simulator**: replays the script against the Voice Worker with a **mock STT** (emits the
  scripted interim + final transcripts on a configurable clock) and a **mock TTS** (records
  what would be spoken and when, including stop/flush events for barge-in). Latency is
  *injected*, not measured, at this stage — the simulator asserts *behavioral* correctness
  (right words, right tools, right stops) and that the pipeline's internal deadlines/fallback
  rules fire (`06` §3 fallback-when-slow).
- **Post-call assertions**: after each simulated call, assert the five mandatory post-call
  outputs (`06` §5): summary, `Promise` rows, `MissingItem` rows, next-action proposal,
  `ExtractedField` updates with confidence — each with evidence refs to transcript timestamps.
- LiveKit Agents ships a simulation/testing framework (`06` §1) — evaluate it as the base for
  this stage before building bespoke tooling.

### Stage B — Live-audio stage (staging environment)

Only after Stage A is green: run the same scenario scripts as **synthesized or recorded
audio** through the real transport (LiveKit Agents or Pipecat per `06` §1) on staging.

- Audio fixtures: TTS-rendered "client" audio per scenario, plus recorded human variants for
  accent/noise/emotion scenarios (synthetic voices cannot represent accents and anger
  faithfully — human recordings are mandatory for scenarios 5, 7).
- Measures the real timing metrics: TTFA percentiles, barge-in stop latency, end-of-utterance
  detection quality — using Pipecat's built-in TTFA metrics or LiveKit turn-timing hooks
  (`06` §1) feeding `Call` turn timings exactly as `15` §2.1 expects.
- A "caller bot" drives the audio side deterministically (plays fixture audio, interrupts on
  cue, goes silent on cue) so runs are repeatable.

---

## 2. The 13 mandated test scenarios

Each scenario runs in Stage A (behavioral) and Stage B (timed). "Doc rule" cites the
specification the expected behavior comes from.

### S1 — Simple booking
- **Setup**: cooperative caller, one service request, gives address/date/time when asked.
- **Expected behavior**: short-answer policy (1–2 sentences + one question, `06` §2); explicit
  confirmation of critical slots (address, date — `06` §4 repair/confirm rule); calendar tool
  call; clean end state `scheduled`.
- **Pass criteria**: all required slots filled and confirmed; booking tool called with correct
  args; call end reason = completion; post-call summary + next action produced (`06` §5).
- **Feeds metrics**: TTFA P50/P95, tool-augmented TTFA, intent accuracy, slot accuracy, call
  completion rate, task creation accuracy.

### S2 — Client interrupts the AI mid-sentence
- **Setup**: while the agent is speaking a multi-sentence answer, the client starts talking.
- **Expected behavior**: barge-in — VAD detects speech during TTS → immediately stop TTS,
  flush the queued response, re-listen; `barge_in_events` tracked on the `Call` (`06` §4).
- **Pass criteria**: TTS stop ≤ 200 ms after detected speech onset (`06` §3, Stage B); flushed
  content is not spoken later; the interrupting utterance is fully processed; event logged.
- **Feeds**: barge-in stop latency, barge-in correctness (precision), interruption recovery.

### S3 — Client changes their mind mid-sentence
- **Setup**: "Book me for Thursday— actually no, make it Tuesday morning."
- **Expected behavior**: slot-filling is revisable; the last confirmed value wins (`06` §4
  Corrections rule); agent confirms the *final* value.
- **Pass criteria**: booked slot = Tuesday; Thursday nowhere in the confirmation, booking, or
  summary; repair-confirmed slot counts correct only if final value matches gold (`15` §2.2).
- **Feeds**: slot-filling accuracy (critical slots), interruption recovery, intent accuracy.

### S4 — Client gives wrong info, then corrects on a later turn
- **Setup**: gives address "Oak Street 15"; three turns later: "sorry, it's 50, not 15."
- **Expected behavior**: correction accepted at any time (`06` §4); targeted repair phrasing
  if ASR-ambiguous ("was that *fifteen* or *fifty*?" — `06` §4); explicit re-confirmation of
  the critical slot.
- **Pass criteria**: final stored value 50; correction reflected in `ExtractedField` update
  and summary; no stale value in any post-call output.
- **Feeds**: slot-filling accuracy, repair-behavior correctness (counts under slot accuracy).

### S5 — Strong accent
- **Setup**: recorded human audio with a strong regional/non-native accent (Stage B only;
  Stage A stand-in: transcripts with realistic ASR error patterns injected).
- **Expected behavior**: on ASR uncertainty, targeted repair + explicit confirmation of
  critical slots rather than guessing (`06` §4); if confidence stays low, offer callback or
  human handoff rather than proceeding on garbage (`06` §3 fallback rules).
- **Pass criteria**: WER on accented set ≤ 20% (`15` §2.1 aspirational); zero critical slots
  committed without explicit confirmation when ASR confidence was low.
- **Feeds**: ASR WER (accented cohort), slot accuracy, handoff correctness.

### S6 — Mixed languages mid-call
- **Setup**: client starts in English, switches to Polish mid-call.
- **Expected behavior**: language detected per utterance; STT/TTS voice switched; respond in
  the client's language mid-call; `languages` stored on the `Call` (`06` §4 Language switching).
- **Pass criteria**: response language matches the client's last-used language per turn;
  `Call.languages` contains both; slot values survive the switch.
- **Feeds**: turn-taking accuracy, intent/slot accuracy per language cohort, ASR WER.

### S7 — Angry client
- **Setup**: escalating frustration, raised voice, complaint about a previous job.
- **Expected behavior**: sentiment feeds `ClientEmotion` in `EscalationScore` (`06` §4);
  warm transfer on anger/distress with a live summary passed to the human (`06` §4 Human
  handoff); no argumentative or defensive generation.
- **Pass criteria**: escalation raised (recall — the dangerous error is missing it, `15`
  §2.9); handoff summary contains the complaint, case ref, and emotional state; no promise
  made that policy forbids.
- **Feeds**: escalation recall, handoff correctness, summary quality, hallucination rate.

### S8 — 10-second silence mid-call
- **Setup**: client goes silent for 10 s mid-negotiation (thinking / distracted).
- **Expected behavior**: semantic end-of-utterance detection, not a fixed VAD timeout — don't
  interrupt a client mid-thought (`06` §4 Silence/pause handling); never leave dead air
  > ~1.5 s without a backchannel once it *is* the agent's turn (`06` §3); a gentle check-in
  ("are you still there?") after a prolonged silence, not a hang-up.
- **Pass criteria**: no premature barge-in on the thinking pause (counts against barge-in
  correctness); check-in emitted within a configured window; call not dropped; if client is
  gone, clean end state with callback next-action.
- **Feeds**: turn-taking accuracy, barge-in correctness (false-trigger rate), call completion.

### S9 — Out-of-scope question
- **Setup**: client asks something outside the playbook ("can you do my taxes?" or a legal
  question).
- **Expected behavior**: honesty about limits (`06` §6); no fabricated capability or advice;
  abstain below `θ_conf` (`05` §6 via `15` §2.8); offer what the business *can* do or a human.
- **Pass criteria**: zero unsupported claims; correct out-of-scope intent label; graceful
  redirect or handoff; nothing invented enters the summary or case fields.
- **Feeds**: intent accuracy, hallucination rate, handoff correctness.

### S10 — Client asks for a human
- **Setup**: "Can I just talk to a person?"
- **Expected behavior**: warm transfer on explicit request — unconditional, not scored
  (`06` §4: handoff "on explicit request"); live summary passed to the human.
- **Pass criteria**: handoff initiated on the first request (no deflection loop); summary
  transferred; end reason = warm-handoff (counts as completion, `15` §2.1).
- **Feeds**: handoff correctness (hard pass/fail), escalation recall, call completion rate.

### S11 — "I'll send the photos later" promise
- **Setup**: client promises to send boiler photos by tomorrow evening.
- **Expected behavior**: post-call promise extraction → `Promise` row (who / what / by when)
  with evidence ref to the transcript timestamp (`06` §5.2); feeds the Completion Loop (`09`).
- **Pass criteria**: exactly one `Promise` row; correct promisor (client), artifact (photos),
  deadline (normalized datetime); evidence timestamp lands on the actual utterance.
- **Feeds**: promise extraction accuracy, task creation accuracy.

### S12 — Client asks about a previous conversation
- **Setup**: "Last week your colleague said the part was ordered — is it in?"
- **Expected behavior**: prefetched case context (`06` §2 — Case Graph fetch into turn
  context); answer only from case state with evidence; if case history doesn't contain it,
  say so and offer to check — never confabulate a prior conversation (`06` §6 honesty,
  `15` §2.8 unsupported-claim rule).
- **Pass criteria**: answer consistent with fixture case state; zero fabricated references to
  prior calls; if info absent → explicit "I don't have that" + follow-up task.
- **Feeds**: hallucination rate (primary), tool-augmented TTFA, summary quality.

### S13 — Info that must become a task
- **Setup**: client mentions in passing: "by the way, the outdoor unit is making a grinding
  noise" during a billing call.
- **Expected behavior**: post-call next-action generation → proposal into the NBA utility
  calc (`06` §5.4); `MissingItem`/field updates as applicable (`06` §5.3, §5.5); applied only
  through the Orchestrator autonomy gate — nothing client-facing without it (`06` §5).
- **Pass criteria**: a task/next-action proposal exists referencing the grinding noise with a
  transcript evidence ref; it is a *proposal* (autonomy gate respected), not an executed
  action; the original billing intent is still completed.
- **Feeds**: task creation accuracy, missing-info extraction, intent accuracy (multi-intent).

---

## 3. Metrics table

All targets below are **doc-06/15 targets, not measurements** — nothing has run.

| Metric | Measurement method | Pass threshold (source) | Fed by scenarios |
|---|---|---|---|
| **P50 first-response latency (TTFA)** | Stage B: `end_of_utterance → first_tts_frame` per turn, percentile over turns (`15` §2.1) | **≤ 800 ms** (gate, `06` §3) | S1–S13 (all timed turns) |
| **P95 first-response latency** | Same distribution, P95 | **≤ 1500 ms** (gate, `06` §3); repeated breach → shorten/scripted turns | all |
| **Turn-taking accuracy** | Human-label a sample of turn transitions: {correct take, premature interrupt, missed turn-end}; report share correct | ≥ 0.9 correct transitions (engineering goal — no doc-fixed number; pause discipline is a known weak point per `06` §4 / Full-Duplex-Bench) | S8, S2, S3 |
| **Barge-in success (stop latency)** | Stage B: `barge_in_onset → tts_stop` per event | **≤ 200 ms** (`06` §3) | S2 |
| **Barge-in correctness** | Human-label sampled barge-in events {true-interrupt, false-trigger, missed} → precision/recall (`15` §2.1) | precision ≥ 0.9, recall ≥ 0.85 (asp.) | S2, S8 |
| **Interruption recovery** | After barge-in/correction: does the dialogue resume coherently with the corrected state and no re-utterance of flushed content? Scripted assertions + LLM-judge with human calibration (`15` §3.3) | ≥ 0.9 coherent recoveries (engineering goal) | S2, S3, S4 |
| **Intent accuracy** | Confusion matrix vs gold labels on the scenario set + prod sample (`15` §2.2) | accuracy ≥ 92%, macro-F1 ≥ 0.85 (asp.) | all, esp. S9, S13 |
| **Slot-filling accuracy** | Per-slot normalized match vs gold; critical slots (address, date, price, amount) separate (`15` §2.2) | critical ≥ 95% exact, others ≥ 88% (asp.) | S1, S3, S4, S5, S6 |
| **Promise extraction accuracy** | Extracted `Promise` rows vs gold (promisor, artifact, deadline); P/R/F1 | F1 ≥ 0.9 on scripted set (engineering goal; no doc-fixed number) | S11 |
| **Missing-info extraction accuracy** | `MissingItem` rows vs gold, precision/recall (`15` §2.5) | recall ≥ 0.90, precision ≥ 0.85 (asp.) | S13, S1 |
| **Summary quality** | LLM-judge rubric (coverage of decisions/promises/emotion, no invented content) calibrated against weekly human labels (`15` §3.3) | judge score ≥ threshold set at calibration; human agreement tracked, human label is ground truth | S7, S11, S12, all |
| **Handoff correctness** | Scripted assertion: handoff triggered on {explicit request, anger, `EscalationScore ≥ θ_escalate`, safety}; summary payload present (`06` §4) | 100% on explicit-request and hard-override cases (hard gate per `15` §2.9); escalation recall ≥ 0.95 (gate) | S7, S10, S5 |
| **Hallucination rate** | Unsupported-claim rate: claims lacking valid `EvidenceReference` or asserting certainty below `θ_conf`; Quality Worker per-event + weekly human spot-check (`15` §2.8) | ≤ 1% client-facing (gate); 0 on legal/financial (hard gate) | S9, S12, all |
| **Task creation accuracy** | Proposed next-actions/tasks vs gold per scenario; P/R; autonomy-gate compliance checked on every proposal | F1 ≥ 0.85 (engineering goal); 100% of client-facing actions gated (hard requirement, `06` §5) | S13, S11, S1 |
| **ASR WER** | Stage B sampled audio vs human reference transcript, (S+D+I)/N (`15` §2.1) | ≤ 12% overall, ≤ 20% accented/noisy (asp.) | S5, S6, S7 |

---

## 4. Implementation tasks: zero → measurable harness

Ordered; each unlocks the next. Today **none of these exist** — there is no `package.json`
script, no test directory, no fixture, no pipeline code in this repo.

1. **Transcript fixture format + the 13 scenario scripts** (Stage A fixtures). Define the
   YAML/JSON schema (turns, interims, timing annotations, gold labels) and author S1–S13.
   No dependencies; can start immediately. *Deliverable: fixtures + schema validator.*
2. **Extraction pipeline tests.** Implement/stub the post-call extraction chain (summary,
   promises, missing items, fields, next actions) and run it on fixture transcripts alone —
   this verifies `06` §5 outputs before any dialogue loop exists. *First real numbers:
   promise/missing-info/task extraction F1 on the scripted set.*
3. **Dialogue-loop simulator with mock STT/TTS + latency injection.** Turn-by-turn replay
   against the Voice Worker; mock STT emits interims/finals on a clock, mock TTS records
   speak/stop events. Inject configurable STT/LLM/TTS latencies to verify the deadline logic:
   filler phrase on soft-deadline breach, handoff offer on hard breach, no dead air > 1.5 s
   (`06` §3). *First behavioral pass/fail on all 13 scenarios.*
4. **Golden-set + regression wiring.** Freeze the scenario set as a versioned golden set
   (`15` §3.1/3.2); wire pass criteria as declarative gates in the eval harness (`15` §4.1)
   so scenario regressions block releases.
5. **Live pipeline on staging (LiveKit Agents or Pipecat — Phase-0 decision, `06` §1).**
   Stand up cascaded STT→LLM→TTS with real vendors, telephony loopback, caller-bot driving
   audio fixtures. Instrument TTFA (Pipecat built-in metrics / LiveKit timings) and barge-in
   stop latency into `Call` timings. *First real latency measurements — until this step, every
   ms number is a target.*
6. **Human-labeled samples.** Recorded accent/anger audio, human reference transcripts (WER),
   weekly labeling of barge-in events, summaries, and hallucination spot-checks (`15` §2.1,
   §2.8, §3.3) — the calibration layer for every LLM-judged metric.

---

## 5. Verdict

**Voice = DOCUMENTED ONLY.** The architecture (doc 06) is specific and testable, and the
Evaluation Lab (doc 15) defines the metrics — but zero lines of pipeline, harness, or fixture
code exist in this repository, and no latency or accuracy figure has ever been measured on
Finalis.

**Earliest measurable milestone**: tasks 1–2 above — the 13 transcript fixtures plus the
post-call extraction pipeline running on them. That yields the first honest numbers
(promise/missing-info/task extraction F1, summary quality vs gold) with **no audio stack, no
telephony, and no vendor accounts required**. Latency numbers (TTFA, barge-in ≤ 200 ms) cannot
be measured before task 5 (staging pipeline) and should not be quoted as anything but targets
until then.
