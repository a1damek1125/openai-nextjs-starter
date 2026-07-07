"""Finalis OCR Engine — router/ensemble core (docs/finalis-ai/47).

Our own IP is NOT an OCR model — it is the layer around pluggable engines:
document-type classification → preprocessing → engine routing → multi-model
cross-check on critical fields → field confidence → abstention/re-scan/human
review. Engines are adapters behind `OCREngineProtocol`; the scaffold ships
mock engines driven by fixtures, the production system plugs real ones
(PaddleOCR-VL, olmOCR 2, Surya, Marker, Mistral API...) behind the same seam.

Acceptance rule (enforced by `cross_check`): no critical decision may rely on
OCR output unless confidence is high, independent models agree, or a human
verified the field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

DocClass = Literal[
    "digital_pdf", "clean_scan", "photo", "degraded_scan", "handwritten",
    "table_heavy", "long_multipage", "multilingual",
]

# Routing policy: doc class → ordered engine preference (doc 47 §3).
# Names are roles, not hard vendor bindings; adapters register under them.
ROUTING_TABLE: dict[str, list[str]] = {
    "digital_pdf": ["structure_parser"],                       # Docling/Marker class
    "clean_scan": ["primary_parser", "layout_ocr"],            # PaddleOCR-VL / Surya class
    "photo": ["primary_parser", "vlm_fallback"],
    "degraded_scan": ["robust_vlm", "vlm_fallback"],           # olmOCR2 / Qwen-VL class
    "handwritten": ["robust_vlm", "vlm_fallback"],
    "table_heavy": ["primary_parser", "structure_parser"],
    "long_multipage": ["longdoc_parser", "structure_parser"],  # Unlimited-OCR class
    "multilingual": ["primary_parser", "layout_ocr"],
}


@dataclass
class OCRFieldResult:
    field_key: str
    value: object
    ocr_confidence: float   # engine-reported [0,1]
    page: int | None = None
    bbox: tuple | None = None
    snippet: str = ""


@dataclass
class OCRResult:
    engine: str
    doc_class: str
    fields: list[OCRFieldResult] = field(default_factory=list)
    overall_quality: float = 0.0


class OCREngineProtocol(Protocol):
    name: str
    def parse(self, document_ref: str, doc_class: str) -> OCRResult: ...


def classify_document(meta: dict) -> DocClass:
    """Document-type classifier (rule-based MVP; model later).

    `meta` carries cheap signals: has_text_layer, page_count, image_quality
    [0,1], handwriting_ratio [0,1], table_density [0,1], languages.
    """
    if meta.get("has_text_layer"):
        return "digital_pdf"
    if meta.get("page_count", 1) > 30:
        return "long_multipage"
    if meta.get("handwriting_ratio", 0.0) > 0.4:
        return "handwritten"
    if meta.get("image_quality", 1.0) < 0.5:
        return "degraded_scan"
    if meta.get("table_density", 0.0) > 0.5:
        return "table_heavy"
    if len(meta.get("languages", ["en"])) > 1:
        return "multilingual"
    if meta.get("is_photo"):
        return "photo"
    return "clean_scan"


def preprocess_plan(meta: dict) -> list[str]:
    """Preprocessing pipeline steps for the input (doc 07 §3)."""
    steps = []
    if meta.get("dpi", 300) < 300:
        steps.append("upscale_to_300dpi")
    if meta.get("skew_deg", 0.0) and abs(meta["skew_deg"]) > 1.0:
        steps.append("deskew")
    if meta.get("noise", 0.0) > 0.3:
        steps.append("denoise")
    if meta.get("contrast", 1.0) < 0.5:
        steps.append("clahe_contrast")
    if meta.get("has_borders"):
        steps.append("border_removal")
    steps.append("binarize" if meta.get("image_quality", 1.0) < 0.7 else "none")
    return [s for s in steps if s != "none"]


class OCRRouter:
    """Routes a document to engines and cross-checks critical fields."""

    def __init__(self, engines: dict[str, OCREngineProtocol], audit) -> None:
        self.engines = engines   # role name → adapter
        self.audit = audit

    def route(self, document_ref: str, meta: dict) -> tuple[DocClass, list[str]]:
        doc_class = classify_document(meta)
        roles = ROUTING_TABLE[doc_class]
        available = [r for r in roles if r in self.engines]
        if not available:
            raise RuntimeError(f"no engine registered for roles {roles}")
        return doc_class, available

    def parse(self, document_ref: str, meta: dict) -> OCRResult:
        doc_class, roles = self.route(document_ref, meta)
        result = self.engines[roles[0]].parse(document_ref, doc_class)
        self.audit.append(event_type="ocr.parsed", actor="ai",
                          payload={"doc": document_ref, "class": doc_class,
                                   "engine": result.engine,
                                   "quality": result.overall_quality})
        return result

    def cross_check(self, document_ref: str, meta: dict,
                    critical_keys: set[str],
                    *, theta_high: float = 0.85,
                    theta_conf: float = 0.6) -> dict[str, dict]:
        """Multi-model cross-check for critical fields (acceptance rule).

        Verdict per critical field:
          - 'accepted'      : primary confidence >= theta_high, OR two engines
                              agree on the value with both >= theta_conf.
          - 'human_review'  : engines disagree, or confidence below theta_conf.
          - 'abstained'     : only one engine available and confidence in
                              [theta_conf, theta_high) — not enough for a
                              critical decision without agreement or a human.
        """
        doc_class, roles = self.route(document_ref, meta)
        results = [self.engines[r].parse(document_ref, doc_class)
                   for r in roles[:2]]
        primary = {f.field_key: f for f in results[0].fields}
        secondary = {f.field_key: f for f in results[1].fields} \
            if len(results) > 1 else {}

        verdicts: dict[str, dict] = {}
        for key in critical_keys:
            p = primary.get(key)
            s = secondary.get(key)
            if p is None:
                verdicts[key] = {"verdict": "human_review",
                                 "reason": "missing_from_primary"}
            elif p.ocr_confidence >= theta_high:
                verdicts[key] = {"verdict": "accepted", "value": p.value,
                                 "reason": f"high_conf={p.ocr_confidence:.2f}"}
            elif s is not None and s.value == p.value \
                    and min(p.ocr_confidence, s.ocr_confidence) >= theta_conf:
                verdicts[key] = {"verdict": "accepted", "value": p.value,
                                 "reason": "two_engines_agree"}
            elif s is not None and s.value != p.value:
                verdicts[key] = {"verdict": "human_review", "value": None,
                                 "reason": f"disagreement:{p.value!r}!={s.value!r}"}
            elif p.ocr_confidence < theta_conf:
                verdicts[key] = {"verdict": "human_review", "value": None,
                                 "reason": f"low_conf={p.ocr_confidence:.2f}"}
            else:
                verdicts[key] = {"verdict": "abstained", "value": None,
                                 "reason": "single_engine_mid_conf"}
            self.audit.append(event_type="ocr.cross_check", actor="ai",
                              payload={"doc": document_ref, "field": key,
                                       **verdicts[key]})
        return verdicts
