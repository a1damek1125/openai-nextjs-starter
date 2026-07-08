"""EVIDENCE-REPORT-C2 invariants — deterministic report hashing, tamper
detection, honest signing, and no legal / notarization / production overclaim.
Math-layer invariants run against the pure reports module; honesty invariants
run against the served workbench page.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from finalis.evidence import reports as R
from finalis.portal.app import create_app
from finalis.portal.seed import seed


def _sig(**over):
    ev = {"id": "ev1", "case_id": "c1", "evidence_type": "payment_proof",
          "source": "upload", "created_at": "2026-07-08T00:00:00",
          "content_hash": "abc", "algorithm": "sha256",
          "integrity_valid": True, "state": "ADMISSIBLE",
          "human_verified": True}
    ev.update(over.pop("evidence", {}))
    s = {"evidence": ev,
         "inclusion": {"status": "VERIFIED", "root_hash": "RH",
                       "tree_size": 3, "leaf_index": 0, "leaf_hash": "LH"},
         "consistency": {"status": "VERIFIED", "append_only_verified": True,
                         "proof_nodes": ["n1"]},
         "derivatives": [], "contracts": []}
    s.update(over)
    return s


def _payload(**over):
    return R.build_report_payload(
        report_id="RID", tenant_id="t", generated_by="u",
        generated_at="2026-07-08T10:00:00", signals=_sig(**over))


def _rh(p):
    return p["report_metadata"]["report_hash"]


class TestHashInvariants:
    def test_1_deterministic(self):
        assert _rh(_payload()) == _rh(_payload())

    def test_2_excludes_itself(self):
        p = _payload()
        h = _rh(p)
        tampered = copy.deepcopy(p)
        tampered["report_metadata"]["report_hash"] = "ZZZ"
        hashable = {k: tampered[k] for k in tampered
                    if k not in ("report_metadata", "hash_input_manifest")}
        assert R.compute_report_hash(hashable) == h

    def test_3_excludes_signature(self):
        p = _payload()
        h = _rh(p)
        t = copy.deepcopy(p)
        t["report_metadata"]["report_signature_status"] = "SIGNED"
        t["report_metadata"]["signature_algorithm"] = "ed25519"
        hashable = {k: t[k] for k in t
                    if k not in ("report_metadata", "hash_input_manifest")}
        assert R.compute_report_hash(hashable) == h

    def test_key_order_independent(self):
        import json
        p = _payload()
        reordered = json.loads(json.dumps(p))
        hashable = {k: reordered[k] for k in reordered
                    if k not in ("report_metadata", "hash_input_manifest")}
        assert R.compute_report_hash(hashable) == _rh(p)

    def test_4_changes_when_proof_critical_changes(self):
        base = _rh(_payload())
        assert _rh(_payload(evidence={"content_hash": "different"})) != base
        assert _rh(_payload(evidence={"integrity_valid": False})) != base
        assert _rh(_payload(consistency={"status": "NOT_VERIFIED",
                                         "append_only_verified": False})) \
            != base

    def test_generated_at_excluded_from_hash(self):
        a = R.build_report_payload(report_id="A", tenant_id="t",
                                   generated_by="u", generated_at="T1",
                                   signals=_sig())
        b = R.build_report_payload(report_id="B", tenant_id="t",
                                   generated_by="u", generated_at="T2",
                                   signals=_sig())
        assert _rh(a) == _rh(b)          # id + time excluded


class TestTamperAndVerify:
    def test_5_detects_tampered_payload(self):
        p = _payload()
        pkg = R.build_package(p)
        t = copy.deepcopy(p)
        t["verdict"]["final_technical_verdict"] = "NOT_VERIFIED"
        v = R.verify_report_artifact(t, _rh(p), pkg["package_hash"])
        assert v["verification_status"] == "MISMATCHED"

    def test_6_detects_tampered_package(self):
        p = _payload()
        v = R.verify_report_artifact(p, _rh(p), "bad-package-hash")
        assert v["verification_status"] == "MISMATCHED"
        assert v["package_hash_status"] == "MISMATCHED"

    def test_untampered_matches(self):
        p = _payload()
        pkg = R.build_package(p)
        v = R.verify_report_artifact(p, _rh(p), pkg["package_hash"])
        assert v["verification_status"] == "MATCHED"


class TestSigningAndVerdictInvariants:
    def test_7_no_signing_claim_without_infrastructure(self):
        m = _payload()["report_metadata"]
        assert m["report_signature_status"] == "NOT_CONFIGURED"
        assert m["signature_algorithm"] is None

    def test_11_missing_consistency_prevents_append_only_claim(self):
        p = _payload(consistency={"status": "NOT_EXPOSED"})
        assert p["proof_algebra"]["D3"] == "NOT_EXPOSED"
        # no append-only claim in the transparency snapshot
        assert p["transparency_log_snapshot"]["append_only_verified"] is False

    def test_12_19_hard_fail_prevents_verified_and_score_no_override(self):
        # A hash-integrity FAIL is a hard fail: verdict must not be
        # VERIFIED_FOR_INTEGRITY regardless of otherwise-positive signals.
        p = _payload(evidence={"integrity_valid": False})
        assert p["verdict"]["final_technical_verdict"] != \
            "VERIFIED_FOR_INTEGRITY"
        assert p["verdict"]["automation_allowed"] is False
        assert p["verdict"]["hard_fail_reasons"]

    def test_unsupported_algorithm_hard_fail(self):
        p = _payload(evidence={"algorithm": "md5"})
        assert p["proof_algebra"]["D9"] == "UNSUPPORTED_CRITICAL_ALGORITHM"
        assert p["verdict"]["final_technical_verdict"] != \
            "VERIFIED_FOR_INTEGRITY"


class TestSafeViewInvariants:
    def test_16_safe_view_omits_restricted_fields(self):
        sv = R.safe_view(_payload())
        assert sv["subject"]["content_hash"] == "<omitted in safe view>"
        assert sv["subject"]["canonical_hash"] == "<omitted in safe view>"
        # leaf_hash lives in the transparency snapshot and is redacted there.
        assert sv["transparency_log_snapshot"]["leaf_hash"] == \
            "<omitted in safe view>"

    def test_17_safe_view_not_a_separate_proof(self):
        sv = R.safe_view(_payload())
        assert "Safe view is not a separate proof." in \
            sv["redaction_manifest"]["note"]


class TestHonestyLabelsInReport:
    def test_8_9_10_no_implied_legal_notary_blockchain(self):
        labels = _payload()["honesty_labels"]
        assert "Cryptographic verification is not the same as legal " \
            "validity." in labels
        assert "External notarization is not connected." in labels
        assert "Blockchain anchoring is not implemented." in labels


class TestWorkbenchHonesty:
    @pytest.fixture()
    def norm(self):
        app = create_app(":memory:")
        seed(app.state.db)
        return " ".join(TestClient(app).get("/portal").text.split())

    def test_20_ui_labels_cannot_unlock_actions(self, norm):
        assert "UI report display is not legal advice." in norm
        assert "Server-side Evidence logic remains authoritative." in norm
        assert "a display score cannot unlock actions" in norm
