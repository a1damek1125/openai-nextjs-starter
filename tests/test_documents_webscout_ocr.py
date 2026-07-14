"""Document confidence gate (07), WebScout policy (08), OCR Router (47) tests."""
import pytest

from finalis.audit import AuditLog
from finalis.documents import THETA_CONF, ingest_document
from finalis.models import Case, Document, ExtractedField
from finalis.ocr_router import (
    OCRFieldResult, OCRResult, OCRRouter, classify_document, preprocess_plan,
)
from finalis.webscout import FixturePage, RestrictionViolation, WebScout


def make_case() -> Case:
    return Case(tenant_id="t1")


def make_field(key: str, value, conf_each: float) -> ExtractedField:
    return ExtractedField(field_key=key, field_value=value, page=1,
                          ocr_q=conf_each, extraction_q=1.0, source_q=1.0,
                          consistency_q=1.0)


class TestDocumentConfidenceGate:
    """Acceptance rule: never silently rely on low-confidence OCR."""

    def test_high_confidence_accepted(self):
        case, audit = make_case(), AuditLog()
        doc = Document(doc_type="offer", ocr_quality=0.9,
                       fields=[make_field("price", 8400, 0.95)])
        decisions = ingest_document(case, doc, audit)
        assert decisions[0].outcome == "accepted"

    def test_low_confidence_critical_goes_to_human(self):
        case, audit = make_case(), AuditLog()
        doc = Document(doc_type="offer", ocr_quality=0.8,
                       fields=[make_field("price", 8400, 0.5)])
        decisions = ingest_document(case, doc, audit,
                                    critical_fields={"price"})
        assert decisions[0].outcome == "human_review"
        assert len(audit.events(event_type="approval.requested")) == 1

    def test_low_confidence_noncritical_abstains(self):
        case, audit = make_case(), AuditLog()
        doc = Document(doc_type="offer", ocr_quality=0.8,
                       fields=[make_field("color_preference", "blue", 0.4)])
        decisions = ingest_document(case, doc, audit)
        assert decisions[0].outcome == "abstained"

    def test_terrible_scan_triggers_rescan_request(self):
        case, audit = make_case(), AuditLog()
        doc = Document(doc_type="contract", ocr_quality=0.2,
                       fields=[make_field("warranty", "24m", 0.9)])
        decisions = ingest_document(case, doc, audit)
        assert all(d.outcome == "rescan_requested" for d in decisions)
        assert doc.status == "needs_rescan"
        assert len(audit.events(event_type="document.needs_rescan")) == 1

    def test_no_fourth_path_exists(self):
        """Every low-confidence field lands in exactly one of the 3 safe exits."""
        case, audit = make_case(), AuditLog()
        doc = Document(doc_type="invoice", ocr_quality=0.7, fields=[
            make_field("total", 1200, 0.55),        # critical, low
            make_field("note", "thanks", 0.55),     # non-critical, low
            make_field("iban", "PL61...", 0.99),    # critical, high
        ])
        decisions = ingest_document(case, doc, audit,
                                    critical_fields={"total", "iban"})
        outcomes = {d.field.field_key: d.outcome for d in decisions}
        assert outcomes == {"total": "human_review", "note": "abstained",
                            "iban": "accepted"}
        for d in decisions:
            if d.field.confidence < THETA_CONF:
                assert d.outcome in {"abstained", "rescan_requested",
                                     "human_review"}


class FixtureFetcher:
    def __init__(self, pages: dict[str, FixturePage]):
        self.pages = pages

    def fetch(self, url: str) -> FixturePage:
        return self.pages[url]


class TestWebScoutPolicy:
    def make_scout(self, page: FixturePage) -> WebScout:
        return WebScout(FixtureFetcher({page.url: page}), AuditLog())

    def test_public_page_researched_with_source_record(self):
        page = FixturePage(url="https://maker.example/spec.pdf",
                           source_type="manufacturer_pdf",
                           content="12kW unit, MSRP 9200 EUR, 5y warranty")
        scout = self.make_scout(page)
        src = scout.research(page.url, date_checked="2026-07-07",
                             trust_inputs={"authority": .9, "recency": .8,
                                           "corroboration": .5,
                                           "directness": 1.0,
                                           "transparency": 1.0},
                             relevance=0.9)
        assert src.trust_score == pytest.approx(81.5)
        assert src.url == page.url and src.date_checked == "2026-07-07"
        assert src.snippet.startswith("12kW unit")

    @pytest.mark.parametrize("flag", ["requires_login", "paywalled",
                                      "captcha", "robots_disallowed"])
    def test_hard_restrictions_refuse_loudly(self, flag):
        page = FixturePage(url="https://gated.example/x",
                           source_type="retailer", content="secret",
                           **{flag: True})
        scout = self.make_scout(page)
        with pytest.raises(RestrictionViolation):
            scout.research(page.url, date_checked="2026-07-07",
                           trust_inputs={}, relevance=0.5)
        assert len(scout.audit.events(event_type="webscout.blocked")) == 1


