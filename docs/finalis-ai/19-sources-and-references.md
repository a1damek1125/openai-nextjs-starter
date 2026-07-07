# Finalis AI — Sources & References

> Verification policy: technical claims in this blueprint are backed by primary sources
> (official repos/docs, arXiv, model cards) wherever possible. During research, a proxy blocked
> direct fetches of several arXiv/vendor pages, so some figures were confirmed via search-engine
> snippets of those official pages rather than a direct read — those are flagged **[snippet]**.
> Items we could not confirm are flagged **[UNVERIFIED]**. Always re-read the primary source
> before quoting load-bearing numbers verbatim.

## A. Agent orchestration & protocols

| Ref | What we use it for | URL | Verification |
|---|---|---|---|
| OpenAI Agents SDK (Python) | Agents/Handoffs/Guardrails/Sessions/Tracing; within-turn loop; "guardrails run in parallel, fail fast"; human review | https://openai.github.io/openai-agents-python/ | [snippet] primitives confirmed; exact HITL mechanism [UNVERIFIED] |
| OpenAI Agents guide | Agents plan, use tools, collaborate, keep state | https://developers.openai.com/api/docs/guides/agents | [snippet] |
| LangGraph | Durable execution, checkpoint/resume, streaming, persistence, human-in-the-loop `interrupt` | https://docs.langchain.com/oss/python/langgraph/overview · https://docs.langchain.com/oss/python/langgraph/durable-execution | [snippet], repo https://github.com/langchain-ai/langgraph |
| Model Context Protocol | Standard for tools/resources/prompts; stable spec 2025-11-25 (async tasks, OIDC discovery, elicitation enums — see §G); prior baseline 2025-06-18 (OAuth resource servers, structured output, elicitation) | https://modelcontextprotocol.io/specification/2025-11-25 | 2025-11-25 **[VERIFIED primary]** per §G; 2025-06-18 [snippet] |
| Claude Code skills/subagents/hooks | Playbook-authoring & dev-productivity pattern (skills = on-demand markdown; subagents = isolated context; hooks = lifecycle control) | https://code.claude.com/docs/en/skills · https://github.com/anthropics/skills | skills page fetched directly; others [snippet] |
| NVIDIA NeMo Agent Toolkit | Later profiling/eval infra reference (framework-agnostic, MCP/A2A) | https://github.com/NVIDIA/NeMo-Agent-Toolkit | repo description verified |

## B. Autonomy / capability benchmarks (why narrow + supervised)

| Ref | Claim used | URL | Verification |
|---|---|---|---|
| TheAgentCompany | Best agent ~**24%** of 175 realistic office tasks fully autonomous (Claude 3.5 Sonnet; ~34.4% partial); updated leaderboard ~30.3% (Gemini 2.5 Pro) | https://arxiv.org/abs/2412.14161 | [snippet]; two numbers reflect different model/versions |
| OSWorld | 369 real computer tasks; **humans ~72.4%** vs. **best model ~12.2%** at publication (GUI grounding hard) | https://arxiv.org/abs/2404.07972 | [snippet]; later SOTA rising toward/over human baseline [UNVERIFIED specifics] |

## C. Voice / real-time

