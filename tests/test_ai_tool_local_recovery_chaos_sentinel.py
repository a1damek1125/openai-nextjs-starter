"""TOOL-B9.1 v4: Chaos Sentinel crash-drill harness (section 3). The runtime
replays a crash after every recovery lifecycle phase and proves each crash
leaves a prefix-valid, incomplete transaction that is SAFE: no external effect,
the inert outbox stays inert, tenant isolation holds. The harness runs on EVERY
outcome (clean AND blocked), the release gate PASSES only when all crashes are
safe, and a CRASH_DRILL action reports RECOVERY_REQUIRED.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


# --- kernel layer ----------------------------------------------------------
def test_chaos_sentinel_phase_count_21():
    h = k.clean_outcome()["b91_chaos_harness"]
    assert h["phase_count"] == 21
    assert len(h["phases"]) == 21


def test_chaos_sentinel_phase_names_match_crash_phases():
    h = k.clean_outcome()["b91_chaos_harness"]
    assert {ph["phase"] for ph in h["phases"]} == set(lr.CRASH_PHASES)
    assert len(lr.CRASH_PHASES) == 21


def test_chaos_sentinel_every_phase_no_external_effect():
    h = k.clean_outcome()["b91_chaos_harness"]
    for ph in h["phases"]:
        assert ph["no_external_effect"] is True


def test_chaos_sentinel_every_phase_inert_outbox_preserved():
    h = k.clean_outcome()["b91_chaos_harness"]
    for ph in h["phases"]:
        assert ph["inert_outbox_preserved"] is True


def test_chaos_sentinel_every_phase_tenant_isolation_preserved():
    h = k.clean_outcome()["b91_chaos_harness"]
    for ph in h["phases"]:
        assert ph["tenant_isolation_preserved"] is True


def test_chaos_sentinel_every_phase_safe():
    h = k.clean_outcome()["b91_chaos_harness"]
    for ph in h["phases"]:
        assert ph["safe"] is True


def test_chaos_sentinel_all_crashes_safe_and_status():
    h = k.clean_outcome()["b91_chaos_harness"]
    assert h["all_crashes_safe"] is True
    assert h["harness_status"] == "SAFE"


def test_chaos_sentinel_release_gate_passed():
    rg = k.clean_outcome()["b91_release_gate_report"]
    assert rg["release_gate_status"] == "PASSED"
    assert rg["all_crashes_safe"] is True
    assert rg["phase_count"] == 21


def test_chaos_sentinel_present_on_kill_switch_blocked():
    o = k.prepare(desired_recovery_action="RECOVER", kill_switch=True)
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "RUNTIME_KILL_SWITCH_ACTIVE"
    h = o["b91_chaos_harness"]
    assert h["phase_count"] == 21
    assert h["all_crashes_safe"] is True
    assert h["harness_status"] == "SAFE"
    assert o["b91_release_gate_report"]["release_gate_status"] == "PASSED"


def test_chaos_sentinel_present_on_poe_tamper_blocked():
    o = k.prepare(desired_recovery_action="RECOVER", poe_tamper=True)
    assert o["final_recovery_state"] == "TAMPERED"
    assert o["dominant_signal"] == "PROOF_OF_EXECUTION_TAMPERED"
    h = o["b91_chaos_harness"]
    assert h["phase_count"] == 21
    assert h["all_crashes_safe"] is True
    for ph in h["phases"]:
        assert ph["safe"] is True


def test_chaos_sentinel_present_on_authority_quarantine():
    o = k.prepare(desired_recovery_action="RECOVER",
                  recovery_authority_basis={"source": "DOCUMENT"})
    assert o["final_recovery_state"] == "QUARANTINED"
    h = o["b91_chaos_harness"]
    assert h["all_crashes_safe"] is True
    assert h["phase_count"] == 21
    # No actual external effect even on a quarantined outcome.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False


def test_chaos_sentinel_crash_drill_action_recovery_required():
    o = k.prepare(desired_recovery_action="CRASH_DRILL")
    assert o["final_recovery_state"] == "RECOVERY_REQUIRED"
    assert o["no_external_effect"] is True


def test_chaos_sentinel_harness_hash_recompute():
    h = k.clean_outcome()["b91_chaos_harness"]
    assert _core_hash(h, "chaos_hash") == h["chaos_hash"]


def test_chaos_sentinel_release_gate_hash_recompute():
    rg = k.clean_outcome()["b91_release_gate_report"]
    assert _core_hash(rg, "release_gate_hash", "signal") == \
        rg["release_gate_hash"]


def test_chaos_sentinel_every_phase_prefix_valid_reason():
    h = k.clean_outcome()["b91_chaos_harness"]
    for ph in h["phases"]:
        assert ph["reason_code"] == "CRASH_DRILL_PREFIX_VALID_INCOMPLETE"
        assert ph["classification"] == "RECOVERY_REQUIRED"


# --- API layer -------------------------------------------------------------
def test_chaos_sentinel_api_chaos_drill_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "chaos-drill")
    assert r.status_code == 200
    h = r.json()["b91_chaos_harness"]
    assert h["phase_count"] == 21
    assert h["all_crashes_safe"] is True
    assert h["harness_status"] == "SAFE"


def test_chaos_sentinel_api_release_gate_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "release-gate")
    assert r.status_code == 200
    rg = r.json()["b91_release_gate_report"]
    assert rg["release_gate_status"] == "PASSED"


def test_chaos_sentinel_api_crash_drill_action(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="crash-drill").json()
    assert o["final_recovery_state"] == "RECOVERY_REQUIRED"
    assert o["b91_chaos_harness"]["all_crashes_safe"] is True
    assert o["no_external_effect"] is True
