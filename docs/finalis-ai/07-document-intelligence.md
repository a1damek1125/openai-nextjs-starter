# Finalis AI — Document Intelligence & OCR Architecture

> The Document Intelligence Worker turns PDFs, scans, photos, offers, invoices, contracts,
> notarial/property/insurance documents, and messy handwriting into **structured, evidence-
> linked fields with honest confidence** — and never pretends certainty it doesn't have.

## 1. Design principles

1. **Layout-aware, not flat text.** Preserve reading order, tables, and regions so extracted
   fields carry a page + bounding box (evidence). Modern VLM/layout parsers retain structure
   that legacy engines flatten away.
2. **Confidence is mandatory.** Every `ExtractedField` gets `Confidence = OCR_q · Extraction_q
   · Source_q · Consistency_q` (`05`). Below `θ_conf` → abstain and ask for a clearer scan.
3. **Evidence for every claim.** Analysis outputs (`RiskFlag`, contradictions, summaries) link
   to `EvidenceReference{page, bbox, snippet}`.
4. **Never legal advice.** Legal/notarial content is analyzed as *business support* and routed
   to human review; outputs are labeled assistive, not final legal opinion.
5. **Cost-aware routing.** Cheap, fast engines first; escalate to heavier VLMs only when
   needed.

## 2. Engine stack (multi-layer, routed)

We combine complementary open tools rather than betting on one. All are verified from primary
repos except where flagged.

| Layer | Engine | Role | License | Source |
|---|---|---|---|---|
| Structure/parse | **Docling** (v2.110, 2026-07) | PDF/DOCX/PPTX/XLSX/HTML/image/audio → layout, reading order, table structure, formulas; pluggable OCR/VLM backends (incl. nemotron-ocr, Granite-Docling); outputs Markdown/HTML/lossless JSON | **MIT** | IBM Research Zurich origin; hosted in LF AI & Data. https://github.com/docling-project/docling |
| Linearized OCR | **olmOCR 2** (`olmOCR-2-7B-1025`) | PDF/PNG/JPEG → clean linearized Markdown; equations, tables, handwriting, multi-column; v2 adds **RL training with unit-test rewards** | **Apache-2.0** (model+data+code) | Fine-tuned from Qwen2.5-VL-7B; **olmOCR-Bench 82.4 ±1.1** (beats Marker 76.1, MinerU 75.8; bench is English-only). https://github.com/allenai/olmocr , https://arxiv.org/abs/2510.19817 |
| Multilingual doc parse | **PaddleOCR-VL-1.6** (~1B) | ERNIE-4.5-0.3B-based; **111 languages** (1.5); text/tables/formulas/charts → Markdown/JSON; GGUF build available | **weights license UNVERIFIED** (repo Apache-2.0) | Reported **96.33 on OmniDocBench v1.6** (vendor number, [snippet]). https://arxiv.org/abs/2606.03264 (1.6), https://arxiv.org/abs/2601.21957 (1.5), https://huggingface.co/PaddlePaddle/PaddleOCR-VL |
| Compact multilingual alt | **dots.ocr** (1.7B) | Unified layout + recognition + reading order in one VLM; **100+ languages** | **MIT** | Strong OmniDocBench text/tables/reading-order results ([snippet]). https://github.com/rednote-hilab/dots.ocr |
| Hard multimodal | **Qwen2.5-VL / Qwen3-VL** | Omni-document parsing (QwenVL-HTML layout+content), handwriting, tables, charts; Qwen3-VL expands OCR to **32 languages**, robust to low light/blur/tilt | Apache-2.0 (check per-size) | https://arxiv.org/abs/2502.13923 (2.5-VL), https://github.com/qwenlm/qwen3-vl |
| Edge/tiny | **Granite-Docling-258M** | 258M doc-conversion VLM, native Docling integration | **Apache-2.0** | https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion |
| Lightweight layout+OCR | **Surya** | Layout, reading order, table recognition, OCR in **90+ languages**; Surya-2 single VLM | code **Apache-2.0**; weights **AI-Pubs Open RAIL-M** (free under $5M funding/revenue) | https://github.com/datalab-to/surya |

