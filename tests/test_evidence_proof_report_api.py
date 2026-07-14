"""EVIDENCE-REPORT-C2 — Canonical Evidence Report Package API.

Deterministic, replayable, auditable proof-report artifacts over the Evidence
Trust Fabric: creation, retrieval, safe view, artifact-integrity verification
(replay), listing, diff; RBAC + tenant isolation; tamper detection; honest
signing status. No external providers, no legal-validity claim.
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from finalis.evidence import reports as R
from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    return a


@pytest.fixture()
def client(app):
    return TestClient(app)


def _login(client, email="owner@demo.finalis"):
    t = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"}).json()
    return {"Authorization": f"Bearer {t['token']}"}


def _evidence(client, h, *, root=True):
    cid = client.get("/cases", headers=h).json()[0]["id"]
    ev = client.post("/evidence/upload", json={
        "case_id": cid, "filename": "p.txt", "mime": "text/plain",
        "content_b64": base64.b64encode(b"450 EUR").decode(),
        "evidence_type": "payment_proof", "text_preview": "450 EUR"},
        headers=h).json()["id"]
    client.post(f"/evidence/{ev}/verify-integrity", headers=h)
    if root:
        client.post("/evidence/merkle-roots/generate", headers=h)
    return ev


def _report(client, h, ev):
    r = client.post(f"/evidence/{ev}/proof-reports", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


class TestEndpointsExistAndShape:
    def test_1_5_endpoints_exist(self, client):
        h = _login(client)
        ev = _evidence(client, h)
        d = _report(client, h, ev)
        rid = d["report_id"]
        assert client.get(f"/evidence/proof-reports/{rid}",
                          headers=h).status_code == 200
        assert client.post(f"/evidence/proof-reports/{rid}/verify",
                           headers=h).status_code == 200
        assert client.get(f"/evidence/{ev}/proof-reports",
                          headers=h).status_code == 200
        # diff endpoint IS implemented.
        d2 = _report(client, h, ev)
        assert client.get(
            f"/evidence/proof-reports/{rid}/diff",
            params={"other_report_id": d2["report_id"]},
            headers=h).status_code == 200

    def test_14_25_metadata_and_subject(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        m = d["report_metadata"]
        for k in ("report_id", "report_type", "report_version",
                  "report_status", "canonicalization_profile",
                  "canonicalization_version",
                  "report_hash_input_schema_version", "report_hash",
                  "report_signature_status", "signature_envelope_type",
                  "redaction_profile", "replay_status"):
            assert k in m, k
        assert d["report_metadata"]["canonicalization_profile"] \
            == "finalis-canonical-json-v1"
        assert "hash_input_manifest" in d
        assert d["subject"]["evidence_id"]
        assert d["subject"]["content_hash"] and d["subject"]["algorithm"]

    def test_20_package_hash_present(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        assert d["package"]["package_hash"]
        assert d["package"]["report_hash"] == d["report_metadata"][
            "report_hash"]

    def test_26_32_proof_snapshot_and_algebra(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        ps = d["proof_snapshot"]
        for k in ("hash_integrity", "merkle_inclusion", "merkle_consistency",
                  "derivative_chain", "contract_history", "timestamp_signal",
                  "provenance_signal", "c2pa_signal", "scitt_signal",
                  "object_lock_signal", "algorithm_pqc_signal"):
            assert k in ps, k
        assert set(d["proof_algebra"].keys()) == \
            {f"D{i}" for i in range(1, 16)}
        assert "root_hash" in d["transparency_log_snapshot"]

    def test_33_36_verdict_warnings_capabilities(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        assert d["verdict"]["final_technical_verdict"]
        assert isinstance(d["conflicts"], list)
        assert isinstance(d["warnings"], list) and d["warnings"]
        assert d["missing_capabilities"] and d["scaffolded_only"]


class TestHonestyLabels:
    def test_37_all_labels_present(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        labels = d["honesty_labels"]
        for required in (
                "Cryptographic verification is not the same as legal "
                "validity.",
                "Report hash is implemented.",
                "Report signing requires configured signing infrastructure.",
                "SCITT receipts are not implemented.",
                "Safe view is not a separate proof.",
                "Production readiness is false.",
                "Server-side Evidence logic remains authoritative."):
            assert required in labels, required

    def test_57_58_no_legal_or_production_overclaim(self, client):
        h = _login(client)
        blob = json.dumps(_report(client, h, _evidence(client, h))).lower()
        for banned in ("legally valid", "legally binding", "production ready",
                       "court-admissible", "non-repudiation guaranteed"):
            assert banned not in blob, banned


class TestSignatureHonesty:
    def test_51_52_signature_not_configured_no_fake_signed(self, client):
        h = _login(client)
        m = _report(client, h, _evidence(client, h))["report_metadata"]
        assert m["report_signature_status"] in ("NOT_CONFIGURED",
                                                 "NOT_IMPLEMENTED")
        assert m["signature_algorithm"] is None
        assert m["signed_payload_hash"] is None
        assert m["report_signature_status"] != "SIGNED"


class TestDeterminismAndHashInputManifest:
    def test_38_same_state_same_hash(self, client):
        h = _login(client)
        ev = _evidence(client, h)
        a = _report(client, h, ev)["report_metadata"]["report_hash"]
        b = _report(client, h, ev)["report_metadata"]["report_hash"]
        assert a == b                          # same proof state
        assert a  # non-empty

    def test_18_40_41_manifest_lists_exclusions(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        man = d["hash_input_manifest"]
        assert "report_hash" in man["excluded_fields"]
        assert "report_signature" in man["excluded_fields"]
        assert "generated_at" in man["excluded_fields"]
        assert "subject" in man["included_fields"]
        assert "proof_algebra" in man["included_fields"]


class TestVerifyReplayTamper:
    def test_48_verify_matched_untampered(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        v = client.post(f"/evidence/proof-reports/{d['report_id']}/verify",
                        headers=h).json()
        assert v["verification_status"] == "MATCHED"
        assert v["verification_kind"] == "artifact_integrity_verification"
        assert v["current_state_comparison"] is False

    def test_49_verify_mismatch_tampered_payload(self, app, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        rid = d["report_id"]
        # Tamper the stored payload's verdict directly in the registry.
        payload = json.loads(
            app.state.db.one("SELECT payload_json p FROM "
                             "evidence_proof_reports WHERE id=?", rid)["p"])
        payload["verdict"]["final_technical_verdict"] = "VERIFIED_FOR_INTEGRITY"
        app.state.db.update("evidence_proof_reports", rid,
                            {"payload_json": json.dumps(payload)})
        v = client.post(f"/evidence/proof-reports/{rid}/verify",
                        headers=h).json()
        assert v["verification_status"] == "MISMATCHED"

    def test_50_verify_mismatch_tampered_package_hash(self, app, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        rid = d["report_id"]
        app.state.db.update("evidence_proof_reports", rid,
                            {"package_hash": "deadbeef" * 8})
        v = client.post(f"/evidence/proof-reports/{rid}/verify",
                        headers=h).json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["package_hash_status"] == "MISMATCHED"


class TestSafeView:
    def test_53_54_55_safe_view_redacts_no_state_change(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        rid = d["report_id"]
        sv = client.get(f"/evidence/proof-reports/{rid}/safe",
                        headers=h).json()
        assert sv["redaction_profile"] == "SAFE_VIEW"
        assert sv["subject"]["content_hash"] == "<omitted in safe view>"
        assert "Safe view is not a separate proof." in \
            sv["redaction_manifest"]["note"]
        # Full report unchanged after safe view (no server truth mutation).
        full = client.get(f"/evidence/proof-reports/{rid}",
                          headers=h).json()
        assert full["subject"]["content_hash"] != "<omitted in safe view>"


class TestRbacAndTenantIsolation:
    def test_8_restricted_role_safe_only(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        rid = d["report_id"]
        vh = _login(client, "viewer@demo.finalis")
        assert client.get(f"/evidence/proof-reports/{rid}",
                          headers=vh).status_code == 403     # full denied
        assert client.get(f"/evidence/proof-reports/{rid}/safe",
                          headers=vh).status_code == 200     # safe allowed
        # A viewer cannot generate a full report either.
        ev2 = _evidence(client, h)
        assert client.post(f"/evidence/{ev2}/proof-reports",
                           headers=vh).status_code == 403

    def test_9_10_11_cross_tenant_denied(self, client):
        h = _login(client)
        d = _report(client, h, _evidence(client, h))
        rid, ev = d["report_id"], d["subject"]["evidence_id"]
        oh = _login(client, "owner@other.finalis")
        assert client.get(f"/evidence/proof-reports/{rid}",
                          headers=oh).status_code == 404
        assert client.post(f"/evidence/proof-reports/{rid}/verify",
                           headers=oh).status_code == 404
        assert client.post(f"/evidence/{ev}/proof-reports",
                           headers=oh).status_code == 404    # evidence hidden

    def test_12_13_unknown_ids_safe_not_found(self, client):
        h = _login(client)
        assert client.post("/evidence/nope/proof-reports",
                           headers=h).status_code == 404
        assert client.get("/evidence/proof-reports/nope",
                          headers=h).status_code == 404


class TestLifecycleAndDiff:
    def test_new_report_does_not_overwrite(self, client):
        h = _login(client)
        ev = _evidence(client, h)
        a = _report(client, h, ev)
        b = _report(client, h, ev)
        assert a["report_id"] != b["report_id"]           # new artifact
        assert b["report_metadata"]["supersedes_report_id"] == a["report_id"]
        lst = client.get(f"/evidence/{ev}/proof-reports", headers=h).json()
        assert len(lst) == 2                              # both auditable

    def test_diff_identical_and_reports_differ(self, client):
        h = _login(client)
        ev = _evidence(client, h)
        a = _report(client, h, ev)["report_id"]
        b = _report(client, h, ev)["report_id"]
        d = client.get(f"/evidence/proof-reports/{a}/diff",
                       params={"other_report_id": b}, headers=h).json()
        assert d["identical_proof_state"] is True         # same proof state
        assert d["changed_fields"] == []


def test_56_no_external_provider_note_and_verify_shape(client_fixture=None):
    # Consolidated: response carries no external call surface; verify is
    # about the stored artifact, not current evidence truth.
    app = create_app(":memory:")
    seed(app.state.db)
    c = TestClient(app)
    h = _login(c)
    d = _report(c, h, _evidence(c, h))
    v = c.post(f"/evidence/proof-reports/{d['report_id']}/verify",
               headers=h).json()
    assert v["current_state_comparison"] is False
    assert v["signature_status"] == "NOT_CONFIGURED"
