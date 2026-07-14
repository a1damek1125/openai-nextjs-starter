# Finalis AI — State-of-the-Art Technology Review (2026-07)

> **Standing requirement (applies to this blueprint and to every future architecture
> decision):** before any final component decision, re-research the newest available
> technologies — official docs, GitHub release activity, Hugging Face model cards, arXiv —
> compare **at least 2–4 options per component**, and pick both a **production-MVP choice**
> and a **long-term advanced choice**. The source list in the original brief is a *baseline,
> not the answer*: if a listed tool is no longer best-in-class, replace it and justify the
> replacement. Classify every candidate as **production-ready now / promising-but-experimental
> / research-only / not recommended**. The architecture must be technologically ambitious but
> buildable — an MVP that can become a category-defining product, not a mediocre one.

This document is the result of the second (2026-07) research pass, executed by a swarm of
verification agents against primary sources. Tags: **[V]** = verified on a primary source
(repo/PyPI/GitHub releases/official page) · **[s]** = corroborated via search snippets of the
primary (proxy blocked direct fetch) · **[U]** = unverified. Re-check [s]/[U] before quoting
verbatim. Full citation registry: `19`.

---

## 0. What changed vs. the first pass (deltas already applied to docs 02/06/07/08/19)

| Area | Old rec | New finding | Action taken |
|---|---|---|---|
| MCP | spec 2025-06-18 | **Stable spec 2025-11-25** [V] (async tasks, OIDC discovery, elicitation enums); 2026-07-28 RC in flight | `02` updated; async tasks flagged for long doc/web jobs |
| OCR primary | PaddleOCR-VL 0.9B | **PaddleOCR-VL-1.6** (~1B, reported 96.33 OmniDocBench v1.6 [s]) + **olmOCR 2** (RL unit-test rewards, 82.4 [V]) + **dots.ocr** as compact multilingual alt | `07` engine table updated |
| Voice frameworks | Pipecat/LiveKit (generic) | **Pipecat 1.5** [V] (Flows in core, TTFA metrics, Smart Turn v3 ~12 ms CPU [s]); **LiveKit Agents 1.6.4** [V] (unified audio+text Turn Detector v1.0, async tools, filler phrases, sim framework [s]) | `06` updated |
| Realtime S2S | gpt-realtime (GA 2025) | **gpt-realtime-2.1/-mini** [s] (reasoning-effort control, ≥25% lower P95 relative); best native S2S ~0.4–0.9 s TTFA per third-party boards [s] | `06` updated + quarterly re-eval rule |
| Benchmarks | OSWorld 12% vs 72% | Single-app SOTA now ~72% [s] **but** cross-app **<21%** (WindowsWorld, ACL 2026) and long-horizon **~20.6%** (OSWorld 2.0) [s] | `02` evidence section rewritten (more precise, same conclusion) |
| Agentic security | OWASP LLM 2025 + Agentic (Dec 2025) | + **OWASP Agentic Skills Top 10** [s], **ceLLMate HTTP-layer sandboxing** [s], **SOPGuard agent-SOP** [s], **NIST AI Agent Standards Initiative** (Feb 2026) [s] | `08` hardening patterns added |
| Durable execution | Temporal (generic) | **Temporal × OpenAI Agents SDK integration GA** (~2026-03) [V]; Cloudflare Agents/Durable Objects; **Google ADK 2.x** GA workflow runtime [V] | recommendation refined below |

**Conclusion up front: no first-pass architectural decision was overturned** — cascaded voice,
LangGraph+MCP orchestration, routed multi-engine OCR, Postgres-first data layer, and
controlled autonomy all *strengthened* under re-research. What changed are versions, specific
model picks, and added security patterns.

---

## 1. Per-component review

Format per component: options compared → **Production now / Open-source / Experimental /
Fallback** → role in Finalis.

### 1.1 Multi-agent orchestration
Compared: LangGraph 1.2.8 [V] · OpenAI Agents SDK 0.18.0 [V] · Google ADK 2.3.0 (GA graph
Workflow Runtime, HITL, Task API/A2A) [V] · CrewAI ~1.15 (Flows + checkpoint forking [s]) ·
NeMo Agent Toolkit 1.8 (profiling/eval/MCP/A2A layer, not an orchestrator) [V] · OpenClaw
(see §1.20).
- **Production now**: **LangGraph 1.2** — durable error-handler resume across host crashes,
  delta-channel snapshotting [V]; the deciding features for multi-day cases.
- **Open-source alt**: **Google ADK 2.x** — GA graph runtime with fan-out/loops/retry/HITL;
  the strongest newcomer; keep as the challenger in Phase-0 ADR.
