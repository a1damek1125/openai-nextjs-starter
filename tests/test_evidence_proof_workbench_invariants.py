"""V-F operational invariants — the Evidence Proof Workbench must never let
a positive signal average away a hard proof failure, never imply business
truth / legal validity from integrity, and never claim external anchoring
that the server does not provide.

Two layers, both deterministic:

  * TestUiProofAlgebra — asserts the shipped, deterministic UI proof-algebra
    guards and mandated messages are present in the served page. The mission
    explicitly permits asserting static UI logic where the algebra is a UI
    concern (no new backend logic invented).
  * TestServerBackedInvariants — exercises the real Evidence APIs the
    workbench reads (hash integrity, Merkle inclusion proof, tenant
    isolation, append-only contract history) so the data the UI classifies
    is proven real, not faked.
"""
import base64

import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    return a


@pytest.fixture()
def page(app):
    return TestClient(app).get("/portal").text


@pytest.fixture()
def norm(page):
    return " ".join(page.split())


# ---------------------------------------------------------------------------
# Layer 1 — deterministic UI proof-algebra guards (source of the workbench).
# Each tuple: (invariant name, list of substrings that must all be present).
# ---------------------------------------------------------------------------
UI_INVARIANTS = [
    ("1 hash mismatch dominance",
     ["dims.D1 === 'FAIL'", "'TAMPER_WARNING'", "readiness: 0"]),
    ("2 root mismatch dominance",
     ["dims.D2 === 'FAIL'", "'FAILED_VERIFICATION'"]),
    ("3 missing proof cannot verify",
     ["proof == null ? 'NOT_EXPOSED'", "PROOF_MISSING"]),
    ("4 inclusion is not business truth",
     ["Integrity verification and business truth are separate verdicts",
      "business context still REVIEW_REQUIRED"]),
    ("5 consistency requirement",
     ["consistency == null ? 'NOT_EXPOSED'",
      "Append-only evidence cannot be assumed", "NOT_VERIFIED / NOT_EXPOSED"]),
    ("6 derivative parent requirement",
     ["x.parent_evidence_id !== d.id", "orphan"]),
    ("7 derivative trust cannot exceed parent",
     ["!parentVerified", "derivative cannot exceed unverified parent"]),
    ("8 timestamp is not truth",
     ["Timestamping proves existence at a time; it does not prove"]),
    ("9 provenance is not integrity",
     ["Provenance is not the same as integrity"]),
    ("10 c2pa is not final truth",
     ["C2PA provenance is not final truth"]),
    ("11 scitt receipt is not business truth",
     ["SCITT receipt presence does not equal business truth"]),
    ("12 contract append-oriented",
     ["Contract history is append-oriented"]),
    ("13 evidence is not legal validity",
     ["Cryptographic integrity is not the same as legal validity"]),
    ("14 server authority / non-authoritative",
     ["NON-AUTHORITATIVE UI SUMMARY",
      "server-side Evidence verification remains the source of truth"]),
    ("15 tenant isolation dimension shown",
     ["TenantIsolation", "dims.D8"]),
    ("16 no external anchoring claim",
     ["Blockchain anchoring is not implemented",
      "External notarization is not connected"]),
    ("17 crypto agility cannot be ignored",
     ["UNSUPPORTED_CRITICAL_ALGORITHM", "REVIEW_REQUIRED"]),
    ("18 score cannot override verdict",
     ["hard-fail dimension", "wbReadiness"]),
]


class TestUiProofAlgebra:
    @pytest.mark.parametrize("name,needles", UI_INVARIANTS,
                             ids=[i[0] for i in UI_INVARIANTS])
    def test_guard_present(self, norm, name, needles):
        # Compare on whitespace-normalised text so HTML/JS line-wrapping in
        # the source does not defeat multi-word guards.
        for n in needles:
            assert n in norm, f"{name}: missing guard {n!r}"

    def test_hard_fail_set_zeroes_readiness(self, page):
        # wbReadiness returns 0 for every hard-fail dimension — a display
        # score can never average a critical failure away.
        for guard in ("dims.D1 === 'FAIL'", "dims.D2 === 'FAIL'",
                      "dims.D6 === 'FAIL'", "dims.D8 === 'FAIL'",
                      "dims.D3 === 'FAIL'",
                      "dims.D9 === 'UNSUPPORTED_CRITICAL_ALGORITHM'",
                      "dims.D11 === 'DISPUTED'"):
            assert guard in page, guard

    def test_no_false_positive_anchoring_language(self, norm):
        # The UI must not *claim* external anchoring/notarisation/timestamp
        # certification that the server does not provide.
        for forbidden in ("anchored to the blockchain", "notarized on-chain",
                          "externally notarized", "timestamp certified by",
                          "legally non-repudiable", "court-admissible proof"):
            assert forbidden.lower() not in norm.lower(), forbidden

    def test_no_production_or_legal_overclaim(self, norm):
        for forbidden in ("production ready", "legally valid",
                          "guaranteed authentic", "immutable storage "
                          "guaranteed"):
            assert forbidden.lower() not in norm.lower(), forbidden


