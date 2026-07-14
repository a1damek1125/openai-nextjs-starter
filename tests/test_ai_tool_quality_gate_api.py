"""TOOL-B2 — ViktorAI Formal Tool Descriptor Assurance Graph.

App-level surface: every quality endpoint exists and returns 200 for the owner
on a checked tool, every response carries honesty labels, reads before a check
404, and unknown tools 404. Nothing here executes a tool.
"""
from tests.conftest import OWNER, OTHER_OWNER


def _labels_ok(payload):
    hl = payload.get("honesty_labels")
    return isinstance(hl, list) and len(hl) > 0


# (path suffix under /quality, http method) for a checked tool.
QUALITY_ENDPOINTS = [
    ("/check", "POST"),
    ("", "GET"),
    ("/history", "GET"),
    ("/safe", "GET"),
    ("/verify", "POST"),
    ("/diff", "POST"),
    ("/matrix", "GET"),
    ("/evidence", "GET"),
    ("/assurance", "GET"),
    ("/ir", "GET"),
    ("/graph", "GET"),
    ("/confusion", "GET"),
    ("/selection-boundary", "GET"),
    ("/mutation-check", "POST"),
    ("/counterfactual-check", "POST"),
    ("/non-regression", "GET"),
]


class TestEveryEndpointExists:
    def test_all_quality_endpoints_200_for_owner(self, gate):
        tid, _ = gate.checked_quality_tool()
        for path, method in QUALITY_ENDPOINTS:
            r = gate.q(tid, path, actor=OWNER, method=method)
            assert r.status_code == 200, (path, method, r.status_code)
            assert _labels_ok(r.json()), path

    def test_registry_quality_endpoints_200(self, gate):
        gate.checked_quality_tool()
        for path in ("/ai-tools/registry/quality",
                     "/ai-tools/registry/quality/policy"):
            r = gate.c.get(path, headers=gate.h(OWNER))
            assert r.status_code == 200, path
            assert _labels_ok(r.json()), path


class TestEndpointPayloads:
    def test_check_returns_pass_report(self, gate):
        _, rep = gate.checked_quality_tool()
        assert rep["quality_status"] == "QUALITY_PASS"
        assert rep["quality_score_total"] == 155
        assert rep["formal_descriptor_ir"]["ir_matches_tool_b1_truth"] is True

    def test_latest_matches_check(self, gate):
        tid, rep = gate.checked_quality_tool()
        latest = gate.q(tid, "").json()
        assert latest["tool_id"] == tid
        assert latest["quality_report_hash"] == rep["quality_report_hash"]

    def test_history_lists_the_check(self, gate):
        tid, _ = gate.checked_quality_tool()
        hist = gate.q(tid, "/history").json()
        assert hist["count"] >= 1
        assert hist["history"][-1]["quality_status"] == "QUALITY_PASS"

    def test_safe_view_hashes_and_status(self, gate):
        tid, _ = gate.checked_quality_tool()
        view = gate.q(tid, "/safe").json()
        assert view["quality_status"] == "QUALITY_PASS"
        assert view["quality_safe_view_hash"]

    def test_matrix_reports_full_score_vector(self, gate):
        tid, _ = gate.checked_quality_tool()
        m = gate.q(tid, "/matrix").json()
        assert m["quality_score_total"] == 155
        assert isinstance(m["quality_score_vector"], dict)
        assert m["score_vector_hash"]

    def test_ir_endpoint_matches_registry_truth(self, gate):
        tid, _ = gate.checked_quality_tool()
        ir = gate.q(tid, "/ir").json()
        assert ir["formal_descriptor_ir"]["ir_matches_tool_b1_truth"] is True
        assert ir["canonical_descriptor_semantic_record"][
            "canonical_semantic_record_hash"]

    def test_graph_endpoint_is_acyclic_and_matched(self, gate):
        tid, _ = gate.checked_quality_tool()
        g = gate.q(tid, "/graph").json()["descriptor_assurance_graph"]
        assert g["acyclic"] is True
        assert g["assurance_graph_status"] == "MATCHED"

    def test_evidence_and_assurance_carry_hashes(self, gate):
        tid, _ = gate.checked_quality_tool()
        ev = gate.q(tid, "/evidence").json()["quality_evidence_package"]
        ac = gate.q(tid, "/assurance").json()["quality_assurance_case"]
        assert ev["quality_evidence_package_hash"]
        assert ac["quality_assurance_case_hash"]

    def test_verify_matched_on_fresh_report(self, gate):
        tid, _ = gate.checked_quality_tool()
        v = gate.q(tid, "/verify", method="POST").json()
        assert v["verification_status"] == "MATCHED"
        assert v["tamper_detected"] is False

    def test_mutation_and_counterfactual_declare_no_llm(self, gate):
        tid, _ = gate.checked_quality_tool()
        mut = gate.q(tid, "/mutation-check", method="POST").json()
        cf = gate.q(tid, "/counterfactual-check", method="POST").json()
        assert mut["calls_llm"] is False
        assert mut["mutation_harness"]["mutation_harness_version"]
        assert cf["calls_llm"] is False
        assert cf["counterfactual_planner"]["counterfactual_planner_version"]


class TestRegistrySummaries:
    def test_registry_summary_counts_tool(self, gate):
        gate.checked_quality_tool()
        s = gate.c.get("/ai-tools/registry/quality",
                       headers=gate.h(OWNER)).json()
        assert s["tool_count"] >= 1
        assert s["quality_by_status"].get("QUALITY_PASS", 0) >= 1

    def test_registry_policy_declares_no_execution(self, gate):
        p = gate.c.get("/ai-tools/registry/quality/policy",
                       headers=gate.h(OWNER)).json()
        assert p["executes_tools"] is False
        assert p["quality_pass_means_executable"] is False
        assert "NON_REGRESSION" in p["score_dimensions"]


class TestNotFound:
    def test_read_before_check_404(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        # No quality/check has been run yet.
        assert gate.q(tid, "").status_code == 404

    def test_unknown_tool_check_404(self, gate):
        assert gate.q("does-not-exist", "/check",
                      method="POST").status_code == 404

    def test_unknown_tool_read_404(self, gate):
        assert gate.q("does-not-exist", "").status_code == 404

    def test_cross_tenant_read_404(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert gate.q(tid, "", actor=OTHER_OWNER).status_code == 404
