"""TOOL-B2 formal descriptor IR tests.

Covers the deterministic descriptor interpretation (``build_formal_ir``): it
derives action verbs / payment terms from prose, escalates (never downgrades)
against TOOL-B1 registry truth, is negation-aware, hashes deterministically and
self-excludingly, and is surfaced by the GET /quality/ir endpoint.

Kernel is exercised directly (``tool_quality as tq``) and via the ``gate``
fixture endpoints. No product file is modified; no tool executes.
"""
from finalis.ai_employee import tool_quality as tq
from tests.conftest import OWNER, VIEWER


def _ir(descriptor, *, category="DATA_SEARCH", side_effect="PURE_READ",
        risk="TRIVIAL"):
    return tq.build_formal_ir(
        descriptor=descriptor, tenant_id="t1", tool_id="tool1",
        tool_version_id="v1", source_descriptor_hash="deadbeef",
        b1_category=category, b1_side_effect=side_effect, b1_risk=risk,
        b1_prompt_exposure="NAME_AND_SUMMARY")


class TestIrMatchesTruth:
    def test_clean_report_ir_matches_registry_truth(self, gate):
        _, rep = gate.checked_quality_tool()
        ir = rep["formal_descriptor_ir"]
        assert ir["ir_matches_tool_b1_truth"] is True
        assert ir["ir_mismatch_reasons"] == []

    def test_clean_report_ir_guesses_read_only(self, gate):
        _, rep = gate.checked_quality_tool()
        ir = rep["formal_descriptor_ir"]
        assert ir["ir_side_effect_guess"] == "PURE_READ"
        assert ir["ir_risk_guess"] == "TRIVIAL"
        assert ir["ir_category_guess"] == "DATA_READ"

    def test_clean_kernel_ir_matches_pure_read_truth(self):
        ir = _ir({"tool_name": "Search Local Cases",
                  "tool_summary": "read only local case search",
                  "tool_description": "Read-only keyword search over local "
                  "cases. No side effects, no external calls, no writes."})
        assert ir["ir_matches_tool_b1_truth"] is True
        assert ir["ir_mismatch_reasons"] == []


class TestIrEscalation:
    def test_payment_prose_on_data_search_mismatches(self):
        ir = _ir({"tool_name": "Search Cases",
                  "tool_summary": "searches cases",
                  "tool_description": "charges the customer card and moves "
                  "money to the bank"})
        assert ir["ir_matches_tool_b1_truth"] is False
        assert ir["ir_mismatch_reasons"]

    def test_payment_prose_escalates_side_effect_and_risk(self):
        ir = _ir({"tool_name": "Search Cases",
                  "tool_summary": "searches cases",
                  "tool_description": "charges the customer card and moves "
                  "money to the bank"})
        assert ir["ir_side_effect_guess"] == "PAYMENT_MOVEMENT"
        assert ir["ir_risk_guess"] == "HIGH"
        assert ir["ir_category_guess"] == "PAYMENT"

    def test_payment_prose_via_registered_report_flags_mismatch(self, gate):
        body = gate.quality_tool_body(
            tool_name="Case Finder",
            tool_description="Finds cases; also charges the customer card and "
            "moves money to the bank account.")
        tid = gate.register_quality_tool(body=body).json()["tool_id"]
        rep = gate.quality_check(tid).json()
        ir = rep["formal_descriptor_ir"]
        assert ir["ir_matches_tool_b1_truth"] is False
        assert "formal_ir_mismatch" in [b["code"]
                                        for b in rep["quality_blockers"]]


class TestIrNegationAware:
    def test_negation_suppresses_externality_and_side_effect(self):
        ir = _ir({"tool_name": "Reader",
                  "tool_summary": "reads records",
                  "tool_description": "reads records with no external calls, "
                  "no writes, no side effects"})
        assert ir["detected_externality_terms"] == []
        assert ir["detected_side_effect_terms"] == []
        assert ir["ir_matches_tool_b1_truth"] is True

    def test_negation_still_matches_pure_read_truth(self):
        ir = _ir({"tool_name": "Reader", "tool_summary": "reads",
                  "tool_description": "no writes and no side effects here"})
        assert ir["ir_side_effect_guess"] == "PURE_READ"


class TestIrDetectedTerms:
    def test_action_verbs_populated_for_read_tool(self):
        ir = _ir({"tool_name": "Search Cases", "tool_summary": "read data",
                  "tool_description": "read and search the local case records"})
        assert "read" in ir["detected_action_verbs"]
        assert "search" in ir["detected_action_verbs"]
        assert ir["detected_payment_terms"] == []

    def test_payment_terms_populated_for_payment_prose(self):
        ir = _ir({"tool_name": "Payer", "tool_summary": "moves money",
                  "tool_description": "processes a refund and pays the invoice "
                  "with the card"})
        assert set(ir["detected_payment_terms"]) & {"refund", "pay", "invoice",
                                                    "card"}

    def test_detected_action_verbs_sorted(self):
        ir = _ir({"tool_name": "T", "tool_summary": "s",
                  "tool_description": "search read fetch list the data"})
        assert ir["detected_action_verbs"] == sorted(
            ir["detected_action_verbs"])


class TestIrHash:
    def test_hash_deterministic(self):
        d = {"tool_name": "X", "tool_summary": "y",
             "tool_description": "reads local data records"}
        a = _ir(d)
        b = _ir(d)
        assert a["formal_descriptor_ir_hash"] == b["formal_descriptor_ir_hash"]

    def test_hash_self_excluding(self):
        ir = _ir({"tool_name": "X", "tool_summary": "y",
                  "tool_description": "reads local data records"})
        recomputed = tq._core_hash(ir, "formal_descriptor_ir_hash")
        assert recomputed == ir["formal_descriptor_ir_hash"]

    def test_hash_changes_with_prose(self):
        clean = _ir({"tool_name": "X", "tool_summary": "y",
                     "tool_description": "reads local data records"})
        danger = _ir({"tool_name": "X", "tool_summary": "y",
                      "tool_description": "charges the card and moves money"})
        assert clean["formal_descriptor_ir_hash"] != danger[
            "formal_descriptor_ir_hash"]


class TestIrEndpoint:
    def test_ir_endpoint_returns_ir_and_semantic_record(self, gate):
        tid, _ = gate.checked_quality_tool()
        r = gate.q(tid, "/ir", actor=OWNER)
        assert r.status_code == 200
        body = r.json()
        assert "formal_descriptor_ir" in body
        assert "canonical_descriptor_semantic_record" in body
        assert body["formal_descriptor_ir"]["ir_matches_tool_b1_truth"] is True

    def test_ir_endpoint_semantic_record_fields(self, gate):
        tid, _ = gate.checked_quality_tool()
        rec = gate.q(tid, "/ir", actor=OWNER).json()[
            "canonical_descriptor_semantic_record"]
        assert rec["ir_side_effect_guess"] == "PURE_READ"
        assert "read" in rec["action_verbs"]

    def test_ir_endpoint_requires_prior_check(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        assert gate.q(tid, "/ir", actor=OWNER).status_code == 404

    def test_ir_endpoint_readable_by_viewer(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert gate.q(tid, "/ir", actor=VIEWER).status_code == 200
