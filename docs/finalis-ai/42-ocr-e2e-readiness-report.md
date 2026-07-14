# Finalis AI — OCR E2E Readiness Report

> Reviewer report on branch `claude/finalis-ai-enterprise-e2e-autofix` (scaffold: 102 passing
> tests). Companion to `07-document-intelligence.md`, `29-ocr-document-verification-plan.md`,
> `47-finalis-ocr-engine.md`, `36-test-fixtures-plan.md`.

## Verdict

**OCR router/gating core = Implemented and tested (scaffold, mock engines). Real OCR =
Designed.**

The proprietary layer — classifier, preprocessing planner, routing table, multi-model
cross-check, field confidence gate, abstention/re-scan/human-review workflow — is real,
executable code in `finalis/ocr_router.py` and `finalis/documents.py`, exercised by
`tests/test_documents_webscout_ocr.py`. Every engine behind it is a mock driven by fixture
values (`MockEngine` in the test file); no real OCR model is wired.

## What IS tested (all in `tests/test_documents_webscout_ocr.py`)

**Router core (`TestOCRRouter`):**

- `test_classifier` — the rule-based classifier over cheap signals returns all 7
  non-default classes (`digital_pdf`, `long_multipage`, `handwritten`, `degraded_scan`,
  `table_heavy`, `multilingual`, and the `clean_scan` default; `photo` is covered by the
  routing table).
- `test_preprocess_plan` — low-DPI/skewed/noisy/low-contrast input yields exactly
  `[upscale_to_300dpi, deskew, denoise, clahe_contrast, binarize]`; a clean input yields
  no steps.
- `test_routing_degraded_scan_prefers_robust_vlm` — `image_quality: 0.3` classifies as
  `degraded_scan` and routes to `robust_vlm` first (olmOCR-2/Qwen-VL role class).
- `test_high_confidence_accepted_without_second_engine` — conf 0.95 ≥ θ_high → `accepted`,
  reason `high_conf`.
- `test_two_engines_agree_accepts_mid_confidence` — 0.70/0.75 with equal values →
  `accepted`, reason `two_engines_agree`.
- `test_disagreement_goes_to_human` — **the 8400 vs 3400 case**: two engines disagreeing on
  `price` → `human_review` with a `disagreement` reason, plus an `ocr.cross_check` audit
  event.
- `test_low_confidence_goes_to_human` — 0.3/0.4 → `human_review`.
- `test_missing_critical_field_goes_to_human` — critical key absent from the primary
  engine's output → `human_review` (`missing_from_primary`).
- `test_no_engine_for_class_fails_loudly` — an empty engine registry raises `RuntimeError`
  at routing time; no silent degradation.

**Document confidence gate (`TestDocumentConfidenceGate`, `finalis/documents.py`):**

- `test_high_confidence_accepted` — conf ≥ θ_conf → `accepted`.
- `test_low_confidence_critical_goes_to_human` — critical + low conf → `human_review` and
  an `approval.requested` audit event.
- `test_low_confidence_noncritical_abstains` — non-critical + low conf → `abstained`.
- `test_terrible_scan_triggers_rescan_request` — `ocr_quality` below the quality gate →
  the whole document becomes `needs_rescan`, nothing accepted, audited.
- `test_no_fourth_path_exists` — the invariant: every low-confidence field lands in exactly
  one of {`abstained`, `rescan_requested`, `human_review`}; nothing accepted below θ_conf.

The gate is also exercised inside the E2E flow (`tests/test_e2e_mvp_flow.py`): a
quote-critical `room_area_m2` at confidence 0.378 is routed to `human_review` while the
case itself proceeds.

## The acceptance rule is enforced IN CODE

From the module docstring of `finalis/ocr_router.py`:

> *"No critical decision may rely on OCR output unless confidence is high, independent
> models agree, or a human verified the field."*

The enforcement point is `OCRRouter.cross_check` (`finalis/ocr_router.py`): per critical
field the verdict is `accepted` only when `primary confidence >= theta_high (0.85)` OR two
engines agree on the value with both `>= theta_conf (0.6)`; disagreement or low confidence →
`human_review`; single-engine mid confidence → `abstained`. Each verdict emits an
`ocr.cross_check` audit event. This is not documentation — it is the tested control flow.

## Fixture status — honest labeling

- **Mock JSON fixtures only.** The scaffold consumes pre-computed OCR field values
  (`MockEngine` fixtures, and `Document.fields` built inline in tests). The GATING logic is
  real; the OCR output is not.
- **The 18-type real benchmark is NOT built.** The Finalis Document Benchmark — 18 document
  types (digital PDFs, scanned offers, invoices, contracts, notarial deeds, registry
  extracts, nameplate photos, handwritten notes, multilingual docs, …) with golden labels —
  is specified in `29` (type catalogue + verification plan) and `36` §5 (fixture
  inventory), and does not exist as files.
- **Handwritten + weak scans: planned, not supported yet.** The routing is DESIGNED and
  tested at the policy level (`handwritten`/`degraded_scan` → `robust_vlm` role), but no
  real engine is attached to that role. Until olmOCR-2-class capacity is wired and
  benchmarked, handwriting and weak-scan support must be stated as **planned**, never as
  working.

## Backlog to real OCR

1. **Wire real engine adapters** behind `OCREngineProtocol`: PaddleOCR-VL-1.6
   (`primary_parser`), olmOCR-2 (`robust_vlm`), Docling (`structure_parser`) — the
   SAFE-CORE set whose code+weights licenses are verified in `47` §1 (Apache-2.0/MIT;
   Marker deliberately avoided for GPL+RAIL, Surya usable only under its $5M gate,
   HunyuanOCR blocked for EU tenants).
2. **Build the Finalis Document Benchmark** — the 18-type fixture set with golden labels
   per `29`/`36`, including the 10 handwritten items and degraded-scan variants; score
   every adapter on the same benchmark.
3. **Calibrate confidences** — engine-reported confidences must be calibrated (ECE/Brier
   against golden labels) before θ_high/θ_conf are meaningful on real output; recalibrate
   per engine and per doc class.
4. **Enable cross-check on real engines** — run `cross_check` with two independent real
   engines on critical fields, tune thresholds from benchmark data, and add the
   disagreement/abstention rates to the Evaluation Lab regression gates.

The router core will not need to change for any of this — that seam (roles, not vendors) is
the point of the design and is what the 102-test scaffold already proves.
