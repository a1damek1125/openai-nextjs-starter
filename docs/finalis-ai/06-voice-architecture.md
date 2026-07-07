# Finalis AI — Voice Architecture

> The Voice Worker must feel like a competent human assistant: fast, interruptible, natural,
> multilingual, and honest about when to hand off. This doc specifies the pipeline, latency
> targets, and the operational behaviors (barge-in, repair, handoff, extraction) — grounded
> in current research and framework capabilities.

## 1. Recommended approach: cascaded streaming pipeline (with a realtime-model option)

**Decision: ship a cascaded, streaming `STT → LLM → TTS` pipeline for the MVP**, not an
end-to-end speech-to-speech model. Rationale from the research:

- **Cascaded pipelines preserve reasoning depth.** Full-duplex end-to-end speech models win
  on raw latency and turn-taking fluidity but **measurably lose reasoning, self-correction,
  and QA accuracy** vs. text-LLM pipelines. Full-Duplex-Bench findings: backchannels rare/
  poorly timed; end-to-end models fast but over-aggressive with poor pause discipline
  (https://arxiv.org/abs/2503.04721). Work on "liberating LLM capabilities in full-duplex
  speech models" attributes this to end-to-end models suppressing text-native capabilities
  (https://arxiv.org/abs/2606.07547). BayLing-Duplex reports end-to-end QA accuracy still well
  below text LLMs (https://arxiv.org/abs/2606.14528). *(These arXiv figures are search-
  surfaced; treat as directional but consistent across multiple papers.)*
- Finalis needs accurate slot-filling, price/scope reasoning, and evidence discipline —
  **reasoning quality outranks the last 200 ms of latency**. A cascaded pipeline also lets us
  reuse the same text LLM + tools as the rest of the system.
- **Keep a realtime-model adapter behind the same interface.** OpenAI's Realtime API went GA
  (Aug 28 2025) with `gpt-realtime` speech-to-speech, positioned for lower latency and adding
  SIP calling + remote MCP (https://openai.com/index/introducing-gpt-realtime/). We can route
  *specific* low-complexity flows (e.g. simple confirmations) to a realtime model later, but
  the default remains cascaded for reasoning-heavy turns. *(Exact realtime latency in ms:
  UNVERIFIED — OpenAI's positioning is qualitative.)*

**Framework**: use **Pipecat** or **LiveKit Agents** as the real-time media + pipeline layer —
do not build transport/VAD from scratch.
- **Pipecat**: open-source (BSD-2) Python framework for real-time voice/multimodal agents;
  orchestrates `STT→LLM→TTS` in one frame pipeline; transports include WebRTC (Daily/LiveKit/
  Vonage), WebSocket, and telephony (Twilio/Telnyx/Vonage); Silero VAD drives interruption/
  barge-in. https://github.com/pipecat-ai/pipecat , https://docs.pipecat.ai/
- **LiveKit Agents**: Apache-2.0 framework where the agent joins a WebRTC Room as a
  participant; supports cascaded STT/LLM/TTS **or** a realtime speech-to-speech model;
  **semantic turn detection** via a transformer end-of-utterance model; built-in interruption
  handling; **built-in SIP/PSTN telephony** (livekit/sip bridge). OpenAI reportedly built
  ChatGPT Advanced Voice on LiveKit (vendor claim).
  https://docs.livekit.io/agents/ , https://github.com/livekit/agents , https://github.com/livekit/sip

**MVP pick**: **LiveKit Agents** if telephony/SIP + turn detection out-of-the-box is the
priority; **Pipecat** if maximum pipeline flexibility/vendor-neutrality is the priority. Both
are viable; decide during Phase 0 based on the chosen telephony provider.

## 2. Pipeline (turn lifecycle)

```
                 barge-in (VAD) ─────────────────────────────┐
                                                             ▼ (stop TTS)
 mic ─▶ Streaming STT ─▶ partial transcript ─▶ Intent/Slot ─▶ Case Graph fetch
        (interim + final)      │                  detector      (prefetched ctx)
                               ▼
                     End-of-utterance (semantic turn detection)
                               ▼
                        LLM (short-answer policy) ──▶ tool calls (calendar/price/status)
                               ▼
                     Streaming TTS ─▶ speaker  (starts on first token/sentence)
                               ▼
              Post-turn: update transcript, promises, missing items, next actions
```

Key techniques to hit latency:
- **Stream everything**: interim STT, LLM token streaming, sentence-chunked TTS start. Begin
  speaking on the first sentence, not the full response.
- **Prefetch context**: load `BusinessProfile`, playbook, calendar, price rules, and case
  state into the turn context so tools resolve without a cold DB hit mid-utterance.
- **Partial intent detection**: begin classifying intent from interim transcripts to warm the
  right tools before the user finishes.
- **Short-answer policy**: cap responses to 1–2 sentences + one question; no monologues.

## 3. Latency targets

Grounding facts:
- **Human turn-taking baseline ≈200 ms** modal inter-turn gap across 10 languages (Stivers et
  al., PNAS 2009, https://www.pnas.org/doi/full/10.1073/pnas.0903616106) — the north star,
  but too fast for deliberative control; we target "feels natural," not human-parity.
- **Telephony engineering limit**: ITU-T G.114 recommends **≤150 ms one-way** mouth-to-ear for
  good interactive quality (up to ~400 ms tolerable) — WebRTC network adds ~50–150 ms.
- **Concrete cascaded reference**: a published enterprise cascaded agent (Deepgram STT + vLLM
  LLM + ElevenLabs TTS) measured **P50 time-to-first-audio ≈947 ms (best 729 ms)**; a
  different component mix showed 1.4 s P50 / 3.4 s P95 — i.e. config-sensitive
  (https://arxiv.org/html/2603.05413v1). *(Single arXiv tutorial, search-surfaced — source-
  attributed, not an industry-wide benchmark.)*
- Vendor rule-of-thumb perception bands (directional, UNVERIFIED as formal standard):
  200–500 ms natural, 500–800 ms acceptable, >1 s disruptive.

**Finalis targets (time-to-first-audio, TTFA):**

| Metric | Target | Fallback trigger |
|---|---|---|
| P50 first response (simple turn) | **≤ 800 ms** | — |
| P95 first response | **≤ 1500 ms** | if exceeded repeatedly → shorten/scripted turns |
| Barge-in stop-speaking latency | **≤ 200 ms** after detected speech onset | — |
| End-to-end round trip (perceived) | ≤ 1 s P50 target | > 2.5 s sustained → offer human handoff |
| Tool-augmented turn (calendar/price) | ≤ 1200 ms P50 | speak a "one moment" filler, then answer |

**Fallback-when-slow rules**: if the LLM/tool exceeds a soft deadline, the Voice Worker emits
a short holding phrase ("let me check that for you") to preserve conversational rhythm, then
delivers the answer; if a hard deadline is exceeded or confidence is low, it offers a callback
or human handoff. Never leave dead air > ~1.5 s without a backchannel.

## 4. Conversational behaviors

- **Barge-in**: VAD (e.g. Silero) detects user speech during TTS → immediately stop TTS, flush
  the queued response, and re-listen. Track `barge_in_events` on the `Call`.
- **Silence/pause handling**: distinguish thinking-pauses from turn-end using semantic
  end-of-utterance detection (LiveKit turn model) rather than a fixed VAD timeout, so we don't
  interrupt a client who's mid-thought. Note: full-duplex research shows pause discipline is
  hard — cascaded + semantic turn detection is the pragmatic choice.
- **Repair phrases**: on ASR uncertainty or contradiction, use targeted repair ("sorry, was
  that *fifteen* or *fifty*?") and confirm critical slots (address, date, price) explicitly.
- **Corrections**: allow the user to correct a slot at any time ("no, Tuesday not Thursday");
  slot-filling is revisable, and the last confirmed value wins.
- **Language switching**: detect language per utterance; switch STT/TTS voice and respond in
  the client's language mid-call; store `languages` on the `Call`. Multilingual STT/TTS
  vendors selected in `VoiceProfile`.
- **Emotion/sentiment**: run lightweight sentiment on transcript (and prosody if the vendor
  exposes it) → feeds `ClientEmotion` in `EscalationScore`. Treat as a *signal*, not ground
  truth; mark as best-effort.
- **Human handoff**: warm transfer when `EscalationScore ≥ θ_escalate`, on explicit request,
  on anger/distress, or on safety emergencies (with a safety script first, e.g. suspected gas
  leak). Handoff passes a live summary to the human.

## 5. Post-call processing (always)

After every call the Voice Worker produces, with evidence refs to transcript timestamps:
1. **Call summary** (concise, owner-readable).
2. **Promise extraction** → `Promise` rows (who promised what, by when).
3. **Missing-information extraction** → `MissingItem` rows.
4. **Next-action generation** → proposal into the NBA utility calc (`05`).
5. **Slot/field updates** → `ExtractedField`/case fields with confidence.
6. **Sentiment timeline** + `barge_in`/latency metrics for the Evaluation Lab.

All of the above are proposals applied by the Orchestrator under autonomy rules; nothing
client-facing happens without passing the autonomy gate.

## 6. What we do NOT promise (honesty)

- We do **not** claim human-indistinguishable, perfectly reasoning full-duplex voice.
  Full-Duplex-Bench-v3 shows current systems still degrade on multi-step reasoning and
  self-correction under real-world disfluency (https://arxiv.org/html/2604.04847). We promise
  *fast, natural, controlled* dialogue with *clean handoff* when the situation exceeds the
  rules — and we measure it (`15-evaluation-lab.md`).
- Recording/consent: call recording is consent-gated and region-configured
  (`VoiceProfile.consent_prompt`, `BusinessProfile.recording_consent_config`); some
  jurisdictions require explicit notice.
