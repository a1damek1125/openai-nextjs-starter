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
| Model Context Protocol | Standard for tools/resources/prompts; spec 2025-06-18 (OAuth resource servers, structured output, elicitation) | https://modelcontextprotocol.io/specification/2025-06-18 | [snippet] |
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
| PaddleOCR-VL | **0.9B** (NaViT encoder + ERNIE-4.5-0.3B); **109 languages**; text/tables/formulas/charts; SOTA OmniDocBench v1.5 | https://arxiv.org/abs/2510.14528 · https://huggingface.co/PaddlePaddle/PaddleOCR-VL | [snippet]; **weights license UNVERIFIED** |
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
