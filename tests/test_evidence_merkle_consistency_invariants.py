"""EVIDENCE-MERKLE-C1 invariants — the Finalis Evidence Transparency Log
never claims append-only consistency unless the server verifies it, and a
consistency proof never implies timestamp / notarization / object-lock /
SCITT / legal validity.

Math-layer invariants are proven directly against transparency.consistency_*;
the honesty invariants are proven against the served workbench page.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.evidence import transparency as mrk
from finalis.portal.app import create_app
from finalis.portal.seed import seed


def _L(n):
    return [f"leaf{i:03d}" for i in range(n)]


def _report(old_leaves, new_leaves, *, old_root=None, new_root=None,
            algorithm="sha256"):
    return mrk.consistency_report(
        old_leaves=old_leaves,
        old_root=old_root if old_root is not None
        else mrk.merkle_root(old_leaves),
        old_size=len(old_leaves), new_leaves=new_leaves,
        new_root=new_root if new_root is not None
        else mrk.merkle_root(new_leaves), new_size=len(new_leaves),
        algorithm=algorithm)


class TestConsistencyMathInvariants:
    def test_1_verified_only_when_proof_reconstructs(self):
        # 1. Consistency is server-verified only: VERIFIED requires the
        #    compact proof to reconstruct both canonical heads.
        leaves = _L(9)
        for m in range(1, 9):
            proof = mrk.consistency_proof(m, leaves)
            assert mrk.verify_consistency(
                m, 9, mrk.mth(leaves[:m]), mrk.mth(leaves), proof)
            assert not mrk.verify_consistency(
                m, 9, mrk.mth(leaves[:m]), "tampered-new-head", proof)

    def test_2_missing_proof_cannot_verify(self):
        r = mrk.consistency_report(
            old_leaves=[], old_root="x", old_size=3,
            new_leaves=_L(5), new_root=mrk.merkle_root(_L(5)), new_size=5)
        assert r.status == "PROOF_MISSING"
        assert r.append_only_verified is False

    def test_3_previous_must_be_prefix(self):
        r = _report(_L(3), _L(8))
        assert r.status == "VERIFIED" and r.append_only_verified
        # A non-prefix previous list never verifies.
        r2 = _report(["z", "y"], _L(8))
        assert r2.status == "NOT_VERIFIED"

    def test_4_reorder_invalidates(self):
        base = _L(4)
        r = _report([base[1], base[0]], [base[1], base[0], base[2], base[3]])
        assert r.append_only_verified is True   # this IS a valid prefix
        # but reversing only the previous vs the current order breaks it:
        r2 = _report([base[0], base[1]], [base[1], base[0], base[2]])
        assert r2.status == "NOT_VERIFIED"

    def test_5_replace_invalidates(self):
        base = _L(4)
        r = _report([base[0], base[1]], [base[0], "REPLACED", base[2]])
        assert r.status == "NOT_VERIFIED"

    def test_6_delete_truncate_not_append_only(self):
        # previous larger than current can never be append-only.
        r = _report(_L(6), _L(3))
        assert r.status == "INVALID_RANGE"
        assert r.append_only_verified is False

    def test_8_unsupported_algorithm_cannot_verify(self):
        for alg in ("md5", "sha1", "crc32", "unknown"):
            r = _report(_L(2), _L(4), algorithm=alg)
            assert r.status == "UNSUPPORTED_ALGORITHM"
            assert r.append_only_verified is False

    def test_determinism_same_inputs_same_proof(self):
        assert mrk.consistency_proof(4, _L(11)) \
            == mrk.consistency_proof(4, _L(11))

    def test_tamper_stored_root_fails(self):
        r = _report(_L(3), _L(7), new_root="deadbeef")
        assert r.status == "NOT_VERIFIED"


class TestTenantAndRbacInvariants:
    """7. Cross-tenant comparison denied; RBAC enforced server-side."""

    @pytest.fixture()
    def client(self):
        app = create_app(":memory:")
        seed(app.state.db)
        return TestClient(app), app

    def _mk_root(self, app, tenant, leaves):
        import json
        import uuid
        rid = str(uuid.uuid4())
        app.state.db.insert("evidence_merkle_roots", {
            "id": rid, "tenant_id": tenant, "root": mrk.merkle_root(leaves),
            "size": len(leaves), "leaves_json": json.dumps(leaves),
            "created_at": "2026-07-08T00:00:00"})
        return rid

    def _login(self, client, email="owner@demo.finalis"):
        t = client.post("/auth/login", json={"email": email,
                                             "password": "demo1234"}
                        ).json()["token"]
        return {"Authorization": f"Bearer {t}"}

    def test_7_cross_tenant_comparison_denied(self, client):
        c, app = client
        h = self._login(c)
        mine = self._mk_root(app, "demo-hvac", ["a", "b"])
        theirs = self._mk_root(app, "other-tenant", ["a", "b", "c"])
        d = c.get(f"/evidence/merkle-roots/{theirs}/consistency",
                  params={"previous_root_id": mine}, headers=h).json()
        # theirs is invisible to this tenant → never compared.
        assert d["status"] == "ROOT_NOT_FOUND"
        assert d["append_only_verified"] is False

    def test_rbac_denied_without_audit_view(self, client):
        c, app = client
        r1 = self._mk_root(app, "demo-hvac", ["a"])
        r2 = self._mk_root(app, "demo-hvac", ["a", "b"])
        h = self._login(c, "viewer@demo.finalis")
        assert c.get(f"/evidence/merkle-roots/{r2}/consistency",
                     params={"previous_root_id": r1},
                     headers=h).status_code == 403


class TestHonestyInvariants:
    """9-14. A consistency proof never implies more than append-only tree
    evolution; the score never overrides a consistency failure."""

    @pytest.fixture()
    def norm(self):
        app = create_app(":memory:")
        seed(app.state.db)
        return " ".join(TestClient(app).get("/portal").text.split())

    def test_9_score_cannot_override_consistency_failure(self, norm):
        # D3 FAIL is a hard-fail in the proof algebra (readiness forced 0).
        assert "dims.D3 === 'FAIL'" in norm
        assert "Positive signals cannot average away a critical proof " \
            "failure." in norm

    def test_10_does_not_imply_legal_validity(self, norm):
        assert "Merkle consistency proves append-only tree evolution only; " \
            "it does not prove legal validity." in norm
        assert "Cryptographic integrity is not the same as legal validity." \
            in norm

    def test_11_12_13_does_not_imply_timestamp_notary_objectlock(self, norm):
        assert "Timestamping proves existence at a time; it does not prove " \
            "business truth." in norm
        assert "External notarization is not connected." in norm
        assert "Blockchain anchoring is not implemented." in norm

    def test_14_does_not_imply_scitt_receipt(self, norm):
        assert "SCITT receipts are not implemented." in norm
        assert "SCITT receipt presence does not equal business truth." in norm