*(Experimental watch: **DeepSeek-OCR** — "optical context compression", ~200k pages/day/A100,
MIT — a genuinely new token-efficiency direction; **MinerU2.5-Pro** — vendor-reported ~95.7 on
OmniDocBench v1.6. All 2026 OmniDocBench scores are vendor-reported and span different bench
versions — validate on the tenant's real document mix before adopting. See `21`.)*

**Cost anchor**: olmOCR reports converting **~1M PDF pages for ~$190** vs. >$6,240/M for
GPT-4o (paper abstract, search-surfaced) — self-hosting the OCR layer is materially cheaper at
volume, which matters for a per-seat SaaS.

### Routing policy (default)
1. **Digital PDF (text layer present)** → Docling (fast, structured) → done.
2. **Clean scan / image** → PaddleOCR-VL or Surya (fast, multilingual) → structure via Docling
   if needed.
3. **Messy scan / handwriting / low quality / non-Latin script** → olmOCR and/or Qwen VL
   (heavier, more robust).
4. **Disagreement or low `Confidence`** → run a second engine and reconcile; if still low →
   request a clearer scan (abstain).

> Engine choices are behind an interface; specific vendors/models can be swapped as the
> frontier moves. Evaluate candidates on the tenant's real document mix in the Evaluation Lab
> before locking defaults.

## 3. Pre-processing (raises accuracy on bad scans)

Before OCR on low-quality inputs: **binarization, deskew, denoise, border removal, DPI
normalization to ≥300 DPI, CLAHE contrast** (CLAHE avoids over-amplifying noise vs. plain
histogram equalization). Vendor guidance reports meaningful accuracy gains on poor scans; the
defensible primary anchors are standard preprocessing practice + Microsoft Document
Intelligence confidence docs. Image quality is scored and folded into `OCR_q` and the `Q`
term of `DocRisk`.

## 4. Field extraction + confidence

- **Schema-constrained extraction**: for each document type the playbook defines a target
  schema (e.g. invoice: supplier, date, line items, totals, VAT; contract: parties, dates,
  price, warranty, payment terms, termination). Extraction is constrained to the schema and
  each field gets a page + bbox.
- **Confidence per field** = product of the four q-factors (`05` §6). Approaches grounded in:
  Azure Document Intelligence's per-word/per-field confidence with a human-review threshold
  (https://learn.microsoft.com/azure/ai-services/document-intelligence/concept/accuracy-confidence);
  research arguing OCR-stage confidence captures the *cause* of extraction failure while
  logprobs capture a *consequence*, motivating **multi-signal** confidence for abstain/route
  decisions ("Beyond Logprobs" — arXiv ID search-surfaced, **verify before quoting**).
- **Calibration**: numeric fields tend well-calibrated; free-text tends overconfident. Apply
  Platt/isotonic calibration and monitor reliability curves in the Evaluation Lab.
- **Extraction accuracy metric**: field-level **F1 (precision/recall)** is the standard IDP
  metric and is what `15-evaluation-lab.md` tracks per field type.
- **Abstain rule**: `Confidence < θ_conf` → field marked *unverified*; if it's a
  quote/decision blocker → `WAITING_FOR_DOCUMENTS` with a specific re-scan request ("photo of
  the boiler label, straight-on, in good light").

## 5. Analysis outputs (per document)

For every analyzed document the worker produces:
1. **Structured fields** (schema) with page/bbox + confidence.
2. **Plain-language summary** (owner-readable).
3. **Missing elements** (expected-but-absent: signatures, dates, attachments, warranty).
4. **Contradictions** — vs. prior agreements, other offers, and the **call/message transcript**
   (uses the Case Graph edges, e.g. `OFFER_CONTRADICTS_AGREEMENT`).
5. **Risk flags** → `RiskFlag` rows feeding `DocRisk` (`05` §5), each with an evidence ref.
6. **Confidence** (document-level = aggregate of field confidences + quality).
7. **Questions for human/legal/notarial review** when content is sensitive or `DocRisk`/
   `EscalationScore` is high.
8. **Re-scan request** when quality gates fail.

Example (contradiction, evidence-linked):
> "The offer states a **24-month warranty** (offer p.2, §Warranty) but the draft contract
> contains **no warranty clause** (contract pp.1–4 scanned; not found). Confidence 0.82 on the
> offer field, 0.6 on 'absent in contract' due to scan quality on p.3. **Recommend human
> review before signing.**"

## 6. Handwriting & low-quality specifics

- Route to olmOCR / Qwen VL (both report handwriting handling); Surya/PaddleOCR-VL for
  multilingual print. Always attach lower `OCR_q` and require corroboration for critical
  handwritten values (bank details, amounts) — handwritten/noisy content keeps
  human-in-the-loop validation on low-confidence extractions.
- Never silently "best-guess" a smudged number that drives a quote or payment — abstain and
  ask.

## 7. Data handling

- Documents live in S3 (encrypted); OCR text + fields in Postgres (`Document`,
  `ExtractedField`); embeddings in pgvector for semantic retrieval across a case's docs and
  against similar past cases (Deal Memory).
- Sensitive types (IDs, contracts, notarial) are access-logged; retention per tenant policy;
  erasure removes object + derived text (`04`, `16`).
- Self-hosting the OCR/VLM layer (all engines above are self-hostable) keeps sensitive
  documents inside the tenant's data boundary — a selling point for privacy-sensitive
  verticals.
