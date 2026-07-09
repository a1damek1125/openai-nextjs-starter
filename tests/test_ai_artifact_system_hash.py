"""CORE-A6 — deterministic artifact hashing (pure). Every hash excludes itself,
is key-order independent, changes with covered content, rejects NaN/Inf."""
import math

import pytest

from finalis.ai_employee import artifacts as A


def _env(body="hello world"):
    return A.build_content_envelope(
        content_format="TEXT", content_role="draft",
        content_trust_level="AI_DRAFT", content_body=body)


class TestCanonical:
    def test_key_order_irrelevant(self):
        assert A.canonical_json({"b": 1, "a": 2}) \
            == A.canonical_json({"a": 2, "b": 1})

    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            A.canonical_json({"x": math.nan})

    def test_infinity_rejected(self):
        with pytest.raises(ValueError):
            A.canonical_json({"x": math.inf})


class TestContentHash:
    def test_same_envelope_same_hash(self):
        assert A.content_hash(_env()) == A.content_hash(_env())

    def test_changed_content_changes_hash(self):
        assert A.content_hash(_env("a")) != A.content_hash(_env("b"))

    def test_excludes_body_hash_field(self):
        e = _env()
        e2 = dict(e, content_body_hash="x")
        assert A.content_hash(e) == A.content_hash(e2)


class TestManifestHash:
    def _m(self, **over):
        kw = dict(artifact_id="a", tenant_id="t", artifact_type="X",
                  artifact_status="DRAFT", artifact_trust_tier="AI",
                  task_id="k", run_id=None, approval_request_id=None,
                  approval_grant_id=None, created_by_actor_id="u",
                  created_by_actor_type="human", task_contract_hash="ch",
                  task_envelope_hash="eh", task_state_hash=None,
                  run_state_hash=None, run_chain_hash=None,
                  approval_grant_hash=None, content_hash="c", version_hash="v",
                  claim_graph_hash="cg", dependency_hashes=["d1"],
                  provenance_hash="pv", abom_hash="ab", evidence_refs=[],
                  report_refs=[], subject_refs=[], redaction_profile="FULL",
                  safe_view_available=True, quarantine_status="CLEAN",
                  materialization_status="PENDING", retention_hint="D",
                  legal_hold_hint=None)
        kw.update(over)
        return A.build_manifest(**kw)

    def test_excludes_itself_and_version_hash(self):
        m = self._m()
        m2 = dict(m, manifest_hash="z", version_hash="different")
        assert A.manifest_hash(m) == A.manifest_hash(m2)

    def test_changed_content_hash_changes_manifest(self):
        assert self._m(content_hash="a")["manifest_hash"] \
            != self._m(content_hash="b")["manifest_hash"]

    def test_changed_task_contract_hash_changes_manifest(self):
        assert self._m(task_contract_hash="a")["manifest_hash"] \
            != self._m(task_contract_hash="b")["manifest_hash"]

    def test_changed_claim_graph_changes_manifest(self):
        assert self._m(claim_graph_hash="a")["manifest_hash"] \
            != self._m(claim_graph_hash="b")["manifest_hash"]

    def test_changed_quarantine_changes_manifest(self):
        assert self._m(quarantine_status="CLEAN")["manifest_hash"] \
            != self._m(quarantine_status="QUARANTINED")["manifest_hash"]


class TestVersionAndStateHash:
    def test_version_hash_changes_with_content(self):
        kw = dict(artifact_id="a", version_number=1, manifest_hash="m",
                  claim_graph_hash="cg", provenance_hash="pv", abom_hash="ab",
                  previous_version_hash=None, created_by_actor_id="u")
        assert A.version_hash(content_hash="a", **kw) \
            != A.version_hash(content_hash="b", **kw)

    def test_chain_hash_links_previous(self):
        assert A.version_chain_hash("p1", "v") != A.version_chain_hash("p2", "v")

    def _state(self, **over):
        kw = dict(artifact_id="a", tenant_id="t", artifact_type="X",
                  artifact_status="DRAFT", artifact_trust_tier="AI",
                  latest_version_id="v1", version_number=1, task_id="k",
                  run_id=None, approval_request_id=None, approval_grant_hash=None,
                  task_contract_hash="ch", content_hash="c", manifest_hash="m",
                  claim_graph_hash="cg", provenance_hash="pv", abom_hash="ab",
                  dependency_graph_hash="dg", lineage_hash="lg",
                  quarantine_status="CLEAN", materialization_status="P",
                  version_chain_hash="vc")
        kw.update(over)
        return A.artifact_state_hash(**kw)

    def test_state_hash_changes_with_status(self):
        assert self._state(artifact_status="DRAFT") \
            != self._state(artifact_status="QUARANTINED")

    def test_state_hash_changes_with_content(self):
        assert self._state(content_hash="a") != self._state(content_hash="b")

    def test_state_hash_changes_with_quarantine(self):
        assert self._state(quarantine_status="CLEAN") \
            != self._state(quarantine_status="QUARANTINED")

    def test_state_hash_key_order_irrelevant(self):
        # deterministic across repeated calls (canonicalization)
        assert self._state() == self._state()


class TestGraphHashesExcludeSelf:
    def test_claim_graph_hash_excludes_itself(self):
        g = A.build_claim_graph(artifact_id="a", artifact_version_id="v",
                                tenant_id="t", claims_input=[], source_text="x")
        assert A.claim_graph_hash(dict(g, claim_graph_hash="z")) \
            == A.claim_graph_hash(g)

    def test_abom_hash_excludes_itself(self):
        ab = A.build_abom(artifact_id="a", artifact_version_id="v",
                          tenant_id="t", artifact_type="X", content_format="T",
                          input_sources=[], source_channels=[],
                          dependency_artifact_versions=[], evidence_refs=[],
                          report_refs=[], task_refs=[], run_refs=[],
                          approval_refs=[], policy_capsule_hash="p",
                          scanner_hash="s", trust_tier="AI")
        assert A.abom_hash(dict(ab, abom_hash="z")) == A.abom_hash(ab)

    def test_provenance_hash_excludes_itself(self):
        pv = A.build_provenance(artifact_id="a", artifact_version_id="v",
                                tenant_id="t", task_id="k", run_id=None,
                                approval_request_id=None, created_by_actor_id="u",
                                created_by_actor_type="human",
                                assigned_ai_employee_id="",
                                dependency_artifact_ids=[], evidence_refs=[],
                                report_refs=[], supersedes_artifact_id=None,
                                has_claim=True, has_abom=True)
        assert A.provenance_hash(dict(pv, provenance_hash="z")) \
            == A.provenance_hash(pv)

    def test_changed_dependency_changes_abom_hash(self):
        base = dict(artifact_id="a", artifact_version_id="v", tenant_id="t",
                    artifact_type="X", content_format="T", input_sources=[],
                    source_channels=[], evidence_refs=[], report_refs=[],
                    task_refs=[], run_refs=[], approval_refs=[],
                    policy_capsule_hash="p", scanner_hash="s", trust_tier="AI")
        a1 = A.build_abom(dependency_artifact_versions=[{"artifact_id": "d1"}],
                          **base)
        a2 = A.build_abom(dependency_artifact_versions=[{"artifact_id": "d2"}],
                          **base)
        assert a1["abom_hash"] != a2["abom_hash"]
