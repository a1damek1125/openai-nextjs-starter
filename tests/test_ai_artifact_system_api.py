"""CORE-A6 — Artifact System API surface (endpoints exist; create stores
fields + hashes; responses carry honesty labels; nothing executes)."""
from conftest import OWNER, MANAGER


class TestEndpointsExist:
    def test_types(self, gate):
        r = gate.c.get("/ai-artifacts/types", headers=gate.h(OWNER)).json()
        assert "CASE_SUMMARY_DRAFT" in r["artifact_types"]
        assert "SIGNED_LEGAL_DOCUMENT" in r["forbidden_types"]

    def test_dashboard(self, gate):
        gate.make_artifact("RESEARCH_NOTE", "n")
        d = gate.c.get("/ai-artifacts/lifecycle-dashboard",
                       headers=gate.h(OWNER)).json()
        assert "artifacts_by_type" in d and "quarantined_count" in d

    def test_all_read_endpoints(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "n").json()
        aid = a["artifact_id"]
        for ep in ["", "/safe", "/versions", "/manifest", "/lineage",
                   "/provenance", "/claims", "/abom", "/dependencies"]:
            assert gate.art(aid, ep).status_code == 200, ep
        assert gate.art(aid, "/verify", method="POST").status_code == 200
        assert gate.art(aid, "/materialization-check",
                        method="POST").status_code == 200
        assert gate.art(aid, "/decontamination-check",
                        method="POST").status_code == 200

    def test_list_and_task_artifacts(self, gate):
        tid = gate.make_task("case_summary")
        cid = gate.case_id(gate.h(MANAGER))
        gate.make_artifact("CASE_SUMMARY_DRAFT", "s", task_id=tid,
                           subject_type="case", subject_id=cid)
        assert len(gate.c.get("/ai-artifacts",
                              headers=gate.h(OWNER)).json()) >= 1
        ta = gate.c.get(f"/ai-tasks/{tid}/artifacts",
                        headers=gate.h(OWNER)).json()
        assert len(ta["artifacts"]) == 1


class TestCreate:
    def test_stores_core_fields(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        tid = gate.make_task("case_summary")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "summary", task_id=tid,
                               subject_type="case", subject_id=cid).json()
        assert a["tenant_id"]
        assert a["task_id"] == tid
        assert a["artifact_type"] == "CASE_SUMMARY_DRAFT"
        assert a["artifact_trust_tier"]
        assert a["artifact_version"] == 1

    def test_computes_all_hashes(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "n").json()
        for h in ["artifact_content_hash", "artifact_manifest_hash",
                  "artifact_version_hash", "artifact_state_hash",
                  "artifact_provenance_hash", "artifact_claim_graph_hash",
                  "artifact_abom_hash", "artifact_lineage_hash",
                  "artifact_dependency_graph_hash",
                  "artifact_policy_capsule_hash"]:
            assert a[h] and len(a[h]) == 64, h

    def test_honesty_labels_present(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "n").json()
        labels = " ".join(a["honesty_labels"])
        assert "does not execute the action" in labels
        assert "does not send customer messages" in labels
        assert "Server-side artifact truth is authoritative." in labels
        assert "C2PA/Sigstore/DSSE/SLSA/in-toto are not implemented" in labels

    def test_forbidden_type_rejected(self, gate):
        assert gate.make_artifact("SIGNED_LEGAL_DOCUMENT",
                                  "x").status_code == 400
        assert gate.make_artifact("PAYMENT_EXECUTED", "x").status_code == 400

    def test_unknown_type_rejected(self, gate):
        assert gate.make_artifact("TOTALLY_MADE_UP", "x").status_code == 400

    def test_creation_does_not_execute(self, gate):
        # No run events / no side effects; validated indirectly by artifact
        # never leaving a recorded state and materialization can_execute_now
        # always False.
        a = gate.make_artifact("RESEARCH_NOTE", "n").json()
        mc = gate.art(a["artifact_id"], "/materialization-check",
                      method="POST").json()
        assert mc["can_execute_now"] is False
