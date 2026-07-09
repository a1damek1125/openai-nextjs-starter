"""CORE-A6 — artifact versioning. New versions never overwrite old ones; the
chain links; old versions stay readable and verifiable; diff reports changes."""
from conftest import OWNER, MANAGER


class TestVersions:
    def test_creation_makes_version_1(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        assert a["artifact_version"] == 1
        vs = gate.art(a["artifact_id"], "/versions").json()["versions"]
        assert len(vs) == 1 and vs[0]["version_number"] == 1

    def test_new_version_increments(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        r = gate.art(a["artifact_id"], "/versions", actor=MANAGER,
                     method="POST", content_body="v2").json()
        assert r["version_number"] == 2
        assert gate.art(a["artifact_id"]).json()["artifact_version"] == 2

    def test_previous_version_hash_links(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        v2 = gate.art(a["artifact_id"], "/versions", actor=MANAGER,
                      method="POST", content_body="v2").json()["artifact_version"]
        vs = gate.art(a["artifact_id"], "/versions").json()["versions"]
        assert v2["previous_version_hash"] == vs[0]["version_hash"]

    def test_version_chain_changes(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        vs1 = gate.art(a["artifact_id"], "/versions").json()["versions"]
        gate.art(a["artifact_id"], "/versions", actor=MANAGER, method="POST",
                 content_body="v2")
        vs2 = gate.art(a["artifact_id"], "/versions").json()["versions"]
        assert vs2[1]["version_chain_hash"] != vs1[0]["version_chain_hash"]

    def test_old_versions_remain_readable(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        gate.art(a["artifact_id"], "/versions", actor=MANAGER, method="POST",
                 content_body="v2")
        vs = gate.art(a["artifact_id"], "/versions").json()["versions"]
        got = gate.art(a["artifact_id"],
                       f"/versions/{vs[0]['artifact_version_id']}").json()
        assert got["content_envelope"]["content_body"] == "v1"

    def test_old_versions_remain_verifiable(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        gate.art(a["artifact_id"], "/versions", actor=MANAGER, method="POST",
                 content_body="v2")
        v = gate.art(a["artifact_id"], "/verify", method="POST").json()
        assert v["verification_status"] == "MATCHED"
        assert v["versions_checked"] == 2

    def test_diff_reports_changes(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        gate.art(a["artifact_id"], "/versions", actor=MANAGER, method="POST",
                 content_body="v2 different")
        vs = gate.art(a["artifact_id"], "/versions").json()["versions"]
        d = gate.art(a["artifact_id"], "/diff", method="POST",
                     from_version_id=vs[0]["artifact_version_id"],
                     to_version_id=vs[1]["artifact_version_id"]).json()
        assert d["content_changed"] is True
        assert "content_hash" in d["changed_fields"]

    def test_terminal_artifact_cannot_be_versioned(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        gate.art(a["artifact_id"], "/archive", actor=MANAGER, method="POST")
        r = gate.art(a["artifact_id"], "/versions", actor=MANAGER,
                     method="POST", content_body="v2")
        assert r.status_code == 409

    def test_superseded_artifact_cannot_be_versioned(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "v1").json()
        gate.art(a["artifact_id"], "/supersede", actor=MANAGER, method="POST")
        r = gate.art(a["artifact_id"], "/versions", actor=MANAGER,
                     method="POST", content_body="v2")
        assert r.status_code == 409
