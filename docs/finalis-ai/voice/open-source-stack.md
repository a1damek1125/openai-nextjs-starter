# Finalis Voice Engine — Open-Source Stack Decisions

Research verified 2026-07-07. Tags: `[VP]` = verified against a primary source
(repo LICENSE file, GitHub issue, model card), `[S]` = corroborated search
snippet, `[U]` = unverified — must be confirmed before GA.

## Ground rules

1. **No paid AI subscriptions.** No OpenAI/Anthropic/Deepgram/ElevenLabs/Cartesia
   API keys anywhere in the voice path. Every model runs on hardware we control,
   under a license that permits commercial self-hosting (attribution obligations
   like CC-BY-4.0 are acceptable and will be honored).
2. **Telecom infrastructure costs are acceptable** — they buy connectivity, not
   intelligence: SIP trunk minutes, phone numbers (DIDs), and TURN relay
   servers/bandwidth (self-hosted coturn `[U]`). These are utilities, not AI
   vendors, and are the only recurring external costs in the design.
3. **Code and weights are licensed separately.** A permissive framework wrapping
   proprietary weights is not open — this exact trap (LiveKit's turn detector)
   drove the framework decision below.

## Stack decision table

| Role | Choice | Code license | Weights license | Polish | Self-host requirements | Verdict / justification |
|---|---|---|---|---|---|---|
| Agent framework | **Pipecat v1.5.0** | BSD-2 `[S]` | n/a | n/a (see turn detection) | Python service, CPU | **Adopt.** Fully open including its turn model; ships `SmallWebRTCTransport` (P2P, zero external infra) *and* a native LiveKit transport, so both deployment modes use one pipeline. |
| — rejected | LiveKit Agents v1.6.4 | Apache-2.0 `[VP]` | Turn-detector weights: proprietary "LiveKit Model License", restricted to LiveKit Agents sessions (issue #3262) `[VP]` | Turn detector: **no** (issue #3795) `[VP]` | — | **Reject as framework.** Open code around closed, Polish-less turn weights fails both ground rule 3 and our primary market. (LiveKit *server* is still adopted below — the SFU is genuinely Apache-2.0.) |
| Turn detection | **Smart Turn v3** (Pipecat) | BSD-2, incl. training code `[S]` | BSD-2 open weights **and data** `[S]` | **Yes** — 23 languages incl. PL `[S]` | CPU only, ~8M params, 12–60 ms inference `[S]` | **Adopt.** The single biggest differentiator vs LiveKit Agents; semantic end-of-turn at CPU cost. |
| VAD | Silero VAD (Pipecat default) | MIT `[U]` | MIT `[U]` | Language-agnostic | CPU, negligible | **Adopt** `[U]` — confirm license pin at integration time. |
| WebRTC transport (scale) | **LiveKit server** (self-hosted) | Apache-2.0 `[VP]` | n/a | n/a | Go binary; coturn for TURN | **Adopt.** OSS SFU for multi-party/scale; Pipecat connects via its native LiveKit transport. |
| WebRTC transport (small installs) | Pipecat `SmallWebRTCTransport` | BSD-2 `[S]` | n/a | n/a | None (P2P) | **Adopt** for single-tenant/dev — zero external infra. |
| SIP / PSTN bridge | **livekit/sip** | Apache-2.0 `[VP]` | n/a | n/a | Go service + SIP trunk from any carrier | **Adopt.** SIP↔room bridge without running a GPL PBX. Alternatives documented: Asterisk (GPL-2.0), FreeSWITCH (MPL-1.1), Kamailio (GPL-2.0+ — only relevant for carrier-grade trunk aggregation). |
| Primary ASR (all langs) | **NVIDIA Parakeet TDT 0.6B v3** | NeMo: Apache-2.0 `[U]` | **CC-BY-4.0** (commercial OK with attribution) `[S]` | **Yes** — 25 European languages incl. PL/DE/ES/EN, auto language detection `[S]` | GPU; RTFx ~3333 `[S]`; **not natively streaming** — chunked inference `[S]` | **Adopt.** One model, all four launch languages, automatic language ID for mixed-language calls (scenario S8). Chunked-streaming latency must be measured on the audio path. |
| Fallback ASR (all langs) | **faster-whisper large-v3** | MIT `[S]` | Whisper large-v3: MIT `[U]` | **Yes** — tops open-model Polish WER on BIGOS / amu-cai leaderboard `[S]` | GPU (CTranslate2); 0.5–2 s latency `[S]` | **Adopt as fallback.** Best open Polish accuracy; higher latency makes it the failover, not the primary. |
| Streaming ASR lane (DE/ES/EN) | **Voxtral Realtime 4B** | Apache-2.0 `[S]` | Apache-2.0 `[S]` | **NO** — 13 languages, no PL `[S]` | GPU; 240 ms–2.4 s configurable delay `[S]` | **Adopt for DE/ES/EN only** where true streaming beats Parakeet chunking. Never routed Polish. |
| ASR benchmark lane | Canary 1B v2 | NeMo: Apache-2.0 `[U]` | **CC-BY-4.0** — the NC restriction was v1 only `[S]` | Yes | GPU | **Evaluation only** — ASR+translation benchmark comparator, not in the serving path. |
| Primary TTS (all langs) | **ZONOS2 (Zyphra)** | GitHub LICENSE = MIT `[VP]`; announcement says Apache-2.0 — **discrepancy, see GA-1** | HF weights-file license **unconfirmed** — GA-1 | **Yes** — Polish Tier 3 `[VP]` | GPU; MoE 8B total / 900M active; streaming via SGLang server; zero-shot cloning | **Adopt provisionally.** ~3 weeks old; blocked on GA-1 (license confirmation) and GA-3 (Polish quality bake-off). |
| Fallback TTS (PL) | **Piper** | Original MIT build **archived 2025-10**; successor **piper1-gpl is GPL-3.0** `[S]` | Voice models: per-voice (pl_PL-darkman / gosia / mc_speech) `[U]` | **Yes** | CPU only | **Adopt as PL fallback.** Run piper1-gpl as a **separate process** (CLI/service boundary) so GPL-3.0 never links into the BSD/MIT codebase; pin the archived MIT build as a secondary option. |
| Fallback TTS (DE/ES/EN) | **Qwen3-TTS** | Apache-2.0 `[VP]` | Apache-2.0 `[VP]` | **NO** `[VP]` | GPU; 97 ms streaming `[VP]` | **Adopt for DE/ES/EN.** Fast streaming fallback; excluded from Polish routing. |
| LLM runtime | **vLLM** | Apache-2.0 `[S]` | n/a | n/a | GPU server | **Adopt** for dialogue policy + LLM extractor serving. |
| LLM model | **Qwen3-30B-A3B-Instruct** | — | Apache-2.0 `[S]` | Multilingual; PL quality to validate | GPU (MoE, 3B active) | **Adopt.** Consider **Bielik-11B** for Polish-specialized quality `[U]`. |
| LLM edge runtime | llama.cpp | MIT `[S]` | n/a | n/a | CPU/small GPU | **Adopt** for edge/on-prem-lite deployments. |
| LLM dev runtime | Ollama | MIT `[U]` | n/a | n/a | Dev machines | **Dev-only.** Never a production dependency. |

## License matrix (compact)

| Component | Code | Weights | Commercial self-host | Tag |
|---|---|---|---|---|
| Pipecat v1.5.0 | BSD-2 | — | Yes | `[S]` |
| Smart Turn v3 | BSD-2 (incl. training code) | BSD-2 (weights + data) | Yes | `[S]` |
| LiveKit server | Apache-2.0 | — | Yes | `[VP]` |
| LiveKit Agents turn detector | Apache-2.0 | Proprietary "LiveKit Model License", LiveKit-sessions-only | **No** (rejected) | `[VP]` issue #3262 |
| livekit/sip | Apache-2.0 | — | Yes | `[VP]` |
| Parakeet TDT 0.6B v3 | Apache-2.0 (NeMo) `[U]` | CC-BY-4.0 | Yes, with attribution | `[S]` |
| faster-whisper large-v3 | MIT | MIT `[U]` | Yes | `[S]` |
| Canary 1B v2 | Apache-2.0 (NeMo) `[U]` | CC-BY-4.0 (NC was v1 only) | Yes (eval lane) | `[S]` |
| Voxtral Realtime 4B | Apache-2.0 | Apache-2.0 | Yes | `[S]` |
| ZONOS2 | MIT per GitHub LICENSE; Apache-2.0 per announcement | **Unconfirmed** | Pending GA-1 | `[VP]` (repo LICENSE) |
| Piper (archived) / piper1-gpl | MIT (archived 2025-10) / GPL-3.0 | Per-voice `[U]` | Yes — GPL isolated as separate process | `[S]` |
| Qwen3-TTS | Apache-2.0 | Apache-2.0 | Yes | `[VP]` |
| vLLM / Qwen3-30B-A3B / llama.cpp | Apache-2.0 / — / MIT | — / Apache-2.0 / — | Yes | `[S]` |
| Asterisk / FreeSWITCH / Kamailio (alternatives) | GPL-2.0 / MPL-1.1 / GPL-2.0+ | — | Documented alternatives only | `[S]` |

## Language routing matrix

Matches the scaffold's `SUPPORTED_LANGUAGES = {"pl", "de", "es", "en"}` and the
`ASRRouter`/`TTSRouter` primary+fallback semantics already tested in
`tests/test_voice_engine.py::TestRouters`.

| Language | ASR primary | ASR fallback / streaming lane | TTS primary | TTS fallback |
|---|---|---|---|---|
| **PL** | Parakeet TDT 0.6B v3 | faster-whisper large-v3 | ZONOS2 | Piper (pl_PL-darkman / gosia / mc_speech) |
| **DE** | Parakeet TDT 0.6B v3 | Voxtral Realtime 4B (streaming) + faster-whisper | ZONOS2 | Qwen3-TTS |
| **ES** | Parakeet TDT 0.6B v3 | Voxtral Realtime 4B (streaming) + faster-whisper | ZONOS2 | Qwen3-TTS |
| **EN** | Parakeet TDT 0.6B v3 | Voxtral Realtime 4B (streaming) + faster-whisper | ZONOS2 | Qwen3-TTS |

Hard exclusions encoded in router config: Voxtral Realtime and Qwen3-TTS have
**no Polish** and must never receive `language="pl"` — exactly the case the
tested `TTSRouter.pick()` language-set mechanism handles (a `de` request routes
past a primary that lacks German).

## Action items before GA

| ID | Action | Why it blocks GA |
|---|---|---|
| **GA-1** | **Confirm the ZONOS2 weights license** on the Hugging Face weights file. GitHub repo LICENSE says MIT `[VP]` but the announcement says Apache-2.0 — resolve the code/weights discrepancy in writing. | Primary TTS for all four languages; ground rule 3 requires a verified weights license, not an announcement. |
| **GA-2** | **Pull Parakeet TDT 0.6B v3 Polish WER** from the amu-cai/pl-asr-leaderboard HF Space and validate with goodmike31/pl-asr-bigos-tools `[S]` as a pre-commit check on the ASR choice. | Primary-ASR status for Polish is currently justified by language coverage, not measured Polish accuracy. |
| **GA-3** | **ZONOS2 vs Piper Polish MOS bake-off** (native-speaker listening panel + latency measurement on the streaming SGLang path). | ZONOS2 is ~3 weeks old and its Polish is Tier 3; if it loses, Piper is promoted to PL primary. |
| GA-4 | Confirm the `[U]` cells above: Silero VAD license pin, NeMo code license for Parakeet/Canary, Whisper large-v3 weights license, Piper per-voice model licenses, Ollama license, Bielik-11B license and quality. | Acceptance rule: nothing unverified ships in the compliance record. |
| GA-5 | Measure real latency (VoiceMetric p50/p95 first response, per-stage ASR/LLM/TTS, barge-in success) once the audio path exists — the scaffold honestly reports `measured: False` until then. | Latency claims must come from our deployment, not model cards. |

## R&D watchlist (not in the serving path)

| Project | License | Why we watch it | Why it's not adopted |
|---|---|---|---|
| **Moshi** | MIT code / CC-BY-4.0 weights `[S]` | True full-duplex speech-to-speech; the long-term interaction model | English-only; no path to Polish today |
| **BayLing-Duplex** (arXiv 2606.14528) | research | Duplex dialogue built on GLM-4-Voice — technique transfer for barge-in-native models | Research artifact, unproven languages/licensing for production |
| **Qwen3-Omni 30B-A3B** | Apache-2.0 `[S]` | Single omni model could collapse ASR+LLM+TTS into one stage | ~70–80 GB VRAM; Polish speech support unconfirmed |
| **Full-Duplex-Bench-v3** (arXiv 2604.04847) | benchmark | Evaluation reference for duplex behavior (barge-in, overlap, backchannel) — feeds `evaluation.md` | Not a component; a measuring stick |

## Cost posture summary

- **Zero** recurring AI-vendor spend: all models self-hosted under
  BSD/MIT/Apache/CC-BY licenses (pending GA-1/GA-4 confirmations).
- **Acceptable** recurring spend: SIP trunk minutes, DID phone-number rental,
  TURN server bandwidth — connectivity utilities only.
- **Capex/infra**: one GPU node covers vLLM (Qwen3-30B-A3B, 3B active MoE) +
  Parakeet + ZONOS2 SGLang for a small tenant; Smart Turn v3, Silero VAD, and
  Piper run on CPU, keeping the GPU budget for ASR/LLM/TTS. Exact sizing lands
  in `operations.md` after GA-5 measurements.