- **Experimental**: Cloudflare "Project Think" durable-execution fibers [V]; NeMo profiling +
  RL fine-tuning of agent teams [s].
- **Fallback**: OpenAI Agents SDK alone (Agents/Handoffs/Guardrails/Sessions/Tracing; now with
  Temporal extra + beta sandbox runtime [s]) — great within-turn, weaker cross-day durability.
- **Role in Finalis**: Orchestrator + Completion Loop (`02`, `09`).

### 1.2 Durable stateful workflows
Compared: Temporal (GA OpenAI-Agents integration ~2026-03 [V]) · LangGraph checkpointing [V] ·
Cloudflare Durable Objects/Agents SDK [V] · Postgres-backed queue/APScheduler.
- **Production now**: **Temporal** for time-based durability (follow-ups scheduled days out,
  promise deadlines) + **LangGraph checkpoints** for graph state. They compose.
- **Open-source**: same (both OSS).
- **Experimental**: Cloudflare Agents (per-agent SQLite + hibernation) — attractive for edge
  deployments later.
- **Fallback**: Postgres queue + APScheduler (lighter MVP; fewer guarantees).
- **Role**: the Completion Loop's heartbeat and scheduled wakeups (`09`).

### 1.3 Tool/integration protocol
Compared: MCP 2025-11-25 [V] · bespoke adapters · A2A (agent-to-agent, complementary).
- **Production now / Open-source**: **MCP 2025-11-25** — async tasks (experimental) map
  directly to long OCR/web jobs; OIDC discovery improves tenant OAuth.
- **Experimental**: MCP 2026-07-28 RC [V exists]; A2A for future inter-agent federation.
- **Fallback**: direct SDK adapters where an MCP server doesn't exist yet.
- **Role**: every integration (`12`).

### 1.4 Real-time voice framework
Compared: Pipecat 1.5.0 [V] · LiveKit Agents 1.6.4 [V] · NVIDIA voice-agent-examples v0.4
(`nvidia_pipecat`: Riva/Nemotron NIMs, ACE avatars; reference stack, low activity) [V] ·
bespoke WebRTC.
- **Production now**: **LiveKit Agents 1.6** (SIP/PSTN built-in, unified audio+text Turn
  Detector v1.0, async tools + filler phrases, simulation framework) *or* **Pipecat 1.5**
  (Flows in core, built-in TTFA metrics, Smart Turn v3 ~12 ms CPU [s], vendor-neutral).
  Decide in Phase 0 by telephony provider; both are mature 1.x.
- **Open-source**: both (Apache-2.0 / BSD-2).
- **Experimental**: NVIDIA `nvidia_pipecat` stack (adds avatars/NIMs) — reference only.
- **Fallback**: half-duplex VAD cascade — boring, reliable, preserves full LLM reasoning.
- **Role**: Voice Worker transport + pipeline (`06`).

