# Finalis Conversation Intelligence Engine

Research verified 2026-07-07. Tags: `[VP]` = verified against a primary source
(repo LICENSE file, model card, paper), `[S]` = corroborated search snippet,
`[U]` = unverified — must be confirmed before GA.

Status labels follow the [acceptance rule](README.md#acceptance-rule):
**Implemented** = executable in `finalis/voice/conversation_intelligence.py`
and covered by `tests/test_conversation_intelligence.py` (11 passing tests;
160 passing repo-wide). **Designed** = specified here, with the plug-in point
already present in code.

## 1. Mission and honest status

After every call, the business must know — without listening to the
recording — what was said, by whom, what was promised, what is missing, what
is risky, and what happens next. The Conversation Intelligence Engine turns a
speaker-attributed, time-stamped transcript into that full structured call
record, with every fact bound to transcript evidence and every low-confidence
claim honestly downgraded instead of silently asserted.

**Honest status:**

- **Analysis layer — Implemented and tested at the transcript level.**
  `ConversationIntelligence.analyze()` consumes `DiarizedSegment` lists (the
  exact shape a WhisperX+pyannote pipeline emits: speaker label, text,
  `start_ms`/`end_ms`, per-segment ASR and diarization confidence, language,
  optional word timings) and produces the complete `ConversationAnalysis`
  record. 11 tests cover full analysis, the acceptance rule, evidence binding,
  the Case-Graph payload, audit events, handoff, and Polish-language segments.
- **Audio pipeline — Designed.** No audio is decoded in this repo. The
  production batch pipeline (WhisperX → pyannote → alignment, §4) replaces
  only the segment producer; everything downstream of `DiarizedSegment` is the
  code that is tested today. This mirrors the voice engine's
  `test_transcript` seam ([architecture.md](architecture.md)).
- **Extraction quality — rule-based MVP.** Facts/promises/objections come from
  `finalis/voice/extractor.py` pattern tables (EN + PL). Production replaces
  this with a local LLM behind the same interface (backlog CI-3, §9). The
  *contract* — statuses, confidences, evidence binding, the acceptance rule —
  is what the tests pin down, and it survives the extractor swap.

## 2. Required outputs after every call

Every call must yield the following 17 outputs. Each maps to a
`ConversationAnalysis` field (`finalis/voice/conversation_intelligence.py`);
examples are the actual values produced from the `CALL` fixture in
`tests/test_conversation_intelligence.py` (client asks for a heat-pump quote,
gives name "Jan Kowalski" and address "ul. Kwiatowa 12", promises photos
tomorrow).

| # | Required output | Field | Status | Example from the `CALL` fixture |
|---|---|---|---|---|
| 1 | Session/case linkage | `voice_session_id`, `case_id` | Implemented | `"vs-1"` / `"case-9"` (`test_case_update_payload_shape`) |
| 2 | Full speaker-attributed, timed transcript | `transcript` | Implemented (attribution from diarizer labels) | `{"speaker": "client", "text": "Hi, I'd like a quote…", "start_ms": 0, "end_ms": 3200, "asr_confidence": 0.95, "diar_confidence": 0.95, "language": "en"}` (`test_transcript_speaker_attributed_and_timed`) |
| 3 | Summary | `summary` | Implemented (template MVP; LLM in CI-3) | `"Client asked about heat pump quote. Missing: … Client promised to send photos (tomorrow)."` — test asserts `"promised to send photos" in a.summary` |
| 4 | Key decisions | `key_decisions` | Implemented | `["classified_intent:request_quote", "promise_recorded:send photos:tomorrow", "info_request_planned"]` |
| 5 | Intent | `intent` | Implemented | `"request_quote"` |
| 6 | Intent confidence | `intent_confidence` | Implemented | `> 0.8` asserted (`test_structured_outputs_complete`) |
| 7 | Facts with status + confidence | `facts` | Implemented | `{"key": "client_name", "value": "Jan Kowalski", "status": "certain", "confidence": 0.9, "critical": true, "evidence_ref_id": "…"}`; `{"client_name", "address"} <= fact_keys` asserted |
| 8 | Missing items (severity, what they block) | `missing_items` | Implemented | `{"type": "installation_photo", "severity": "high", "blocks": "quote_preparation"}` |
| 9 | Promises (who/what/when) | `promises` | Implemented | `{"who": "client", "what": "send photos", "due": "tomorrow", "confidence": …}` |
| 10 | Objections | `objections` | Implemented | `[]` for `CALL`; `{"type": "price_too_high"}` shape from the extractor |
| 11 | Risks | `risks` | Implemented | `[]` for `CALL`; `"low_confidence_critical_facts"` in the low-diar test, `"handoff:human_requested"` in the handoff test |
| 12 | Follow-up tasks | `tasks` | Implemented | `[{"type": "followup_if_no_photos", "due": "tomorrow", "channel": "sms_or_whatsapp"}]` (exact assertion) |
| 13 | Next action | `next_action` | Implemented | `{"type": "send_photo_request", "channel": "sms_or_whatsapp", "requires_human_approval": false}` |
| 14 | Human-review flag | `human_review_required` | Implemented | `False` for `CALL`; `True` on handoff or uncertain critical fact |
| 15 | Evidence references per fact | `evidence_references` | Implemented | `EvidenceReference(source_type="call_segment", locator={"start_ms": 3400, "end_ms": 8100, "speaker": "SPEAKER_00"}, snippet="My name is Jan Kowalski…")` (§6) |
| 16 | Case-Graph update payload | `case_update_payload` | Implemented | see §7 |
| 17 | Audit events (hash-chained) | `audit_event_types` + `AuditLog` writes | Implemented | `CONVERSATION_ANALYZED`, `EVIDENCE_CREATED`, `MISSING_INFO_DETECTED`, `PROMISE_CREATED` all asserted, plus `audit.verify_chain()` (`test_audit_events_written`) |

Everything in this table is Implemented *at the transcript level*: the inputs
are fixture `DiarizedSegment`s, not decoded audio. The audio producer is
Designed (§4).

## 3. The acceptance rule as code

From the module docstring of `finalis/voice/conversation_intelligence.py`:

> *No critical fact may be written as certain unless it is supported by a
> transcript segment AND min(ASR confidence, diarization confidence) is
> sufficient — otherwise it is marked uncertain/unverified for human review.*

The enforcement is small enough to quote in full:

```python
CERTAIN_MIN_CONF = 0.6      # joint ASR×diar floor for "certain" facts

# in analyze():
joint_conf = min(seg.asr_confidence, seg.diar_confidence)

# in _bind_evidence():
if pair is None:
    status, ref_id = "uncertain", None   # no segment → not certain
else:
    ...
    joint = min(fv.confidence, utt.confidence)
    status = "certain" if joint >= CERTAIN_MIN_CONF else "uncertain"
```

Three properties, each pinned by a test in
`tests/test_conversation_intelligence.py::TestAcceptanceRule`:

1. **Joint confidence is `min(ASR, diar)` — NOT the mean.**
   `test_joint_confidence_threshold_is_min_not_mean` feeds a segment with
   `asr=0.9, diar=0.55`: the mean would be 0.725 (above threshold), but
   `min = 0.55 < 0.6`, so the address fact is asserted `"uncertain"`. The test
   also asserts `CERTAIN_MIN_CONF == 0.6` so the threshold can't drift
   silently. Rationale: a perfectly transcribed sentence attributed to the
   wrong speaker is *not* a reliable fact — averaging would let one strong
   signal launder the weak one.
2. **Uncertain critical facts force human review.**
   `test_low_diarization_confidence_downgrades_fact`: address with `diar=0.4`
   → `status == "uncertain"`, `human_review_required is True`, and
   `"low_confidence_critical_facts"` appears in `risks`. Critical keys are
   `{"address", "client_name"}` (`_bind_evidence`). Symmetrically,
   `test_low_asr_confidence_downgrades_fact` proves `asr=0.45, diar=0.95`
   downgrades the name.
3. **Non-critical uncertainty does NOT force review.**
   `test_noncritical_uncertain_fact_does_not_force_review`: an ASR-flagged
   device brand ("Vissmann", `uncertain_terms`) is `"uncertain"` and
   `critical is False`, and `human_review_required is False`. Uncertainty is
   recorded honestly without turning every fuzzy brand name into a human
   escalation — review triggers are `handoff_triggers` or
   *(uncertain AND critical)*, exactly as coded in `analyze()`:

```python
human_review = bool(u.handoff_triggers) or any(
    f["status"] == "uncertain" and f["critical"] for f in facts)
```

Upstream, the extractor adds a second honesty layer: ASR-uncertain terms cap
field confidence at `UNCERTAIN_CONFIDENCE_CEILING = 0.5`
(`finalis/voice/extractor.py`), so a mumbled value can never reach the 0.6
certainty floor regardless of diarization quality.

## 4. Pipeline architecture (Designed)

### Batch pipeline (authoritative)

```
recorded call audio (per-tenant object store, consent-gated)
        │
        ▼
WhisperX v3.8.6 (BSD-2-Clause) [VP]
  ├─ faster-whisper large-v3 batched ASR (~70x realtime on GPU,
  │    batch-size dependent) [VP]
  ├─ integrated VAD segmentation
  └─ wav2vec2 forced alignment → word-level timestamps
       (DE/ES/EN alignment models bundled; PL via a HF wav2vec2
        model — quality [U], validated in CI-2)
        │
        ▼
pyannote speaker-diarization-community-1 (pyannote-audio v4.0.7)
  code MIT [VP]; pipeline weights CC-BY-4.0 but HF-GATED [S] — see note
        │
        ▼
speaker–word assignment (WhisperX assign_word_speakers)
        │
        ▼
DiarizedSegment[] ──► ConversationIntelligence.analyze()   ← Implemented seam
                        (speaker, text, start_ms/end_ms,
                         asr_confidence, diar_confidence, language, words)
        │
        ▼
analysis layer: text-LLM over the speaker-attributed transcript (ALL langs,
  incl. PL) — CI-3; optional Voxtral Mini 3B direct-audio lane for
  EN/DE/ES calls ≤40 min (structured summaries + function calling) [S]
        │
        ▼
ConversationAnalysis → Case Graph + AuditLog + human-review queue
```

**pyannote HF-gating note.** The community-1 *code* is MIT, but the pipeline
*weights* are gated on Hugging Face: they require a token and accepted terms
[S]. Bake the weights into the worker image at build time so production has no
runtime Hugging Face dependency (and no token in the serving path).
community-1 substantially improves on 3.1 (whose published DERs were ~21.7%
DIHARD-III / ~18.8% AMI / ~11.2% VoxConverse); it is the free tier of the paid
pyannoteAI *precision-2* hosted API (claimed 2.2x faster) — an upgrade path
that exists but is not required.

### Streaming pipeline (provisional live view)

Live calls get a **provisional** view: chunked faster-whisper ASR plus
**NVIDIA streaming Sortformer v2** (`diar_streaming_sortformer_4spk-v2`) —
the only serious open streaming diarizer today [S] — or diart (pyannote's
streaming sibling project) as an alternative. Constraints stated honestly:

- Sortformer v2 has a **hard 4-speaker cap** (fine for our 2-party calls);
- weights on the main checkpoint are CC-BY-4.0, but **at least one variant is
  CC-BY-NC-SA — verify the exact checkpoint license before deploying** [S];
- streaming diarization quality is below batch quality.

Therefore the rule is: **the streaming output is provisional and is never
written to the Case Graph as fact; the batch re-pass is authoritative.** The
live view feeds the operator UI and the in-call dialogue manager only; after
the call ends, the batch pipeline reprocesses the full recording and its
output is what `analyze()` commits.

### License matrix

| Component | Role | Code license | Weights license | Commercial self-host | Tag |
|---|---|---|---|---|---|
| WhisperX v3.8.6 | Batch ASR + alignment orchestration | **BSD-2-Clause** (not BSD-4; actively maintained, ~23k stars) | uses faster-whisper (MIT) + wav2vec2 alignment models (per-model) | Yes | `[VP]` |
| faster-whisper large-v3 | ASR backend | MIT | MIT `[U]` | Yes | `[S]` |
| pyannote community-1 | Batch diarization (PRIMARY) | MIT (pyannote-audio v4.0.7) | CC-BY-4.0, **HF-gated** — bake into image | Yes, with attribution | `[VP]` code / `[S]` weights |
| NVIDIA streaming Sortformer v2 | Streaming diarization (FALLBACK/live) | NeMo Apache-2.0 | CC-BY-4.0 on main; **≥1 variant CC-BY-NC-SA — verify checkpoint** | Yes, checkpoint-dependent | `[S]` |
| DiariZen (BUT) | — | — | **CC-BY-NC-4.0 — NO commercial use** | **NO — AVOID in product.** Open diarization SOTA (~13.3% DER); permitted for internal benchmarking only | `[S]` |
| Voxtral Mini 3B | Direct-audio analysis (EN/DE/ES fallback) | Apache-2.0 | Apache-2.0 | Yes — **no Polish** | `[S]` |
| Qwen3-Omni 30B-A3B | Future video-call analysis (R&D) | Apache-2.0 | Apache-2.0 | Yes — PL not in 19 speech-input langs | `[S]` |
| MOSS Transcribe Diarize / SoulX-Transcriber / Speaker-Reasoner / MOSS-Audio | R&D watchlist | see §8 | see §8 | see §8 | `[S]`/`[VP]` |

**The DiariZen NC trap** deserves its own sentence: it is the best open
diarization result on paper, and its weights license forbids exactly the use
we need. It stays on the benchmark bench, never in the product.

**Hardware honesty:** WhisperX + pyannote need a GPU (8–16 GB VRAM for
large-v3 + community-1). Far-field and overlapping-speech DER is still
10–20% across the field — which is precisely why the acceptance rule keys
certainty on diarization confidence rather than assuming diarization is
solved. Polish is the weak spot of every audio-LLM in the matrix; PL analysis
stays text-transcript-based (§8, CI-2/CI-3).

## 5. Speaker-role mapping

`analyze()` accepts an explicit `speaker_roles` map
(`{"SPEAKER_00": "client", "SPEAKER_01": "ai"}`). **In production the gateway
always provides this map** — the AI leg of the call is known to the system
that placed or answered it, so role attribution is metadata, not inference.

Without a map, the scaffold's `_infer_roles()` is deliberately conservative:
it maps every diarized speaker to `"client"`. Stated honestly, straight from
the code comment:

```python
# Without a gateway role map, everyone defaults to client — the AI leg
# is always known in production, so this default is conservative.
```

This is a limitation, not a feature: content-based role inference (greeting
detection, channel energy) is intentionally *not* implemented, because
guessing which speaker is the AI risks attributing the AI's words to the
client — a worse failure than processing the AI's utterances as client
speech (the extractor only acts on `speaker == "client"` utterances, so the
conservative default over-includes rather than fabricates attribution). The
fix is contractual: the gateway role map is a required production input.

## 6. Evidence binding

Every extracted fact carries an `EvidenceReference`
(`finalis/models.py`) pointing at the exact transcript segment it came from:

```python
EvidenceReference(
    source_type="call_segment",
    source_id=session_id,                      # the voice session
    locator={"start_ms": seg.start_ms, "end_ms": seg.end_ms,
             "speaker": seg.speaker},
    snippet=seg.text[:160],
    confidence=min(fv.confidence, utt.confidence))
```

`test_every_fact_is_evidence_bound` proves the invariant: for every fact with
`status == "certain"`, `evidence_ref_id` is non-null, the referenced
`EvidenceReference` has `source_type == "call_segment"`, its locator contains
`start_ms` and `end_ms`, and the snippet is non-empty. A fact with no
resolvable segment cannot be certain (`pair is None → "uncertain"`,
`_bind_evidence`). Each `EvidenceReference` creation is also written to the
hash-chained audit log as an `EVIDENCE_CREATED` event
(`test_audit_events_written`). Anyone reviewing a case can jump from a fact to
the millisecond range of the recording that supports it.

## 7. Case Graph integration

`analyze()` emits a ready-to-consume `case_update_payload`:

```python
{
    "tenant_id": ...,            # from the engine (tenant-scoped)
    "case_id": ...,
    "intent": ..., "case_type": ...,
    "facts": [...],              # each with status/confidence/evidence_ref_id
    "missing_items": [...],      # {type, severity, blocks}
    "promises": [...],           # {who, what, due, confidence}
    "tasks": [...],
    "next_action": {...},
    "human_review_required": bool,
}
```

Shape pinned by `test_case_update_payload_shape` (tenant_id, case_id, intent,
promises, missing_items, next_action all asserted). Consumption path
(`finalis/case_services.py`, `finalis/completion_loop.py`):

- `CaseGraphService.attach_entity()` attaches the analysis and its
  `EvidenceReference`s to the `Case` graph;
- `missing_items` feed `MissingInfoService` (blockers surface via
  `open_blockers()`);
- `promises` feed `PromiseTrackerService.evaluate()` and
  `CompletionLoop.promise_check()` — the "photos tomorrow" promise becomes a
  tracked deadline with automatic follow-up;
- `next_action` + `human_review_required` feed `ActionGateService` /
  `NextBestActionService`, so an uncertain-critical-fact call can never
  auto-advance to `prepare_quote`;
- `CompletionLoopService.run_case()` drives the case forward until done —
  the engine's whole point is that a finished call immediately becomes
  completion-loop fuel rather than a recording nobody replays.

## 8. R&D watchlist

Models whose *architecture* points where we're going, but whose *languages*
don't cover where we are. Honest note up front: **every model below is
ZH/EN-centric; none covers Polish, our primary market.** They are watched,
not adopted.

| Model | What it is | License | Why watch / why not adopt |
|---|---|---|---|
| **MOSS Transcribe Diarize** (arXiv 2601.01554, OpenMOSS/MOSI.AI) | End-to-end speaker-attributed, timestamped transcription in one 4B LLM; 128k ctx ≈ 90 min of audio; cpCER 6.97% on the Chinese Podcast bench | Apache-2.0 reported `[S]` | **The architecture IS our product shape** — one model replacing the ASR→diar→align cascade. But it is Chinese-centric; PL/DE/ES quality is unverified. Watch closely; benchmark when a multilingual checkpoint appears. |
| **SoulX-Transcriber** (arXiv 2606.02400, Soul-AILab) | E2E diarization+ASR on Qwen3-Omni-30B | Apache-2.0 `[VP]` | ZH/EN only, ≤10-min clips — both disqualifying for our calls. Avoid. |
| **Speaker-Reasoner** (arXiv 2604.03074, ASLP-lab) | Agentic-reasoning speaker-attributed transcription | Apache-2.0 `[VP]` | ZH/EN; requires a custom vLLM build. R&D only. |
| **MOSS-Audio** (arXiv 2606.01802) | 4B/8B general audio-understanding foundation model; open SOTA on MMAU/MMAR/MMSU | Apache-2.0 | Candidate for the **analysis layer** (understanding, not transcription) — could eventually replace the text-LLM for direct-audio analysis, if multilingual coverage materializes. R&D. |

Related fallbacks already in the matrix (§4): Voxtral Mini 3B (direct-audio
analysis, EN/DE/ES only — **no Polish**) and Qwen3-Omni 30B-A3B (audio+video,
PL not listed). Consequence, stated plainly: **Polish analysis stays
text-transcript-based** — WhisperX+pyannote produce the transcript, a text
LLM (Qwen3-30B-A3B / Bielik-11B candidate, see
[open-source-stack.md](open-source-stack.md)) does the understanding. The
direct-audio lanes are an EN/DE/ES optimization, never the PL path.

## 9. Implementation backlog

| ID | Item | Scope | Exit criterion |
|---|---|---|---|
| **CI-1** | Wire the WhisperX+pyannote batch worker | GPU worker: recording → WhisperX v3.8.6 (faster-whisper large-v3, batched) → pyannote community-1 (weights baked into image, no runtime HF token) → word-speaker assignment → `DiarizedSegment[]` → `analyze()` | Real call audio flows end-to-end into the existing tested `ConversationAnalysis`; per-segment `asr_confidence`/`diar_confidence` populated from model outputs, not defaults |
| **CI-2** | PL alignment-model validation | Select and benchmark a HF wav2vec2 Polish alignment model for WhisperX (quality currently `[U]`); measure word-timestamp error vs DE/ES/EN bundled models | PL word timestamps accurate enough for evidence locators (start_ms/end_ms) and courtroom-grade snippet binding |
| **CI-3** | LLM analysis layer replacing the rule extractor | Local text-LLM (vLLM) behind the `UnderstandingExtractor` interface; **text-first so PL is a first-class citizen**; optional Voxtral Mini 3B direct-audio lane for EN/DE/ES ≤40 min; pattern tables become playbook data | All 11 conversation-intelligence tests pass unchanged against the LLM extractor (the contract — statuses, evidence binding, acceptance rule — is extractor-agnostic) |
| **CI-4** | Streaming provisional view | Chunked faster-whisper + streaming Sortformer v2 (checkpoint license verified) or diart; live transcript marked PROVISIONAL in UI and never committed to the Case Graph; batch re-pass (CI-1) authoritative | Live view during calls; post-call batch output is the only thing `case_update_payload` is built from |
| **CI-5** | Video call analysis (Phase 3) | Qwen3-Omni 30B-A3B (Apache-2.0) for audio+video understanding of video calls — screen shares, shown documents, on-camera installations | Gated on Phase-3 video channel existing at all; PL support re-checked at adoption time |

Ordering rationale: CI-1 makes the tested analysis layer real; CI-2 protects
the Polish market before GA; CI-3 lifts extraction quality without touching
the tested contract; CI-4 adds live UX without compromising ground truth;
CI-5 is deliberately last — it depends on a channel that doesn't exist yet.
