"""CORE-A6 — local provenance graph (pure + API). Tenant-scoped; deterministic;
NOT C2PA/SLSA/in-toto production attestation."""
from finalis.ai_employee import artifacts as A

from conftest import OWNER, MANAGER, OTHER_OWNER


class TestProvenancePure:
    def _pv(self, **over):
        kw = dict(artifact_id="a", artifact_version_id="v", tenant_id="t",
                  task_id="k", run_id="r", approval_request_id=None,
                  created_by_actor_id="u", created_by_actor_type="human",
                  assigned_ai_employee_id="e", dependency_artifact_ids=[],
                  evidence_refs=[], report_refs=[], supersedes_artifact_id=None,
                  has_claim=True, has_abom=True)
        kw.update(over)
        return A.build_provenance(**kw)

    def test_includes_artifact_entity(self):
        nodes = {n["node"] for n in self._pv()["nodes"]}
        assert "PROV_ENTITY_ARTIFACT" in nodes
        assert "PROV_ENTITY_ARTIFACT_VERSION" in nodes

    def test_includes_creation_activity(self):
        nodes = {n["node"] for n in self._pv()["nodes"]}
        assert "PROV_ACTIVITY_ARTIFACT_CREATE" in nodes

    def test_includes_human_agent(self):
        nodes = {n["node"] for n in self._pv(
            created_by_actor_type="human")["nodes"]}
        assert "PROV_AGENT_HUMAN_USER" in nodes

    def test_ai_employee_agent(self):
        nodes = {n["node"] for n in self._pv(
            created_by_actor_type="ai_employee")["nodes"]}
        assert "PROV_AGENT_AI_EMPLOYEE" in nodes

    def test_generated_by_edge(self):
        edges = {e["edge"] for e in self._pv()["edges"]}
        assert "WAS_GENERATED_BY" in edges
        assert "WAS_ATTRIBUTED_TO" in edges

    def test_derived_from_dependency(self):
        edges = self._pv(dependency_artifact_ids=["d1"])["edges"]
        assert any(e["edge"] == "WAS_DERIVED_FROM" for e in edges)

    def test_hash_deterministic(self):
        assert self._pv()["provenance_hash"] == self._pv()["provenance_hash"]

    def test_hash_changes_with_task(self):
        assert self._pv(task_id="k1")["provenance_hash"] \
            != self._pv(task_id="k2")["provenance_hash"]

    def test_not_production_attestation(self):
        assert "not C2PA/SLSA/in-toto" in self._pv()["note"]


class TestProvenanceApi:
    def test_provenance_endpoint(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        r = gate.art(a["artifact_id"], "/provenance").json()
        assert any(n["node"] == "PROV_ENTITY_ARTIFACT"
                   for n in r["provenance"]["nodes"])
        assert r["provenance_hash"]

    def test_cross_tenant_provenance_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        assert gate.art(a["artifact_id"], "/provenance",
                        actor=OTHER_OWNER).status_code == 404

    def test_lineage_endpoint_safe(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "s", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        r = gate.art(a["artifact_id"], "/lineage").json()
        kinds = {e["lineage_type"] for e in r["lineage"]["lineage_edges"]}
        assert "CREATED_FROM_TASK" in kinds
