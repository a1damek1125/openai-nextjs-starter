"""TOOL-B8 v1-v3 base: shadow-state commit dry-run — every delta applied to a
shadow copy only, never production; plus the upstream B7 consumption gate."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_shadow_dry_run_ok(gate):
    r = k.clean_outcome(gate)["shadow_dry_run"]
    assert r["dry_run_status"] == "DRY_RUN_OK"
    assert r["committed"] is False
    assert r["dry_run_only"] is True
    assert r["touches_production_state"] is False
    assert r["signal"] is None


def test_clean_deltas_never_production_applied(gate):
    r = k.clean_outcome(gate)["shadow_dry_run"]
    assert r["shadow_applied_deltas"]
    for d in r["shadow_applied_deltas"]:
        assert d["production_applied"] is False
        assert d["shadow_applied"] is True


def test_dry_run_certificate_hash_present(gate):
    r = k.clean_outcome(gate)["shadow_dry_run"]
    assert r["dry_run_certificate_hash"]


def test_dry_run_not_ok_fails(gate):
    o = k.clean_outcome(gate, dry_run_ok=False)
    assert o["dominant_signal"] == "SHADOW_DRY_RUN_FAILED"
    assert o["shadow_dry_run"]["dry_run_status"] == "FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_touches_production_fails(gate):
    o = k.clean_outcome(gate, touches_production=True)
    assert o["dominant_signal"] == "SHADOW_DRY_RUN_FAILED"
    assert o["shadow_dry_run"]["touches_production_state"] is True


def test_failure_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, dry_run_ok=False)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_shadow_dry_run_hash_recomputes(gate):
    r = k.clean_outcome(gate)["shadow_dry_run"]
    assert _core_hash(r, "shadow_dry_run_hash", "signal") == \
        r["shadow_dry_run_hash"]


def test_b7_gate_not_escrow_draft(gate):
    b7 = dict(k.b7_outcome(gate))
    b7["write_intent_status"] = "X"
    o = k.prepare(gate, b7)
    assert o["dominant_signal"] == "B7_NOT_ESCROW_DRAFT"


def test_b7_gate_not_future_ready(gate):
    b7 = dict(k.b7_outcome(gate))
    b7["ready_for_future_commit_only"] = False
    o = k.prepare(gate, b7)
    assert o["dominant_signal"] == "B7_NOT_FUTURE_READY"


def test_b7_gate_escrow_missing(gate):
    b7 = k.b7_outcome(gate)
    env = k.make_env(gate, b7)
    o = k.prepare(gate, None, env=env)
    assert o["dominant_signal"] == "B7_ESCROW_MISSING"


def test_b7_gate_cross_tenant(gate):
    b7 = dict(k.b7_outcome(gate))
    b7["tenant_id"] = b7["tenant_id"] + "-other"
    o = k.prepare(gate, b7)
    assert o["dominant_signal"] == "CROSS_TENANT"


def test_shadow_dry_run_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/shadow-dry-run").json()["shadow_dry_run"]
    assert r["dry_run_status"] == "DRY_RUN_OK"
    assert r["committed"] is False