### 1.5 Full-duplex / speech-to-speech conversation
Compared: gpt-realtime-2.1/-mini [s] · Gemini 3.1 Flash Live (native audio, 90+ langs,
preview 2026-03, no GA) [s] · Kyutai Moshi + **MoshiRAG** (full-duplex + async retrieval,
2026-04) [V repo] · Step-Audio-R1 (~0.92 s, #1 Big Bench Audio [s]) · cascaded pipelines.
- **The frontier fact**: Full-Duplex-Bench **v3** (2604.04847 [s]): best native S2S Pass@1 on
  tool-use under disfluency = **0.600 (GPT-Realtime)**; cascaded pipeline = perfect
  turn-taking but ~10 s latency in their harness; **τ-Voice** [s]: sub-1.5 s responders
  plateau at ~10% task accuracy vs ~54% text bound. **The latency-vs-reasoning frontier is
  real and unresolved.**
- **Production now**: **cascaded streaming STT→LLM→TTS** (Finalis's choice stands, now with
  stronger evidence).
- **Experimental**: gpt-realtime-2.1 for low-complexity confirmations behind the same
  interface; MoshiRAG direction (full-duplex + retrieval) as R&D watch.
- **Research-only**: end-to-end full-duplex for reasoning-heavy sales/document dialogue.
- **Not recommended**: betting the product on native S2S today.
- **Role**: `06` §1; re-evaluate quarterly in the Evaluation Lab.

### 1.6 Streaming STT → LLM → TTS pipeline components
- **Production now**: vendor-mix per language via Pipecat/LiveKit plugins (Deepgram/AssemblyAI
  class STT; frontier LLM; ElevenLabs/Cartesia class TTS); **published cascaded reference:
  P50 TTFA ≈947 ms** (arXiv 2603.05413 [s]) — our ≤800 ms P50 target is ambitious-but-grounded.
- **Open-source**: Kyutai **Pocket TTS** (100M, MIT, ~200 ms first chunk on CPU [V repo/s]) —
  serious self-host TTS option; Whisper-class STT.
- **Experimental**: Together/NVIDIA NIM speech services.
- **Fallback**: pre-recorded + template TTS for degraded mode.
- **Role**: `06` §2–3.

### 1.7 Barge-in / turn detection
- **Production now**: **LiveKit Turn Detector v1.0** (audio+text, CPU, <500 MB [s]) or
  **Pipecat Smart Turn v3/v3.1** (~8M params, ~12 ms CPU, 23 langs [s]) — semantic end-of-
  utterance beats fixed VAD timeouts.
- **Fallback**: Silero VAD timeout.
- **Role**: `06` §4 (barge-in ≤200 ms stop target).

### 1.8 Multilingual voice
- **Production now**: per-language STT/TTS vendor selection in `VoiceProfile`; turn models
  cover 14–23 languages [s].
- **Experimental**: Gemini Live-class native multilingual audio (90+ langs, preview [s]).
- **Role**: `06` §4 language switching.

### 1.9 Document OCR (recognition layer)
Compared: PaddleOCR-VL-1.6 (~1B, 111 langs, reported **96.33 OmniDocBench v1.6** [s]) ·
olmOCR 2 (**82.4 olmOCR-Bench**, RL unit-test rewards, Apache-2.0, fully open [V]) ·
dots.ocr (1.7B, MIT, 100+ langs [V repo/s]) · MinerU2.5-Pro (~95.7 v1.6, vendor [s]) ·
DeepSeek-OCR (optical context compression, ~200k pages/day/A100, MIT [V repo/s]) ·
Qwen3-VL (general VLM, 32 OCR langs [s]) · Surya (90+ langs, RAIL-M weights [V]).
- **Production now**: **PaddleOCR-VL-1.6** as primary multilingual parser *(vendor benchmark —
  validate on tenant docs first; weights license [U] — confirm before shipping)*.
- **Open-source (cleanest licensing)**: **olmOCR 2** (English-heavy docs) + **dots.ocr** (MIT,
  multilingual compact).
- **Experimental**: **DeepSeek-OCR** — optical compression is a genuinely new direction for
  token-efficient bulk processing.
- **Fallback**: Qwen3-VL for messy/rotated/handwritten; classic PaddleOCR/Tesseract for
  no-GPU.
- **⚠ Benchmark honesty**: all 2026 OmniDocBench scores are **vendor-reported and span
  different bench versions (v1.0/v1.5/v1.6) — not comparable across versions**. The Evaluation
  Lab decides the per-tenant default, not the leaderboard.
- **Role**: `07` §2 routing layers 2–3.

### 1.10 Layout-aware document parsing / pipeline
- **Production now / Open-source**: **Docling v2.110** [V] (MIT; pluggable OCR/VLM backends
  incl. nemotron-ocr and **Granite-Docling-258M** for edge) — unchanged, strengthened.
- **Experimental**: docling-graph (docs → knowledge graphs) — interesting for Case Graph
  ingestion later.
- **Role**: `07` §2 layer 1 + structure for evidence bboxes.

### 1.11 Handwriting / low-quality scans
- **Production now**: route to olmOCR 2 / Qwen3-VL (robust to blur/tilt/low light [s]) with
  preprocessing (≥300 DPI, deskew, CLAHE) — unchanged (`07` §3, §6).
- **Rule unchanged**: low confidence → abstain + request re-scan; critical handwritten values
  need corroboration.

### 1.12 Evidence-based extraction confidence
- **Production now**: per-field confidence × calibrated thresholds × HITL routing (`05` §6,
  `07` §4).
- **Research to adopt**: **ConfTuner** (Brier-loss calibration of verbalized confidence [s]);
  abstention methods (I-CALM [s]). Multi-signal confidence (OCR-stage + extraction-stage)
  beats logprobs alone [s].
- **Role**: the anti-hallucination core; targets live in `15`.

### 1.13 Browser automation
- **Production now**: **Playwright MCP** (accessibility-tree, deterministic [V]) — unchanged.
- **Open-source alt**: browser-use (MIT [V]); **Experimental**: Skyvern (AGPL [V]) for
  genuine multi-step public workflows.
- **Role**: `08` §3.

### 1.14 Public web research / PDF+web extraction
- **Production now**: **Firecrawl** (robots-respecting, LLM-ready markdown [V]; AGPL —
  posture decision in `18` §9).
- **Fallback**: plain fetch + Docling for public PDFs.
- **New hardening (2026)**: HTTP-layer policy interposition (ceLLMate [s]), agent-adapted SOP
  (SOPGuard [s]), continuous injection fuzzing in CI [s], scoped non-human agent identity
  (NIST [s]) — added to `08`.
- **Role**: WebScout (`08`).

### 1.15 Case graph memory
- **Production now**: Postgres `graph_edges` + recursive CTEs (unchanged; no 2026 finding
  displaces it at MVP scale). **Long-term**: Neo4j migration trigger unchanged (`18` §2);
  docling-graph as a document→graph feeder to watch.
- **Role**: `04`.

### 1.16 Vector search
- **Production now**: pgvector (unchanged). **Long-term**: dedicated store only at scale.
- **Role**: Deal Memory + semantic retrieval (`04`).

### 1.17 Event sourcing / audit
- **Production now**: append-only `AuditEvent` + hash chain in Postgres (unchanged);
  NIST SP 800-53 AU-family mapping [s] validates the design direction (`13`).

### 1.18 Automated evaluation & simulation testing
- **Production now**: internal Evaluation Lab harness (`15`) + **LiveKit Agents' built-in
  simulation/testing framework** [s] for voice; Full-Duplex-Bench methodology as the template
  for voice regression suites.
- **Experimental**: NeMo Agent Toolkit profiling/eval/HPO of agent teams [V/s] — candidate
  for Phase 3+.
- **Role**: `15`.

### 1.19 Human-in-the-loop approval, cost & latency monitoring
- **Production now**: LangGraph `interrupt` + `HumanApproval` entity (`13`); OpenTelemetry +
  **Pipecat TTFA metrics** [V] (voice latency observability now first-class in the framework);
  token/minute cost meters per worker with per-tenant budgets (`15`, `16` cost risk).
- **Role**: `11` Control Center, `13`, `15`.

### 1.20 OpenClaw (comparison requested by the brief)
- **Verdict [V]**: real and extremely active (created 2025-11, **~382k stars**, pushed daily;
  TypeScript; skill registry "ClawHub"). It is a **self-hosted personal AI assistant runtime**
  (Gateway + multi-turn tool loop, surfaces on WhatsApp/Telegram/Slack/etc.), **not** a
  durable-workflow orchestration framework — no Temporal-style replay, checkpointed graphs, or
  HITL workflow primitives. Non-OSI "Other" license [V].
- **Relevance to Finalis**: an inspiration for channel ubiquity and a skills-distribution
  model (its skill ecosystem echoes our `IndustryPlaybook` idea), and a *warning* about
  running over-permissioned assistants on personal credentials — but **not recommended** as a
  Finalis building block. SEO-cited "OpenClaw papers" are [U] — do not cite.

---

## 2. Consolidated classification

| Production-ready now | Promising but experimental | Research-only | Not recommended (for Finalis) |
|---|---|---|---|
| LangGraph 1.2 · Temporal (+Agents-SDK GA) · MCP 2025-11-25 · LiveKit Agents 1.6 / Pipecat 1.5 · Docling 2.110 · olmOCR 2 · dots.ocr · PaddleOCR-VL-1.6* · Playwright MCP · Firecrawl · pgvector/Postgres · Smart Turn v3 / Turn Detector v1.0 | Google ADK 2.x (challenger) · gpt-realtime-2.1 for simple flows · DeepSeek-OCR · Granite-Docling edge · Cloudflare Agents · NeMo Agent Toolkit profiling · docling-graph · MoshiRAG direction · ConfTuner-style calibration | End-to-end full-duplex S2S for reasoning-heavy dialogue · optical-context-compression at case scale · agent RL fine-tuning | Betting on native S2S today · open-ended GUI autonomy (WindowsWorld <21%) · OpenClaw as infrastructure · un-sandboxed browser agents · trusting vendor OmniDocBench numbers cross-version |

\* validate on tenant document mix + confirm weights license before default-on.

## 3. Standing re-research process (how we keep this current)

1. **Quarterly SOTA sweep** (same swarm method as this pass): orchestration, voice, OCR,
   browser, security, benchmarks. Output: a delta table like §0.
2. **Evaluation Lab gates every swap**: no engine/model change ships without beating the
   incumbent on the tenant-mix golden sets (`15`).
3. **ADR per change**: every replacement records what/why/evidence, kept next to `18` §9.
4. **Honesty discipline**: [V]/[s]/[U] tags are mandatory in every future review; vendor
   benchmark numbers never drive a default without local validation; SEO-grade aggregator
   claims are excluded (this pass caught fabricated benchmark numbers in the wild).
