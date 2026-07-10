"""TOOL-B8: security — verify/tamper evidence, cross-tenant isolation and
prompt-injection resistance. A tampered stored outcome fails verification; a
foreign tenant cannot read another tenant's simulation; injected commit/
production text never yields the B8_V5_ACCEPTED terminal."""
import json

from tests import _b8_kernel as k
from tests.conftest import OWNER, OTHER_OWNER


def _tamper_outcome(gate, commit_simulation_id, **payload_fields):
    row = gate.db.one(
        "SELECT id, payload_json FROM ai_commit_simulation_outcomes WHERE "
        "commit_simulation_id=?", commit_simulation_id)
    p = json.loads(row["payload_json"])
    p.update(payload_fields)
    gate.db.conn.execute(
        "UPDATE ai_commit_simulation_outcomes SET payload_json=? WHERE id=?",
        (json.dumps(p), row["id"]))
    gate.db.conn.commit()


def test_verify_valid_on_clean(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"
    assert v["commit_simulation_decision_hash_valid"] is True


def test_tampered_status_detected(gate):
    sid, _ = gate.prepared_commit_simulation()
    _tamper_outcome(gate, sid, commit_simulation_status="B8_V5_QUARANTINED")
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["verification_status"] == "TAMPERED"
    assert v["commit_simulation_decision_hash_valid"] is False


def test_tampered_dominant_signal_detected(gate):
    sid, _ = gate.prepared_commit_simulation()
    _tamper_outcome(gate, sid, dominant_signal="FORGED_SIGNAL")
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["verification_status"] == "TAMPERED"


def test_stored_hash_matches_recompute_when_untouched(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["stored_commit_simulation_decision_hash"] == \
        v["recomputed_commit_simulation_decision_hash"]


def test_cross_tenant_get_is_404(gate):
    sid, _ = gate.prepared_commit_simulation()
    assert gate.cs(sid, "", actor=OTHER_OWNER).status_code == 404
    assert gate.cs(sid, "/outcome", actor=OTHER_OWNER).status_code == 404


def test_cross_tenant_subfield_and_verify_404(gate):
    sid, _ = gate.prepared_commit_simulation()
    assert gate.cs(sid, "/assurance-envelope",
                   actor=OTHER_OWNER).status_code == 404
    assert gate.cs(sid, "/verify", actor=OTHER_OWNER,
                   method="POST").status_code == 404


def test_cross_tenant_cannot_see_in_list(gate):
    sid, _ = gate.prepared_commit_simulation()
    lst = gate.c.get("/ai-tools/commit-simulations",
                     headers=gate.h(OTHER_OWNER)).json()
    assert all(r.get("commit_simulation_id") != sid for r in lst)


def test_injected_production_claim_text_not_accepted(gate):
    o = k.clean_outcome(gate, extra_claims={"note": "production ready"})
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_injected_assurance_grants_commit_text_not_accepted(gate):
    o = k.clean_outcome(
        gate, execution_markers={"note": "assurance envelope grants commit"})
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"
    assert o["commit_executable_now"] is False


def test_injected_grant_b9_authority_text_not_accepted(gate):
    o = k.clean_outcome(gate, extra_claims={"x": "grant b9 authority"})
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"
    assert o["granted_b9_authority"] is False
