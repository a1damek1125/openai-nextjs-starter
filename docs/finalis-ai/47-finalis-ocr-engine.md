# Finalis OCR Engine — Router/Ensemble Document Intelligence Layer

> **Design stance: our IP is not an OCR model — it is the layer around pluggable engines.**
> No single OCR model reads everything; every engine has a licensing, language, or robustness
> boundary. Finalis builds the **OCR Router**, classifier, preprocessing, multi-model
> cross-check, confidence, evidence, abstention, and human-review workflow as proprietary
> engine-agnostic infrastructure — and treats every OCR model as a swappable adapter.
>
> **Acceptance rule (enforced in code — `finalis/ocr_router.py::cross_check`, tested):**
> *No critical decision may rely on OCR output unless confidence is high, independent models
> agree, or a human verified the extracted field.*

**Executable status**: the router core (classifier, preprocessing planner, routing table,
multi-model cross-check with the acceptance rule) is implemented in `finalis/ocr_router.py`
with passing tests (`tests/test_documents_webscout_ocr.py`). Engine adapters are mocks;
real engine integration is Sprint 5 (`35`).

---

## 1. Engine candidates — verified status & license matrix (2026-07-07)

Verification tags: **[V]** primary source read · **[s]** multi-source search snippets (proxy
blocked HF/mistral primary pages) · **[U]** unverified. Full research trail in `19` §G/H.

| # | Engine | Role in ensemble | Code license | Weights license | Verdict |
|---|---|---|---|---|---|
| 1 | **PaddleOCR-VL-1.6** (~1B, 111 langs, reported 96.33 OmniDocBench v1.6) | **primary_parser** — multilingual docs, tables, formulas, charts, seals, distorted scans | Apache-2.0 [s] | Apache-2.0 per HF card + LICENSE file in model repo [s, multi-source — **legal must pull the HF LICENSE file once from an unproxied network**] | **SAFE-CORE** |
| 2 | **Baidu Unlimited-OCR** (~3B, one-shot whole-PDF parsing, R-SWA constant KV cache, released 2026-06-22) [V exists] | **longdoc_parser** — long multi-page PDFs | MIT [V] | MIT reported on HF [s] | **R&D-WATCHLIST** — real and license-safe but ~2 weeks old; adopt after maturity gate |
| 3 | **olmOCR 2** (`olmOCR-2-7B-1025`, olmOCR-Bench 82.4 [V], RL unit-test rewards) | **robust_vlm** — PDF linearization, reading order, tables, formulas, multi-column; degraded scans & handwriting (English-primary [V]) | Apache-2.0 [V] | Apache-2.0 [V] | **SAFE-CORE** (English) |
| 4 | **Surya OCR** (650M, 90+ langs, layout/bbox/confidence/tables, 83.3 olmOCR-bench) [V] | **layout_ocr** — evidence layer (bboxes + per-region confidence) | Apache-2.0 [V] | Modified AI-Pubs OpenRAIL-M: free < **$5M** funding/revenue; **drafting bug found**: license text says "two million US Dollars ($5,000,000)" — words vs. numerals conflict [V]; + non-compete clause | **LICENSE-GATED** — fine for MVP/startup phase, needs Datalab commercial license at scale |
| 5 | **Marker** (doc→Markdown/JSON/HTML, OCR-only mode, LLM correction) [V] | **structure_parser** (alternative to Docling) | **GPL-3.0** ⚠ [V] | Modified OpenRAIL-M, **$2M** gate (stricter than Surya!) [V] | **LICENSE-GATED (double)** — GPL copyleft + RAIL; Datalab sells GPL-removal. Prefer **Docling (MIT)** for this role |
| 6 | **Mistral OCR** (hosted API; OCR 4 ~$4/1k pages [s]; enterprise single-container on-prem via contract [s]) | **api_fallback** — benchmark comparison + enterprise fallback | proprietary | no open weights | **API-FALLBACK** |
| 7 | **DeepSeek-OCR** (optical context compression; accuracy collapses beyond ~10× compression and on degraded inputs per multiple reports [s]) | **experimental** — bulk clean-doc compression only; **never sole parser for weak scans** | MIT [V] | MIT [s] | **SAFE-CORE license / EXPERIMENTAL role** |
| 8 | **HunyuanOCR-1.5** (1B-class fast OCR VLM, DFlash decoding; public weights) [V exists] | R&D watchlist | Tencent Hunyuan Community License [V] | same — **EU/UK/South-Korea territorially EXCLUDED**, >100M-MAU cap, AUP restrictions [V] | **LICENSE-GATED (hard)** — unusable for any EU-serving tenant; watch only |
| — | **Docling** (MIT, structure/layout, pluggable backends) [V] | **structure_parser** (default) | MIT [V] | n/a (pipeline) | **SAFE-CORE** |
| — | **Qwen3-VL** (general VLM, 32 OCR langs) | **vlm_fallback** — hard multimodal cases | Apache-2.0 (check per-size) | Apache-2.0 [s] | SAFE-CORE (fallback role) |

