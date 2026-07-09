"""CORE-A6 — artifact dependencies & lineage. Same-tenant only; missing deps
rejected; self-cycle rejected; dependency drift detected in verify."""
import json

from conftest import OWNER, MANAGER, OTHER_OWNER


class TestDependencies:
    def test_same_tenant_dependency(self, gate):
        dep = gate.make_artifact("RESEARCH_NOTE", "dep").json()
        child = gate.make_artifact(
            "ACTION_PLAN_DRAFT", "child",
            dependency_artifact_ids=[dep["artifact_id"]])
        assert child.status_code == 200
        dg = gate.art(child.json()["artifact_id"], "/dependencies").json()
        deps = dg["dependency_graph"]["dependencies"]
        assert deps[0]["artifact_id"] == dep["artifact_id"]
        assert deps[0]["version_hash"]

    def test_missing_dependency_rejected(self, gate):
        r = gate.make_artifact("ACTION_PLAN_DRAFT", "x",
                               dependency_artifact_ids=["does-not-exist"])
        assert r.status_code == 400

    def test_cross_tenant_dependency_rejected(self, gate):
        dep = gate.make_artifact("RESEARCH_NOTE", "dep").json()
        # other tenant cannot depend on this-tenant artifact
        r = gate.c.post("/ai-artifacts", json={
            "artifact_type": "ACTION_PLAN_DRAFT", "content_body": "x",
            "dependency_artifact_ids": [dep["artifact_id"]]},
            headers=gate.h(OTHER_OWNER))
        assert r.status_code == 400

    def test_self_cycle_rejected(self, gate):
        # The endpoint self-cycle guard (_art.detect_cycle) fires when an
        # artifact's dependency list contains itself. A fresh create can't
        # name its own (unknown) id, so drive the guard through the version
        # path: tamper the head to self-depend, then a new version must 400.
        a = gate.make_artifact("ACTION_PLAN_DRAFT", "a").json()
        aid = a["artifact_id"]
        import json
        row = gate.db.one("SELECT payload_json FROM ai_artifacts WHERE id=?",
                          aid)
        p = json.loads(row["payload_json"])
        p["dependency_artifact_ids"] = [aid]
        gate.db.conn.execute("UPDATE ai_artifacts SET payload_json=? WHERE "
                             "id=?", (json.dumps(p), aid))
        gate.db.conn.commit()
        r = gate.art(aid, "/versions", actor=MANAGER, method="POST",
                     content_body="v2")
        assert r.status_code == 400
        assert "itself" in r.json()["detail"]

    def test_dependency_drift_detected_in_verify(self, gate):
        dep = gate.make_artifact("RESEARCH_NOTE", "dep").json()
        child = gate.make_artifact(
            "ACTION_PLAN_DRAFT", "child",
            dependency_artifact_ids=[dep["artifact_id"]]).json()
        # advance the dependency with a new version -> child dependency drifts
        gate.art(dep["artifact_id"], "/versions", actor=MANAGER,
                 method="POST", content_body="dep v2")
        v = gate.art(child["artifact_id"], "/verify", method="POST").json()
        assert v["verification_status"] == "MISMATCHED"
        assert any("drift" in r for r in v["tamper_reasons"])

    def test_superseded_lineage_preserved(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "a").json()
        gate.art(a["artifact_id"], "/supersede", actor=MANAGER, method="POST")
        # old versions and lineage still readable
        assert gate.art(a["artifact_id"], "/lineage").status_code == 200
        assert gate.art(a["artifact_id"], "/versions").status_code == 200