| Ref | Claim used | URL | Verification |
|---|---|---|---|
| Pipecat | OSS (BSD-2) real-time voice/multimodal; STT→LLM→TTS pipeline; WebRTC/WebSocket/telephony transports; Silero VAD barge-in | https://github.com/pipecat-ai/pipecat · https://docs.pipecat.ai/ | repo fetched (primary) |
| LiveKit Agents | Apache-2.0; WebRTC participant agent; cascaded or realtime S2S; semantic turn detection; built-in SIP/PSTN | https://docs.livekit.io/agents/ · https://github.com/livekit/agents · https://github.com/livekit/sip | repo fetched (primary); "OpenAI built Advanced Voice on LiveKit" = vendor claim |
| Moshi (Kyutai) | Full-duplex speech; **160 ms theoretical / ~200 ms practical (L4)** latency; Mimi codec | https://github.com/kyutai-labs/moshi · https://arxiv.org/abs/2410.00037 | repo fetched (primary) for latency; abstract [snippet] |
| Full-Duplex-Bench (+v2/v3) | Current full-duplex models: poor backchannel timing, over-aggressive turn-taking; degrade on multi-step reasoning/self-correction under disfluency | https://arxiv.org/abs/2503.04721 · https://arxiv.org/html/2604.04847 | [snippet]; directional |
| BayLing-Duplex / "Liberating LLM capabilities…" | End-to-end S2S QA accuracy still well below text LLMs; end-to-end suppresses text-native reasoning | https://arxiv.org/abs/2606.14528 · https://arxiv.org/abs/2606.07547 | [snippet]; **verify arXiv IDs before quoting** |
| Enterprise cascaded voice tutorial | **P50 TTFA ≈947 ms** (best 729 ms) cascaded Deepgram+vLLM+ElevenLabs; config-sensitive | https://arxiv.org/html/2603.05413v1 | [snippet]; single tutorial, not a broad benchmark |
| OpenAI Realtime / gpt-realtime | Realtime API GA 2025-08-28; speech-to-speech; SIP + remote MCP; "lower latency" (qualitative) | https://openai.com/index/introducing-gpt-realtime/ | [snippet]; exact ms [UNVERIFIED] |
| Stivers et al. 2009 (PNAS) | Human modal inter-turn gap ≈**200 ms** across 10 languages | https://www.pnas.org/doi/full/10.1073/pnas.0903616106 | primary academic |
| ITU-T G.114 | ≤**150 ms** one-way mouth-to-ear for good interactive telephony | via https://www.parloa.com/knowledge-hub/speech-latency-voice-ai/ | ITU primary not fetched; via secondary |

## D. Document intelligence / OCR

| Ref | Claim used | URL | Verification |
|---|---|---|---|
| Docling | PDF/DOCX/PPTX/XLSX/HTML/image; layout, reading order, tables, formulas, OCR; MD/HTML/JSON; **MIT**; IBM Research Zurich; LF AI & Data | https://github.com/docling-project/docling | repo fetched (primary) |
| olmOCR | PDF/img → linearized MD; handwriting/tables/equations; 7B VLM (Qwen2-VL→Qwen2.5-VL); **olmOCR-Bench 82.4**; **~$190/M pages** vs >$6,240/M GPT-4o; **Apache-2.0** | https://github.com/allenai/olmocr · https://arxiv.org/abs/2502.18443 | repo fetched (primary); cost/training-set figures [snippet] |
| PaddleOCR-VL | **0.9B** (NaViT encoder + ERNIE-4.5-0.3B); **109 languages**; text/tables/formulas/charts; SOTA OmniDocBench v1.5 (superseded by §G: v1.6, ~1B, 111 langs) | https://arxiv.org/abs/2510.14528 · https://huggingface.co/PaddlePaddle/PaddleOCR-VL | [snippet]; **weights license UNVERIFIED** |
| Qwen2.5-VL / Qwen3-VL | Omni-document parsing (QwenVL-HTML); handwriting/tables/charts; Qwen3-VL OCR 32 langs, robust to low light/blur/tilt | https://arxiv.org/abs/2502.13923 · https://github.com/qwenlm/qwen3-vl | [snippet] + repo |
| Surya | Layout/reading-order/table/OCR, **90+ langs**; code Apache-2.0, weights AI-Pubs Open RAIL-M (free <$5M) | https://github.com/datalab-to/surya | repo fetched (primary) |
| Azure Document Intelligence | Per-word/per-field confidence + human-review threshold model | https://learn.microsoft.com/azure/ai-services/document-intelligence/concept/accuracy-confidence | [snippet] |
| Extraction F1 / calibration | Field-level F1 is the IDP standard; multi-signal confidence beats logprobs; Platt/isotonic calibration | https://www.llamaindex.ai/glossary/f1-score-for-document-extraction · "Beyond Logprobs" | [snippet]; **verify arXiv ID** |

## E. Web research / browser automation & agentic security