**Enterprise-core selection** (prefer Apache-2.0/MIT for code AND weights):
`PaddleOCR-VL-1.6 (primary) + olmOCR 2 (robust/English) + Docling (structure) + Qwen3-VL
(fallback) + DeepSeek-OCR (clean-bulk experimental)`. Surya only while under the $5M gate or
under a paid license; Marker replaced by Docling to avoid GPL; Mistral as paid API fallback;
Unlimited-OCR and HunyuanOCR on the watchlist (the latter blocked for EU tenants regardless).

**License rules applied** (as mandated): licenses checked separately for code and weights;
GPL/RAIL/custom flagged; nothing copied where the license doesn't allow; the $5M/$2M
gates and the EU exclusion are recorded as adoption blockers, not footnotes.

## 2. Architecture (implemented core)

```
document → [classifier] → doc_class → [preprocess planner] → steps
                │                            │
                ▼                            ▼
        [OCR ROUTER: ROUTING_TABLE role lookup] → engine adapter(s)
                │
     critical fields? ──► [MULTI-MODEL CROSS-CHECK]
                │            accepted (high conf OR 2 engines agree)
                │            human_review (disagree OR low conf)
                │            abstained (single engine, mid conf)
                ▼
   [field confidence (05 §6)] → [EvidenceReference page/bbox/snippet]
                ▼
   [abstain / clearer-scan request / human review]  ← the ONLY low-conf exits
                ▼
   [LGGT FactBuilder-compatible output (32)]
```

- **Document type classifier** (`classify_document`): rule-based MVP over cheap signals
  (text layer, page count, handwriting ratio, image quality, table density, languages) →
  8 classes; upgrade path: small vision classifier trained on the Finalis benchmark.
- **Preprocessing pipeline** (`preprocess_plan`): ≥300 DPI upscale, deskew, denoise, CLAHE,
  border removal, binarization — planned per input quality (07 §3).
- **Routing table**: doc class → ordered engine *roles* (not vendors): digital_pdf→structure
  parser; clean_scan/multilingual→primary+layout; degraded/handwritten→robust_vlm+fallback;
  long_multipage→longdoc parser; table_heavy→primary+structure.
- **Multi-model cross-check** (`cross_check`): critical fields accepted only on
  `conf ≥ 0.85` OR two independent engines agreeing at `conf ≥ θ_conf(0.6)`; disagreement or
  low confidence → human review; single-engine mid confidence → abstain. **This is the
  acceptance rule as code.** Tested: agreement, disagreement (8400 vs 3400), low-conf,
  missing-field, and routing cases all pass.
- **Confidence, evidence, abstention, re-scan, human review**: as specified in 05 §6 / 07
  §4–5; the field-level gate is implemented in `finalis/documents.py` with a tested
  "no fourth path" invariant.

## 3. Finalis Document Benchmark

Our own benchmark (proprietary IP, feeds engine selection + regression):
clean PDFs · weak scans · damaged scans · handwritten notes · tables · invoices · contracts ·
notarial-style documents · photos · multi-language documents (full 18-type spec + golden
labels: `29`, fixture inventory: `36`). Every engine adapter is scored on the SAME benchmark
before entering the routing table; vendor OmniDocBench claims are never trusted directly
(they span incomparable bench versions — `21` §1.9).

## 4. Own-model roadmap (5 phases)

| Phase | What | Gate to advance |
|---|---|---|
| 1 (now) | **Router + ensemble** over licensed engines; benchmark harness; evidence/confidence IP | Router in production; benchmark ≥ engine-vendor parity on tenant docs |
| 2 | **Proprietary dataset + benchmark**: consented, anonymized tenant documents + synthetic generation; golden labels; hard-case mining from human-review corrections | ≥10k labeled fields across the 18 types; legal sign-off on data consent |
| 3 | **Supervised fine-tuning where licenses allow** (Apache/MIT bases only: PaddleOCR-VL, olmOCR-2, Qwen — NOT RAIL/Hunyuan-derived) on vertical documents (HVAC offers, invoices, contracts) | Fine-tune beats routed ensemble on the Finalis benchmark for ≥2 doc classes |
| 4 | **Distillation / own compact model** where legally allowed (respect AUP clauses banning "use outputs to train competing models" — Hunyuan explicitly prohibits this; permissive-only teachers) | Own model within 2 pts of ensemble at <⅓ inference cost |
| 5 | **Enterprise on-prem OCR service**: single-container Finalis OCR Engine (own + permissive models only) for data-boundary-sensitive tenants | SOC2-ready packaging; no license-gated weights in the image |

## 5. LGGT compatibility

Router output feeds `FactBuilder` (32): every accepted field becomes an LGGT-compatible
`Fact{key, value, evidence_ref_id, confidence}`; cross-check verdicts and engine agreement
are recorded in the audit log, giving Phase-2 LGGT certification the provenance it needs.