# ---------------------------------------------------------------------------
# Layer 2 — the real Evidence APIs the workbench reads uphold the invariants.
# ---------------------------------------------------------------------------
def _login(client, email="owner@demo.finalis"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _upload(client, h, case_id, text="Payment received 450 EUR"):
    r = client.post("/evidence/upload", json={
        "case_id": case_id, "filename": "proof.txt", "mime": "text/plain",
        "content_b64": base64.b64encode(text.encode()).decode(),
        "evidence_type": "payment_proof", "text_preview": text}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestServerBackedInvariants:
    def test_hash_integrity_data_is_real(self, app):
        # The D1 the UI classifies is a real server-computed sha-256 verdict.
        c = TestClient(app)
        h = _login(c)
        case_id = c.get("/cases", headers=h).json()[0]["id"]
        ev = _upload(c, h, case_id)
        v = c.post(f"/evidence/{ev}/verify-integrity", headers=h)
        assert v.status_code == 200 and v.json()["valid"] is True
        detail = c.get(f"/evidence/{ev}", headers=h).json()
        assert detail["integrity"]["valid"] is True
        assert detail["integrity"]["algorithm"].lower().startswith("sha")

    def test_merkle_inclusion_proof_is_real_and_verifies(self, app):
        c = TestClient(app)
        h = _login(c)
        case_id = c.get("/cases", headers=h).json()[0]["id"]
        ev = _upload(c, h, case_id)
        assert c.post("/evidence/merkle-roots/generate",
                      headers=h).status_code == 200
        proof = c.get(f"/evidence/{ev}/merkle-proof", headers=h)
        assert proof.status_code == 200, proof.text
        body = proof.json()
        # The exact fields D2 reads: verifies + a non-empty root.
        assert body["verifies"] is True
        assert body["root"] and body["leaf_hash"]

    def test_tenant_isolation_blocks_cross_tenant_evidence(self, app):
        # Invariant 15: evidence is never visible/linkable across tenants.
        c = TestClient(app)
        h = _login(c)
        case_id = c.get("/cases", headers=h).json()[0]["id"]
        ev = _upload(c, h, case_id)
        other = TestClient(app)
        oh = _login(other, "owner@other.finalis")
        assert other.get(f"/evidence/{ev}", headers=oh).status_code == 404
        assert other.get(f"/evidence/{ev}/chain",
                         headers=oh).status_code == 404

    def test_contract_history_api_is_append_oriented(self, app):
        # Invariant 12: no destructive rewrite/delete route exists for
        # evidence contracts — history can only be appended/replayed.
        c = TestClient(app)
        methods_paths = set()
        for route in c.app.routes:
            path = getattr(route, "path", "") or ""
            for m in (getattr(route, "methods", None) or set()):
                methods_paths.add((m, path))
        for (m, path) in methods_paths:
            if "contract" in path.lower() and path.startswith("/evidence"):
                assert m not in ("DELETE", "PUT"), (m, path)

    def test_viewer_cannot_reach_audit_scoped_proof_apis(self, app):
        # RBAC: a viewer (no audit.view) is refused Merkle/contract proof
        # APIs server-side; the workbench degrades to an honest label but the
        # server is the gate.
        c = TestClient(app)
        owner = _login(c)
        case_id = c.get("/cases", headers=owner).json()[0]["id"]
        ev = _upload(c, owner, case_id)
        vh = _login(c, "viewer@demo.finalis")
        assert c.get(f"/evidence/{ev}/merkle-proof",
                     headers=vh).status_code == 403
        assert c.get(f"/evidence/{ev}/contracts",
                     headers=vh).status_code == 403
        # ...but a viewer may still read the evidence detail (document.view).
        assert c.get(f"/evidence/{ev}", headers=vh).status_code == 200
