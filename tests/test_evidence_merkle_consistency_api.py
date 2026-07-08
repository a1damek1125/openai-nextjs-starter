"""EVIDENCE-MERKLE-C1 — Finalis Evidence Transparency Log Core.

Server-side Merkle consistency proofs over the existing evidence transparency
ledger. Append-only extension is verified AUTHORITATIVELY by full-leaf
recomputation (the ledger persists every checkpoint's ordered leaves), and a
compact RFC 9162 consistency proof is generated and server-verified before a
VERIFIED verdict. No blockchain, no external notarization, no external
transparency service.

The live ledger is append-only by construction, so reorder/replace/tamper are
exercised against forged/crafted checkpoint rows to prove the verifier rejects
them; genuine append/same-root cases use real checkpoints.
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from finalis.evidence import transparency as mrk
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
    r = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _case(client, h):
    return client.get("/cases", headers=h).json()[0]["id"]


def _upload(client, h, case_id, text):
    r = client.post("/evidence/upload", json={
        "case_id": case_id, "filename": "e.txt", "mime": "text/plain",
        "content_b64": base64.b64encode(text.encode()).decode(),
        "evidence_type": "payment_proof", "text_preview": text}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _gen_root(client, h):
    r = client.post("/evidence/merkle-roots/generate", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["batch_id"]


def _insert_root(app, *, tenant_id="demo-hvac", leaves, root=None, size=None,
                 created_at="2026-07-08T00:00:00"):
    """Directly persist a (possibly forged) checkpoint row for adversarial
    tests."""
    import uuid
    rid = str(uuid.uuid4())
    app.state.db.insert("evidence_merkle_roots", {
        "id": rid, "tenant_id": tenant_id,
        "root": root if root is not None else mrk.merkle_root(leaves),
        "size": size if size is not None else len(leaves),
        "leaves_json": json.dumps(leaves), "created_at": created_at})
    return rid


def _two_real_checkpoints(client, h):
    """A genuine append: root1 then more evidence then root2 (superset)."""
    case_id = _case(client, h)
    _upload(client, h, case_id, "first 100 EUR")
    r1 = _gen_root(client, h)
    _upload(client, h, case_id, "second 200 EUR")
    _upload(client, h, case_id, "third 300 EUR")
    r2 = _gen_root(client, h)
    return r1, r2


def _consistency(client, h, current, previous):
    return client.get(
        f"/evidence/merkle-roots/{current}/consistency",
        params={"previous_root_id": previous}, headers=h)


# ---------------------------------------------------------------------------
class TestConsistencyEndpoint:
    def test_1_endpoint_exists(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        assert _consistency(client, h, r2, r1).status_code == 200

    def test_2_same_root_verified(self, client):
        h = _login(client)
        r1, _ = _two_real_checkpoints(client, h)
        d = _consistency(client, h, r1, r1).json()
        assert d["status"] == "VERIFIED"
        assert d["append_only_verified"] is True

    def test_3_proper_append_verified(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        d = _consistency(client, h, r2, r1).json()
        assert d["status"] == "VERIFIED"
        assert d["append_only_verified"] is True
        assert d["current_tree_size"] > d["previous_tree_size"]

    def test_4_response_shape(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        d = _consistency(client, h, r2, r1).json()
        for key in ("previous_root_id", "current_root_id",
                    "previous_tree_size", "current_tree_size",
                    "previous_root_hash", "current_root_hash",
                    "consistency_proof_nodes", "algorithm", "status",
                    "append_only_verified", "reason", "verified_at",
                    "checkpoint", "notes"):
            assert key in d, key
        assert d["algorithm"] == "sha256"
        assert isinstance(d["consistency_proof_nodes"], list)
        assert len(d["consistency_proof_nodes"]) > 0        # real proof nodes
        assert d["checkpoint"]["checkpoint_signature_status"] \
            == "NOT_IMPLEMENTED"

    def test_5_invalid_range(self, app, client):
        h = _login(client)
        big = _insert_root(app, leaves=[f"l{i}" for i in range(5)])
        small = _insert_root(app, leaves=[f"l{i}" for i in range(2)])
        d = _consistency(client, h, small, big).json()   # prev(5) > cur(2)
        assert d["status"] == "INVALID_RANGE"
        assert d["append_only_verified"] is False

    def test_6_unknown_previous_root_not_found(self, client):
        h = _login(client)
        _, r2 = _two_real_checkpoints(client, h)
        d = _consistency(client, h, r2, "does-not-exist").json()
        assert d["status"] == "ROOT_NOT_FOUND"
        assert d["append_only_verified"] is False

    def test_7_unknown_current_root_not_found(self, client):
        h = _login(client)
        r1, _ = _two_real_checkpoints(client, h)
        d = _consistency(client, h, "nope", r1).json()
        assert d["status"] == "ROOT_NOT_FOUND"

    def test_8_cross_tenant_comparison_denied(self, app, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        # A root that exists, but in another tenant, is simply not found —
        # never compared across the tenant boundary.
        foreign = _insert_root(app, tenant_id="other-tenant",
                               leaves=["x", "y"])
        d = _consistency(client, h, r2, foreign).json()
        assert d["status"] == "ROOT_NOT_FOUND"

    def test_9_reordered_prefix_not_verified(self, app, client):
        h = _login(client)
        base = [f"leaf{i:03d}" for i in range(4)]
        prev = _insert_root(app, leaves=base[:2])
        reordered = [base[1], base[0]] + base[2:]
        cur = _insert_root(app, leaves=reordered)
        d = _consistency(client, h, cur, prev).json()
        assert d["status"] == "NOT_VERIFIED"
        assert d["append_only_verified"] is False

    def test_10_replaced_prefix_not_verified(self, app, client):
        h = _login(client)
        base = [f"leaf{i:03d}" for i in range(4)]
        prev = _insert_root(app, leaves=base[:2])
        replaced = [base[0], "REPLACED"] + base[2:]
        cur = _insert_root(app, leaves=replaced)
        d = _consistency(client, h, cur, prev).json()
        assert d["status"] == "NOT_VERIFIED"

    def test_11_tampered_stored_root_not_verified(self, app, client):
        h = _login(client)
        base = [f"leaf{i:03d}" for i in range(2)]
        full = [f"leaf{i:03d}" for i in range(5)]
        prev = _insert_root(app, leaves=base)
        # A genuine append list, but the stored root hash is tampered.
        cur = _insert_root(app, leaves=full, root="deadbeef" * 8)
        d = _consistency(client, h, cur, prev).json()
        assert d["status"] == "NOT_VERIFIED"
        assert d["append_only_verified"] is False

    def test_12_missing_leaf_order_proof_missing(self, app, client):
        h = _login(client)
        prev = _insert_root(app, leaves=["a", "b"])
        # Historical leaf order lost: size claims 5 but no leaves stored.
        cur = _insert_root(app, leaves=[], root="x" * 64, size=5)
        d = _consistency(client, h, cur, prev).json()
        assert d["status"] == "PROOF_MISSING"
        assert d["append_only_verified"] is False

    def test_14_determinism(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        a = _consistency(client, h, r2, r1).json()["consistency_proof_nodes"]
        b = _consistency(client, h, r2, r1).json()["consistency_proof_nodes"]
        assert a == b and len(a) > 0

    def test_16_no_external_provider_note(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        d = _consistency(client, h, r2, r1).json()
        assert "No external transparency service is called." in d["notes"]
        assert "Merkle consistency proves append-only tree evolution only; " \
            "it does not prove legal validity." in d["notes"]

    def test_17_rbac_denied_without_audit_view(self, client):
        # Viewer/operator lack audit.view -> 403 (server-side gate).
        for role in ("viewer@demo.finalis", "operator@demo.finalis"):
            oh = _login(client)                     # owner creates the roots
            r1, r2 = _two_real_checkpoints(client, oh)
            h = _login(client, role)
            assert _consistency(client, h, r2, r1).status_code == 403

    def test_missing_previous_root_id_is_400(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        assert client.get(
            f"/evidence/merkle-roots/{r2}/consistency",
            headers=h).status_code == 400


class TestLineageEndpoint:
    def test_lineage_lists_roots_in_order(self, client):
        h = _login(client)
        r1, r2 = _two_real_checkpoints(client, h)
        d = client.get(f"/evidence/merkle-roots/{r2}/lineage",
                       headers=h).json()
        assert d["chain_length"] >= 2
        ids = [x["root_id"] for x in d["lineage"]]
        assert ids[0] == r1 and ids[-1] == r2
        assert d["lineage"][0]["previous_root_id"] is None
        assert d["lineage"][-1]["previous_root_id"] == r1

    def test_lineage_unknown_root_404(self, client):
        h = _login(client)
        assert client.get("/evidence/merkle-roots/nope/lineage",
                          headers=h).status_code == 404


class TestUnsupportedAlgorithmUnit:
    def test_13_unsupported_algorithm_refused(self):
        # Algorithm agility guard at the math layer (endpoint pins sha256).
        r = mrk.consistency_report(
            old_leaves=["a"], old_root=mrk.merkle_root(["a"]), old_size=1,
            new_leaves=["a", "b"], new_root=mrk.merkle_root(["a", "b"]),
            new_size=2, algorithm="md5")
        assert r.status == "UNSUPPORTED_ALGORITHM"
        assert r.append_only_verified is False


class TestServerVerifiesProof:
    def test_15_verified_only_when_proof_reconstructs_both_heads(self):
        # A VERIFIED verdict requires the compact RFC 9162 proof to
        # reconstruct BOTH canonical tree heads (server-side verify step).
        leaves = [f"n{i}" for i in range(7)]
        for m in range(1, 7):
            proof = mrk.consistency_proof(m, leaves)
            assert mrk.verify_consistency(
                m, 7, mrk.mth(leaves[:m]), mrk.mth(leaves), proof) is True
            # A wrong previous head must not verify.
            assert mrk.verify_consistency(
                m, 7, "wrong", mrk.mth(leaves), proof) is False
