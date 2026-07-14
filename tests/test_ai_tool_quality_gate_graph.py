"""TOOL-B2 descriptor assurance graph tests.

Covers ``build_assurance_graph`` / ``_is_acyclic``: a clean tool graph is
MATCHED, acyclic and free of unsupported claims; an unsupported positive claim
yields MISMATCHED; blockers map to violated invariants; a cyclic edge set is
detected and forces FAILED; the graph hash is deterministic and self-excluding;
and GET /quality/graph surfaces it.

No product file is modified; no tool executes.
"""
from finalis.ai_employee import tool_quality as tq
from tests.conftest import OWNER


def _graph(*, checks=None, blockers=None, warnings=None, positive_claims=None):
    return tq.build_assurance_graph(
        tool_id="t", tenant_id="te", tool_version_id="v",
        source_hashes={"h1": "aaa"},
        checks=checks if checks is not None else [
            {"id": "linter", "type": "LINTER_RESULT", "source": "h1",
             "result": "run"}],
        blockers=blockers or [], warnings=warnings or [],
        positive_claims=positive_claims if positive_claims is not None else [
            {"text": "clear", "supported_by": ["linter"]}])


class TestCleanGraph:
    def test_clean_report_graph_matched(self, gate):
        _, rep = gate.checked_quality_tool()
        g = rep["descriptor_assurance_graph"]
        assert g["assurance_graph_status"] == "MATCHED"
        assert g["acyclic"] is True
        assert g["unsupported_claims"] == []
        assert g["violated_invariants"] == []

    def test_clean_kernel_graph_matched_acyclic(self):
        g = _graph()
        assert g["assurance_graph_status"] == "MATCHED"
        assert g["acyclic"] is True
        assert g["unsupported_claims"] == []

    def test_report_graph_nodes_edges_are_acyclic(self, gate):
        _, rep = gate.checked_quality_tool()
        g = rep["descriptor_assurance_graph"]
        assert tq._is_acyclic(g["nodes"], g["edges"]) is True


class TestUnsupportedClaims:
    def test_empty_supported_by_is_unsupported(self):
        g = _graph(positive_claims=[{"text": "clear", "supported_by": []}])
        assert g["unsupported_claims"] == ["clear"]
        assert g["assurance_graph_status"] == "MISMATCHED"

    def test_supported_claim_not_unsupported(self):
        g = _graph(positive_claims=[
            {"text": "supported", "supported_by": ["linter"]},
            {"text": "orphan", "supported_by": []}])
        assert g["unsupported_claims"] == ["orphan"]
        assert "supported" not in g["unsupported_claims"]
        assert g["assurance_graph_status"] == "MISMATCHED"


class TestBlockersToInvariants:
    def test_blocker_maps_to_violated_invariant(self):
        g = _graph(blockers=[{"code": "name_reserved", "category": "OVERBROAD"}])
        assert g["violated_invariants"] == ["OVERBROAD"]
        assert g["assurance_graph_status"] == "MISMATCHED"

    def test_multiple_blockers_deduped_and_sorted(self):
        g = _graph(blockers=[
            {"code": "b1", "category": "SCHEMA_MISMATCH"},
            {"code": "b2", "category": "OVERBROAD"},
            {"code": "b3", "category": "OVERBROAD"}])
        assert g["violated_invariants"] == ["OVERBROAD", "SCHEMA_MISMATCH"]

    def test_blocker_adds_blocks_edge(self):
        g = _graph(blockers=[{"code": "x", "category": "OVERBROAD"}])
        blocks = [e for e in g["edges"] if e["type"] == "BLOCKS"]
        assert blocks and blocks[0]["to"] == "inv:OVERBROAD"


class TestCycleDetection:
    def test_is_acyclic_false_on_cyclic_set(self):
        nodes = [{"id": "a", "type": "X", "label": None},
                 {"id": "b", "type": "X", "label": None}]
        edges = [{"from": "a", "to": "b", "type": "E"},
                 {"from": "b", "to": "a", "type": "E"}]
        assert tq._is_acyclic(nodes, edges) is False

    def test_is_acyclic_true_on_dag(self):
        nodes = [{"id": "a", "type": "X", "label": None},
                 {"id": "b", "type": "X", "label": None}]
        edges = [{"from": "a", "to": "b", "type": "E"}]
        assert tq._is_acyclic(nodes, edges) is True

    def test_build_status_failed_when_not_acyclic(self, monkeypatch):
        # build_assurance_graph is structurally a DAG for valid inputs, so the
        # FAILED branch is exercised by forcing the cycle detector to report a
        # cycle. This tests the documented invariant: not acyclic => FAILED.
        monkeypatch.setattr(tq, "_is_acyclic", lambda nodes, edges: False)
        g = _graph()
        assert g["acyclic"] is False
        assert g["assurance_graph_status"] == "FAILED"

    def test_failed_dominates_mismatch(self, monkeypatch):
        monkeypatch.setattr(tq, "_is_acyclic", lambda nodes, edges: False)
        g = _graph(blockers=[{"code": "x", "category": "OVERBROAD"}],
                   positive_claims=[{"text": "c", "supported_by": []}])
        assert g["assurance_graph_status"] == "FAILED"


class TestGraphHash:
    def test_hash_deterministic(self):
        assert _graph()["assurance_graph_hash"] == _graph()[
            "assurance_graph_hash"]

    def test_hash_self_excluding(self):
        g = _graph()
        assert tq._core_hash(g, "assurance_graph_hash") == g[
            "assurance_graph_hash"]

    def test_hash_changes_with_blocker(self):
        assert _graph()["assurance_graph_hash"] != _graph(
            blockers=[{"code": "x", "category": "OVERBROAD"}])[
            "assurance_graph_hash"]


class TestGraphEndpoint:
    def test_graph_endpoint_returns_graph(self, gate):
        tid, _ = gate.checked_quality_tool()
        r = gate.q(tid, "/graph", actor=OWNER)
        assert r.status_code == 200
        g = r.json()["descriptor_assurance_graph"]
        assert g["assurance_graph_status"] == "MATCHED"
        assert g["acyclic"] is True

    def test_graph_endpoint_requires_prior_check(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        assert gate.q(tid, "/graph", actor=OWNER).status_code == 404