| Ref | Claim used | URL | Verification |
|---|---|---|---|
| Playwright MCP | Browser control via **accessibility tree, not screenshots**; deterministic; "no vision models needed"; **Apache-2.0** (Microsoft) | https://github.com/microsoft/playwright-mcp | repo fetched (primary) |
| browser-use | "Make websites accessible for AI agents"; provider-agnostic; **MIT** | https://github.com/browser-use/browser-use | repo verified |
| Skyvern | Browser workflows via LLM + computer vision on Playwright; forms/multi-step; **AGPL-3.0** | https://github.com/Skyvern-AI/skyvern | repo verified |
| Firecrawl | Scrape/crawl/map/search/extract → LLM-ready markdown; **respects robots.txt by default**; **AGPL-3.0** (SDKs MIT) | https://github.com/firecrawl/firecrawl · https://www.firecrawl.dev/ | repo fetched (primary) |
| OWASP Top 10 for LLM Apps 2025 | LLM01 Prompt Injection (#1), LLM06 Excessive Agency | https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf | official PDF (primary) |
| OWASP Top 10 for Agentic Apps | Published 2025-12-09; ASI01–ASI10 (goal hijacking, tool misuse, identity/privilege abuse, memory poisoning, rogue agents, …) | https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-... | announcement page; **ASI ordering SEMI-VERIFIED — confirm final PDF** |
| Agentic-browser security research | AI browser changes the web threat model (human no longer "final arbiter of intent"); sandboxing needed | https://arxiv.org/abs/2511.20597 (BrowseSafe) · https://arxiv.org/pdf/2512.12594 (ceLLMate) | [snippet]; **verify** |
| hiQ v. LinkedIn (9th Cir.) | Scraping **public** data likely not CFAA "without authorization" (Van Buren gates test); but ToS/copyright/paywall/CAPTCHA-bypass still apply; hiQ settled + enjoined for ToS breach | https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn · https://www.jenner.com/... | legal-analysis synthesis; **not legal advice** |
| CRAAP / SIFT | Source-trust scoring frameworks feeding `SourceTrust` | https://www.scribbr.com/working-with-sources/craap-test/ | verified |

## F. General agent/benchmark context

- TheAgentCompany (B) and OSWorld (B) — the core "don't over-promise autonomy" evidence.
- WebArena-style web-agent benchmarks and Full-Duplex-Bench family (C) — capability envelope.

## G. 2026 state-of-the-art refresh (second research pass — see `21`)

| Ref | Claim used | URL | Verification |
|---|---|---|---|
| MCP spec 2025-11-25 | Newer stable spec: async tasks (experimental), OIDC discovery, Client-ID-Metadata auth, elicitation enums, sampling tool-calls; 2026-07-28 RC in flight | https://github.com/modelcontextprotocol/modelcontextprotocol/releases | **[VERIFIED primary]** (GitHub releases + raw changelog) |
| LangGraph 1.2.8 (2026-07-06) | 1.2 line: durable error-handler resume across host crashes, delta-channel snapshotting | https://pypi.org/project/langgraph/ · GitHub release 1.2.0 | **[VERIFIED primary]** (PyPI + release notes); HITL specifics for 1.2.x [UNVERIFIED] |
| OpenAI Agents SDK 0.18.0 (2026-07-07) | RealtimeAgent default → gpt-realtime-2.1; SQLAlchemy sessions; Temporal extra; beta sandbox runtime [snippet] | https://pypi.org/project/openai-agents/ · GitHub releases | **[VERIFIED primary]** versions; sandbox/websocket [snippet] |
| Pipecat v1.5.0 (2026-07-04) | Flows in core; TTFA metrics; Smart Turn v3 ~8M params ~12 ms CPU, 23 langs (v3.1) | https://github.com/pipecat-ai/pipecat/releases | **[VERIFIED primary]** release; Smart Turn figures [snippet] |
| LiveKit Agents 1.6.4 (2026-06-26) | Unified audio+text Turn Detector v1.0; async tools; filler phrases; simulation framework | https://github.com/livekit/agents/releases | **[VERIFIED primary]** version; feature details [snippet] |
| gpt-realtime-2.1 / -mini (~2026-07-06) | Configurable reasoning effort; ≥25% lower P95 (relative); pricing approximate | OpenAI announcement (403 to fetch) | [snippet] |
| Kyutai MoshiRAG (2026-04-30) / Pocket TTS | Full-duplex + async retrieval; 100M TTS, ~200 ms first chunk, CPU real-time, MIT | https://github.com/kyutai-labs/moshi-rag · https://github.com/kyutai-labs/pocket-tts | repos **[VERIFIED primary]**; latency [snippet] |
| olmOCR 2 (`olmOCR-2-7B-1025`) | RL (GRPO) with unit-test rewards; olmOCR-Bench 82.4±1.1; Apache-2.0 | https://github.com/allenai/olmocr · https://arxiv.org/abs/2510.19817 | **[VERIFIED primary]** (GitHub + Ai2 blog) |
| PaddleOCR-VL-1.5 / -1.6 | 0.9–1B, 111 langs; 1.6 reports **96.33 OmniDocBench v1.6** (vendor) | https://arxiv.org/abs/2601.21957 · https://arxiv.org/abs/2606.03264 | [snippet]; weights license [UNVERIFIED] |
| dots.ocr (1.7B, MIT) | Unified layout+recognition+reading order, 100+ langs | https://github.com/rednote-hilab/dots.ocr | repo **[VERIFIED primary]**; scores [snippet] |
| DeepSeek-OCR / Granite-Docling-258M | Optical context compression (~200k pages/day/A100); 258M edge doc VLM | https://github.com/deepseek-ai/DeepSeek-OCR · IBM announcement | repos/announcement **[VERIFIED primary]**; figures [snippet] |
| Docling v2.110 (2026-07-04) | nemotron-ocr + vLLM backends, ASR, ODF; MIT | https://github.com/docling-project/docling/releases | **[VERIFIED primary]** |
| WindowsWorld (ACL 2026) | Cross-app Windows workflows: all agents **<21%** | https://arxiv.org/abs/2604.27776 · https://github.com/HITsz-TMG/WindowsWorld | GitHub **[VERIFIED primary]**; scores [snippet] |
| OSWorld 2.0 | Long-horizon (~318 tool calls median): best **~20.6%** end-to-end / 54.8% partial | https://arxiv.org/abs/2606.29537 · https://osworld-v2.xlang.ai/ | [snippet] |
| OSWorld-Verified 2026 SOTA | Single-app SOTA ~72% (Agent S2; Claude Sonnet 4.6 ~72.5%) — nominal human parity on short tasks only | https://os-world.github.io/ | [snippet]; distrust >76% aggregator claims (SEO spam) |
| macOSWorld / OSUniverse | Proprietary agents >30% vs open <2%; SOTA <50% where humans ~100% | https://arxiv.org/abs/2506.04135 · https://arxiv.org/abs/2505.03570 | [snippet] |
| OWASP Agentic Top 10 2026 (ASI01–10) | Goal hijack, tool misuse, identity/privilege abuse, supply chain, code exec, memory poisoning, inter-agent comms, cascading failures, trust exploitation, rogue agents | https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ | [snippet] multi-source; exact titles TBC vs PDF |
| OWASP Agentic Skills Top 10 (AST01–10) | Skill-layer risks (malicious skills, over-privilege, metadata mismatch, update drift…) | https://owasp.org/www-project-agentic-skills-top-10/ | [snippet]; provisional naming |
| SOPGuard/SOPBench (arXiv 2606.14027) | Same-Origin-Policy enforcement for agentic browsers | https://arxiv.org/abs/2606.14027 | [snippet] |
| ceLLMate (arXiv 2512.12594) | HTTP-layer policy interposition sandbox for browser agents; blocks WASP injection at ~7–15% latency overhead | https://arxiv.org/abs/2512.12594 · https://cellmate-sandbox.github.io/ | [snippet] |
| In-browser injection fuzzing (arXiv 2510.13543) | Real-time LLM-guided fuzzing finds injection vulns in agentic browsers; Comet/Reddit exfiltration case | https://arxiv.org/abs/2510.13543 | [snippet] |
| NIST AI Agent Standards Initiative (2026-02-17) | Identity & authz, security & risk mgmt, monitoring & logging; SP 800-53 mapping | https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative | [snippet] |

---

### How to treat these citations
1. Primary-repo facts (Docling, olmOCR, Surya, Pipecat, LiveKit, Moshi, Playwright MCP,
   browser-use, Skyvern, Firecrawl, OWASP LLM PDF, PNAS) are **high confidence**.
2. **[snippet]** figures (arXiv abstracts, vendor blogs, framework docs behind the proxy) are
   attributed to their canonical URL but were read via search results — **re-read before
   publishing verbatim quotes or exact numbers**.
3. **[UNVERIFIED]** items (some arXiv IDs, PaddleOCR-VL weights license, exact realtime-voice
   ms, OWASP ASI ordering) must be confirmed against the primary source before they drive a
   decision or a public claim.
4. Legal references are **synthesis, not advice** — each tenant confirms with counsel per
   jurisdiction (`16`).
