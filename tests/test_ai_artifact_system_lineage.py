"""CORE-A6 — artifact lineage graph (pure)."""
from finalis.ai_employee import artifacts as A


def _ln(**over):
    kw = dict(artifact_id="a", tenant_id="t", task_id="k", run_id="r",
              approval_request_id="ap", evidence_refs=["ev1"],
              report_refs=["rp1"], dependency_artifact_ids=["d1"],
              supersedes_artifact_id=None, is_tool_input=False,
              is_safe_view_of=None, quarantined_from=None,
              decontaminated_from=None)
    kw.update(over)
    return A.build_lineage(**kw)


class TestLineage:
    def test_lineage_edges(self):
        kinds = {e["lineage_type"] for e in _ln()["lineage_edges"]}
        assert "CREATED_FROM_TASK" in kinds
        assert "CREATED_FROM_RUN" in kinds
        assert "CREATED_FROM_APPROVAL" in kinds
        assert "REFERENCES_EVIDENCE" in kinds
        assert "REFERENCES_REPORT" in kinds
        assert "DERIVED_FROM_ARTIFACT" in kinds

    def test_tool_input_lineage(self):
        kinds = {e["lineage_type"] for e in _ln(
            is_tool_input=True)["lineage_edges"]}
        assert "PROPOSED_TOOL_INPUT" in kinds

    def test_supersedes_lineage(self):
        kinds = {e["lineage_type"] for e in _ln(
            supersedes_artifact_id="old")["lineage_edges"]}
        assert "SUPERSEDES_ARTIFACT" in kinds

    def test_hash_deterministic(self):
        assert _ln()["artifact_lineage_hash"] == _ln()["artifact_lineage_hash"]

    def test_changed_dependency_changes_lineage_hash(self):
        assert _ln(dependency_artifact_ids=["d1"])["artifact_lineage_hash"] \
            != _ln(dependency_artifact_ids=["d2"])["artifact_lineage_hash"]

    def test_dependency_graph_hash_changes(self):
        a = A.build_dependency_graph(artifact_id="a", tenant_id="t",
                                     dependencies=[{"artifact_id": "d1",
                                                    "version_hash": "h1"}])
        b = A.build_dependency_graph(artifact_id="a", tenant_id="t",
                                     dependencies=[{"artifact_id": "d1",
                                                    "version_hash": "h2"}])
        assert a["dependency_graph_hash"] != b["dependency_graph_hash"]

    def test_detect_self_cycle(self):
        assert A.detect_cycle("a", ["a", "b"]) is True
        assert A.detect_cycle("a", ["b", "c"]) is False
