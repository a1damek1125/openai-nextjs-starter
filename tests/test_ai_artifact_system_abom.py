"""CORE-A6 — Artifact Bill of Materials (pure + API). ABOM is local Finalis
composition metadata; it is NOT an SBOM and claims no SPDX/CycloneDX/SLSA."""
from finalis.ai_employee import artifacts as A

from conftest import OWNER, MANAGER


class TestAbomApi:
    def test_abom_endpoint(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        r = gate.art(a["artifact_id"], "/abom").json()
        assert r["abom"]["abom_version"] == A.ABOM_VERSION
        assert r["abom_hash"]

    def test_abom_includes_composition(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        a = gate.make_artifact("RESEARCH_NOTE", "note", subject_type="case",
                               subject_id=cid, evidence_refs=["ev1"],
                               report_refs=["rp1"]).json()
        abom = gate.art(a["artifact_id"], "/abom").json()["abom"]
        assert abom["evidence_refs"] == ["ev1"]
        assert abom["report_refs"] == ["rp1"]
        assert "trust_tier" in abom and "policy_capsule_hash" in abom
        assert "scanner_hash" in abom

    def test_abom_not_sbom(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        abom = gate.art(a["artifact_id"], "/abom").json()["abom"]
        assert "not_an_sbom" in abom
        assert abom["external_provider_used"] is False
        assert abom["llm_provider_used"] is False
        assert abom["tool_broker_used"] is False

    def test_abom_hash_deterministic(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        r1 = gate.art(a["artifact_id"], "/abom").json()
        r2 = gate.art(a["artifact_id"], "/abom").json()
        assert r1["abom_hash"] == r2["abom_hash"]

    def test_dependency_changes_abom_hash(self, gate):
        dep = gate.make_artifact("RESEARCH_NOTE", "dep").json()
        plain = gate.make_artifact("ACTION_PLAN_DRAFT", "plan").json()
        withdep = gate.make_artifact(
            "ACTION_PLAN_DRAFT", "plan",
            dependency_artifact_ids=[dep["artifact_id"]]).json()
        h1 = gate.art(plain["artifact_id"], "/abom").json()["abom_hash"]
        h2 = gate.art(withdep["artifact_id"], "/abom").json()["abom_hash"]
        assert h1 != h2
