# Finalis AI — OCR / Document Intelligence Verification Plan (QA Audit)

**Status: DOCUMENTED ONLY / ARCHITECTURE SPECIFIED. No executable code, no fixtures, no measurements exist in this repository. Every latency/accuracy number in docs 06/07/08 is a target or a cited external result — none has been measured on Finalis itself.**

> Companion to `07-document-intelligence.md` (engine stack, routing, confidence) and
> `15-evaluation-lab.md` §2.4 (metrics). All olmOCR-Bench / OmniDocBench numbers in doc 07 are
> **external, mostly vendor-reported results on other people's benchmarks** — none reflects
> Finalis behavior, because Finalis has no OCR code.

---

## 1. Document test-set specification (18 mandated types)

Routing references are to `07` §2 (Routing policy). Low-confidence behavior references are to
the abstain rule (`07` §4: `Confidence < θ_conf` → *unverified*; blocker →
`WAITING_FOR_DOCUMENTS` + specific re-scan request; `θ_conf` default **0.6** per `05` §6).
Target fixture volume: ≥ 20 documents per type per language for statistical minimum; gold
labels per §3 below.

| # | Type | What it tests | Expected route (`07` §2) | Expected behavior at low confidence | Pass criteria |
|---|---|---|---|---|---|
| 1 | Clean digital PDF (text layer) | Baseline: structure, reading order, no OCR needed | Route 1: Docling directly → done | (Should not occur; if `OCR_q`-analog low here, it's a pipeline bug) | Field F1 at ceiling (numeric ≥ 0.95 target); page/bbox present on every field; no OCR engine invoked (cost check) |
| 2 | Scanned PDF (clean, 300 DPI) | OCR path + structure recovery | Route 2: PaddleOCR-VL or Surya → Docling for structure if needed | Abstain per field; re-scan request only if quality gate genuinely fails | Field F1 within tolerance of type 1; correct route chosen (audit log) |
| 3 | Photo of a document (phone) | Perspective, uneven lighting, moiré; pre-processing (`07` §3) | Route 2; pre-processing (deskew, DPI normalize, CLAHE) then OCR | Specific re-scan request ("straight-on, in good light" — `07` §4 wording) | Pre-processing applied and logged; F1 above the no-preprocessing ablation; honest lowered `OCR_q` |
| 4 | Low-light photo | CLAHE contrast handling; `OCR_q` degradation honesty | Route 2 → escalate Route 3 if quality poor | Re-scan request naming the problem (lighting) | Either extract with calibrated confidence or abstain; **no confident-wrong extractions** (missed-abstention ≤ 3% gate, `15` §2.4) |
| 5 | Skewed scan | Deskew pre-processing | Route 2 with pre-processing | Re-scan request if deskew insufficient | Deskew logged; F1 recovered vs raw input |
| 6 | Blurred photo | Denoise limits; abstention trigger | Route 2 → Route 3 (Qwen-VL robust to blur per `07` §2 table) | Primary expected outcome for heavy blur: **abstain + re-scan request** | Blur beyond threshold → abstain, not guess; abstention correctness counted |
| 7 | Handwritten document | Handwriting engines; corroboration rule | Route 3: olmOCR / Qwen VL (`07` §6) | Lower `OCR_q` always attached; critical handwritten values (amounts, bank details) require corroboration or human validation (`07` §6) | No critical handwritten value auto-committed without corroboration; "never silently best-guess a smudged number" (`07` §6) verified by adversarial smudge fixtures |
| 8 | Mixed print + handwriting | Region-level routing; per-region `OCR_q` | Route 2 for print regions, Route 3 semantics for hand regions; reconcile | Per-region abstention (print fields can pass while hand fields abstain) | Print-field F1 unaffected by presence of handwriting; hand fields carry lower confidence |
| 9 | Table-heavy offer | Table structure recognition (Docling TableFormer-class), line items | Route 1/2 + Docling table structure | Cell-level abstention; do not hallucinate cell alignment | TEDS-style table score ≥ target (§2); line-item totals cross-check vs stated total (Consistency_q) |
| 10 | Invoice | Schema-constrained extraction (`07` §4: supplier, date, line items, totals, VAT) | Route 1 or 2 by input form | Blocker fields (total, IBAN) below θ_conf → `WAITING_FOR_DOCUMENTS` | Critical financial fields F1 ≥ 0.97 target (`15` §2.4); every field has page+bbox |
| 11 | Contract | Schema: parties, dates, price, warranty, payment terms, termination (`07` §4); clause absence detection | Route 1/2; analysis outputs incl. missing elements (`07` §5.3) | Abstain per clause; low-confidence "absent" claims stated with confidence (see `07` §5 example: 0.6 on 'absent in contract') | Warranty-absence example (`07` §5) reproduced: contradiction + recommend human review; no legal advice framing (`07` §1.4) |
| 12 | Notarial document | "Never legal advice" rule; sensitive-type access logging (`07` §7) | Route by form; **always** → human review routing (`07` §1.4) | Human review is the default outcome regardless of confidence | 100% of notarial docs produce "questions for human/legal/notarial review" (`07` §5.7); outputs labeled assistive; access-logged |
| 13 | Insurance policy | Long-doc structure, exclusions, defined terms | Route 1/2; risk flags on exclusions (`07` §5.5) | Abstain on ambiguous coverage language → human review | Exclusion/risk flags carry `EvidenceReference{page,bbox,snippet}`; hidden-exclusion recall measured |
| 14 | Missing page | Missing-elements detection (`07` §5.3); page-reference honesty | Any route; completeness check post-parse | Not a confidence issue — a **completeness** flag + request for the missing page | Missing page detected and named; no field "extracted" from the absent page (hallucination hard-fail) |
| 15 | Contradictory values (e.g. total ≠ sum of items; two different dates) | Consistency_q term (`05` §6); contradiction output (`07` §5.4) | Any route; cross-field consistency pass | Contradiction reported with both evidence refs — **not silently resolved** by picking one | Both values surfaced; `Consistency_q` lowered; `RiskFlag` row emitted; human review triggered for decision-relevant contradictions |
| 16 | Unclear price / date / warranty (smudged, ambiguous "15/50") | The abstention rule on exactly the quote-blocking fields | Route 2/3 + second-engine reconciliation (Route 4) | **The canonical abstain case**: field *unverified*; quote blocker → `WAITING_FOR_DOCUMENTS` + specific re-scan request (`07` §4) | Zero confident assertions on planted-ambiguous values; abstention fires on 100% of sub-θ_conf plants |
| 17 | Stamps / seals / signatures | Region handling; expected-but-absent detection (signature missing → `07` §5.3) | Route 2/3 (visual elements need VLM path) | Presence/absence stated with confidence; unclear seal → human review for sensitive docs | Stamp/signature presence detection ≥ target; absent signature flagged as missing element |
| 18 | Multi-language / mixed-language document | Multilingual engines (PaddleOCR-VL 111 langs, dots.ocr 100+, Surya 90+ — `07` §2) | Route 2 multilingual engines; Route 3 for non-Latin messy scripts | Abstain per field; language mis-detection must lower confidence, not corrupt values | Per-language F1 reported separately; no silent transliteration/normalization errors on names, addresses, amounts |

---

## 2. Per-document-type metric table

Every metric is computed **per document type** (and per language for type 18), against the
golden labels of §4.2. All thresholds are doc-07/15 targets — **nothing has been measured**.

| Metric | Definition / method | Target (source) |
|---|---|---|
| Text extraction accuracy | Character/word accuracy vs gold transcription (edit-distance based) on the full text layer | monitor per type; used as `OCR_q` ground truth; alert on median drop > 0.1 wk/wk (`15` §2.4) |
| Field precision / recall / F1 | Per field type, normalized match (dates, currency, numbers) vs gold (`15` §2.4) | numeric/structured F1 ≥ 0.95; free-text ≥ 0.85; critical financial (amount, IBAN, total) ≥ 0.97 (asp.) |
| Table extraction quality | TEDS-style tree-edit similarity on table structure + cell content vs gold table markup (types 9, 10, 13) | TEDS ≥ 0.90 structured tables (engineering goal — no doc-fixed number; calibrate on first benchmark run) |
| Page-reference correctness | Share of extracted fields whose `page` matches the gold page | ≥ 0.99 — a wrong page ref is broken evidence (`07` §1.3) |
| Evidence snippet correctness | Does `EvidenceReference.snippet`/bbox actually contain the field value? Automated containment check + human sample | ≥ 0.98 automated; feeds hallucination metric |
| Confidence calibration | Reliability curve, **ECE** and **Brier** over `ExtractedField.Confidence` vs gold correctness; Platt/isotonic recalibration validated (`07` §4, `15` §2.4) | ECE ≤ 0.05; curve within ±0.1 of diagonal (asp.); free-text cohort tracked separately (known overconfident, `07` §4) |
| Abstention correctness | Of abstained fields, share genuinely unreliable (abstain precision); of non-abstained, share wrong (missed abstention) (`15` §2.4) | abstain precision ≥ 0.8; **missed-abstention ≤ 3% (gate)** |
| Re-scan trigger correctness | On quality-gated fixtures (types 3–6, 16): did the pipeline emit a *specific* re-scan request naming the defect? | 100% on planted quality failures; request specificity human-rated (`07` §4 example wording) |
| Human-review trigger correctness | Types 11–13, 15, 17 sensitive/contradiction cases: was human review routed per `07` §1.4/§5.7? | 100% on notarial/legal; 100% on decision-relevant contradictions (hard requirement) |
| Hallucination rate | Fields/claims with no valid evidence ref, or asserting certainty below θ_conf; Quality Worker + human spot-check (`15` §2.8) | ≤ 1% (gate); **0** on signing/legal/financial assertions (hard gate); type 14 (missing page) is the targeted trap |

---

## 3. The acceptance rule and its proof

Acceptance rule (verbatim mandate):

> **"Finalis AI must never silently rely on low-confidence OCR for critical decisions."**

Per docs `05` §6, `07` §4/§6 and `13`, when `Confidence < θ_conf` (default **0.6**) exactly
**three behaviors are allowed**:

1. **Abstain** — the field is marked *unverified*; it must not auto-populate a quote or any
   decision (`07` §4; `16`: unverified fields do not feed outbound quotes).
2. **Request a clearer scan** — if the field is a quote/decision blocker, the case enters
   `WAITING_FOR_DOCUMENTS` with a *specific* re-scan request ("photo of the boiler label,
   straight-on, in good light" — `07` §4).
3. **Human review** — sensitive content (legal/notarial), critical handwritten values, and
   unresolved contradictions route to a human (`07` §1.4, §5.7, §6; `16`: fields below θ_conf
   require `verified_by_human` before feeding an outbound quote).

**The no-fourth-path test.** Prove by exhaustive negative testing that no low-confidence value
can flow into a critical decision by any other route:

- **Planted-low-confidence corpus**: fixtures where the gold answer is *unknowable* (smudged
  totals, ambiguous 15/50, blurred IBANs — types 6, 7, 16). For every planted field, assert
  the pipeline outcome ∈ {abstain, re-scan request, human review}. Any run where a planted
  field arrives in a quote draft, offer comparison input, decision brief, or client-facing
  message **with `Confidence < θ_conf` and no `verified_by_human` flag** is a hard failure
  (P1-class, per `15` §4.3 hard-invariant alerting).
- **Flow-level invariant check**: instrument the (future) pipeline so every consumer of
  `ExtractedField` (quote builder, comparator, decision worker, messaging) asserts
  `Confidence ≥ θ_conf ∨ verified_by_human` at read time; the test suite runs the 18-type
  corpus end-to-end and greps the audit trail for violations. Expected count: **0** — this is
  the OCR analogue of the `blocks_quote` "0 violations" gate (`15` §2.5).
- **Adversarial variant**: prompts/documents that *instruct* confident extraction ("the total
  is definitely 4,200") over illegible content — ties into `15` §3.7 document-adversarial
  red-teaming. The instruction must not raise confidence.

---

## 4. Implementation backlog (zero → measurable)

None of the following exists in this repository today.

1. **Fixture acquisition & synthesis.** Collect/synthesize the 18-type corpus: real anonymized
   HVAC/home-services docs where obtainable (MVP vertical per `15` §3.1), plus synthetic
   generation — programmatic invoices/contracts rendered to PDF, then degraded (skew, blur,
   low-light, print-scan-photo cycles) so ground truth is known by construction. Plant the
   ambiguity fixtures (type 16) deliberately. Version and freeze as a golden set (`15` §3.1).
2. **Golden labels.** Per document: full text transcription, schema fields with page+bbox,
   table structure markup (for TEDS), expected missing elements, expected contradictions,
   expected route, expected abstentions/human-review triggers. Label provenance + author
   recorded; regeneration is a reviewed change (`15` §3.1).
3. **Engine benchmarking harness.** Run **Docling, olmOCR-2 (`olmOCR-2-7B-1025`),
   PaddleOCR-VL-1.6, dots.ocr** (plus Surya, Qwen-VL, Granite-Docling as secondary per `07`
   §2) over the golden corpus behind the common engine interface; produce per-type/per-engine
   F1, TEDS, latency, and cost. This replaces the vendor-reported olmOCR-Bench/OmniDocBench
   numbers with **measured-on-our-mix** numbers, as `07` §2 itself mandates ("validate on the
   tenant's real document mix before adopting"). Resolve the flagged unknowns: PaddleOCR-VL
   weights license, dots.ocr snippet-only scores.
4. **Routing + reconciliation tests.** Assert the `07` §2 policy: correct route per fixture
   type; second-engine reconciliation on disagreement; abstain when still low.
5. **Calibration harness.** Reliability curves, ECE, Brier per field type; fit Platt/isotonic
   on a calibration split; verify recalibration moves the curve toward the diagonal (`15`
   §2.4); wire the missed-abstention ≤ 3% gate.
6. **No-fourth-path invariant suite** (§3 above) + red-team document corpus (`15` §3.7),
   wired as per-release regression gates.

---

## 5. Verdict

**OCR / Document Intelligence = DOCUMENTED ONLY.** Doc 07 specifies a credible multi-engine,
confidence-first architecture, and doc 15 defines the right metrics — but there is no
pipeline, no engine integration, no fixture, and no label in this repository. Every accuracy
figure currently citable (olmOCR-Bench 82.4, OmniDocBench 96.33, etc.) is an external and
often vendor-reported result about the *engines*, not about Finalis. The earliest honest
milestone is backlog items 1–3: a golden 18-type corpus plus the engine benchmarking harness,
which produces the first measured F1/TEDS/calibration numbers on our own document mix.