class MockEngine:
    def __init__(self, name: str, fields: list[OCRFieldResult],
                 quality: float = 0.9):
        self.name = name
        self._fields = fields
        self._quality = quality

    def parse(self, document_ref: str, doc_class: str) -> OCRResult:
        return OCRResult(engine=self.name, doc_class=doc_class,
                         fields=list(self._fields),
                         overall_quality=self._quality)


class TestOCRRouter:
    def test_classifier(self):
        assert classify_document({"has_text_layer": True}) == "digital_pdf"
        assert classify_document({"page_count": 60}) == "long_multipage"
        assert classify_document({"handwriting_ratio": 0.7}) == "handwritten"
        assert classify_document({"image_quality": 0.3}) == "degraded_scan"
        assert classify_document({"table_density": 0.8}) == "table_heavy"
        assert classify_document({"languages": ["pl", "de"]}) == "multilingual"
        assert classify_document({}) == "clean_scan"

    def test_preprocess_plan(self):
        steps = preprocess_plan({"dpi": 150, "skew_deg": 4.0, "noise": 0.5,
                                 "contrast": 0.3, "image_quality": 0.4})
        assert steps == ["upscale_to_300dpi", "deskew", "denoise",
                         "clahe_contrast", "binarize"]
        assert preprocess_plan({"dpi": 300, "image_quality": 0.9}) == []

    def _router(self, primary_conf: float, secondary_value, secondary_conf=0.8):
        audit = AuditLog()
        primary = MockEngine("paddle-vl", [OCRFieldResult(
            "price", 8400, primary_conf, page=2, snippet="Cena: 8 400 EUR")])
        secondary = MockEngine("olmocr2", [OCRFieldResult(
            "price", secondary_value, secondary_conf, page=2)])
        return OCRRouter({"primary_parser": primary, "layout_ocr": secondary},
                         audit), audit

    def test_high_confidence_accepted_without_second_engine(self):
        router, _ = self._router(0.95, 8400)
        v = router.cross_check("doc1", {}, {"price"})
        assert v["price"]["verdict"] == "accepted"
        assert v["price"]["reason"].startswith("high_conf")

    def test_two_engines_agree_accepts_mid_confidence(self):
        router, _ = self._router(0.7, 8400, 0.75)
        v = router.cross_check("doc1", {}, {"price"})
        assert v["price"] == {"verdict": "accepted", "value": 8400,
                              "reason": "two_engines_agree"}

    def test_disagreement_goes_to_human(self):
        router, audit = self._router(0.7, 3400, 0.75)   # 8400 vs 3400!
        v = router.cross_check("doc1", {}, {"price"})
        assert v["price"]["verdict"] == "human_review"
        assert "disagreement" in v["price"]["reason"]
        assert len(audit.events(event_type="ocr.cross_check")) == 1

    def test_low_confidence_goes_to_human(self):
        router, _ = self._router(0.3, 8400, 0.4)
        v = router.cross_check("doc1", {}, {"price"})
        assert v["price"]["verdict"] == "human_review"

    def test_missing_critical_field_goes_to_human(self):
        audit = AuditLog()
        empty = MockEngine("paddle-vl", [])
        router = OCRRouter({"primary_parser": empty, "layout_ocr": empty},
                           audit)
        v = router.cross_check("doc1", {}, {"vin"})
        assert v["vin"]["verdict"] == "human_review"

    def test_routing_degraded_scan_prefers_robust_vlm(self):
        audit = AuditLog()
        robust = MockEngine("olmocr2", [])
        router = OCRRouter({"robust_vlm": robust, "vlm_fallback": robust},
                           audit)
        doc_class, roles = router.route("doc1", {"image_quality": 0.3})
        assert doc_class == "degraded_scan"
        assert roles[0] == "robust_vlm"

    def test_no_engine_for_class_fails_loudly(self):
        router = OCRRouter({}, AuditLog())
        with pytest.raises(RuntimeError):
            router.route("doc1", {"has_text_layer": True})
