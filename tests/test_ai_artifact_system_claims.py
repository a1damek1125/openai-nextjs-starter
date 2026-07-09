"""CORE-A6 — artifact claim graph (pure + API). Claims are supported only when
they carry a reference; unsupported claims cannot support completion or
authorize materialization; the claim graph never asserts legal truth."""
from finalis.ai_employee import artifacts as A

from conftest import OWNER, MANAGER


def _cg(claims):
    return A.build_claim_graph(artifact_id="a", artifact_version_id="v",
                               tenant_id="t", claims_input=claims,
                               source_text="src")


class TestClaimPure:
    def test_supported_needs_reference(self):
        g = _cg([{"claim_predicate": "summarizes", "claim_subject_type": "case",
                  "claim_subject_id": "c1", "claim_value": "ok",
                  "supporting_evidence_refs": ["ev1"]}])
        assert g["claims"][0]["claim_support_status"] == "SUPPORTED_BY_REFERENCE"

    def test_unsupported_without_reference(self):
        g = _cg([{"claim_predicate": "recommends", "claim_subject_type": "case",
                  "claim_subject_id": "c1", "claim_value": "do x"}])
        assert g["claims"][0]["claim_support_status"] == "UNSUPPORTED"
        assert g["unsupported_count"] == 1

    def test_needs_review_bad_predicate(self):
        g = _cg([{"claim_predicate": "declares_legal_truth",
                  "claim_subject_id": "c1", "claim_value": "x"}])
        assert g["claims"][0]["claim_support_status"] == "NEEDS_REVIEW"

    def test_needs_review_no_subject(self):
        g = _cg([{"claim_predicate": "summarizes", "claim_value": "x",
                  "supporting_evidence_refs": ["ev1"]}])
        assert g["claims"][0]["claim_support_status"] == "NEEDS_REVIEW"

    def test_no_claims_is_not_implemented(self):
        g = _cg([])
        assert g["claims"][0]["claim_support_status"] == "NOT_IMPLEMENTED"
        assert g["claims"][0]["claim_type"] \
            == "CLAIM_EXTRACTION_NOT_IMPLEMENTED"

    def test_hash_deterministic(self):
        c = [{"claim_predicate": "summarizes", "claim_subject_id": "c1",
              "claim_value": "x", "supporting_report_refs": ["r1"]}]
        assert _cg(c)["claim_graph_hash"] == _cg(c)["claim_graph_hash"]

    def test_changed_claim_changes_hash(self):
        a = _cg([{"claim_predicate": "summarizes", "claim_subject_id": "c1",
                  "claim_value": "x"}])
        b = _cg([{"claim_predicate": "summarizes", "claim_subject_id": "c1",
                  "claim_value": "y"}])
        assert a["claim_graph_hash"] != b["claim_graph_hash"]

    def test_confidence_is_structural_only(self):
        g = _cg([{"claim_predicate": "asserts", "claim_subject_id": "c1",
                  "claim_value": "x", "supporting_artifact_refs": ["a2"]}])
        assert g["claims"][0]["claim_confidence"] == "LOCAL_STRUCTURAL_ONLY"

    def test_claims_all_supported_predicate(self):
        supported = _cg([{"claim_predicate": "summarizes",
                          "claim_subject_id": "c1", "claim_value": "x",
                          "supporting_evidence_refs": ["e"]}])
        assert A.claims_all_supported(supported) is True
        unsupported = _cg([{"claim_predicate": "summarizes",
                            "claim_subject_id": "c1", "claim_value": "x"}])
        assert A.claims_all_supported(unsupported) is False
        assert A.claims_all_supported(_cg([])) is False


class TestClaimApi:
    def test_claims_endpoint(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        a = gate.make_artifact(
            "CASE_SUMMARY_DRAFT", "summary", subject_type="case",
            subject_id=cid, claims=[{"claim_predicate": "summarizes",
                                     "claim_subject_type": "case",
                                     "claim_subject_id": cid,
                                     "claim_value": "ok",
                                     "supporting_evidence_refs": ["ev1"]}]
        ).json()
        r = gate.art(a["artifact_id"], "/claims").json()
        assert r["claim_graph"]["claims"][0]["claim_support_status"] \
            == "SUPPORTED_BY_REFERENCE"
        assert r["claim_graph_hash"]

    def test_unsupported_claim_counts(self, gate):
        cid = gate.case_id(gate.h(MANAGER))
        a = gate.make_artifact(
            "CASE_SUMMARY_DRAFT", "summary", subject_type="case",
            subject_id=cid, claims=[{"claim_predicate": "recommends",
                                     "claim_subject_id": cid,
                                     "claim_value": "do"}]).json()
        assert a["unsupported_claim_count"] >= 1
