"""TOOL-B8: RBAC — creating a commit simulation requires case.update; reading
requires case.read; the /safe view hides all_signals from restricted roles but
still reports the non-execution invariants."""
from tests.conftest import OWNER, MANAGER, VIEWER


def _b7(gate, requester=OWNER):
    wid, _ = gate.b7_write_intent_outcome(requester=requester)
    return wid


def test_owner_can_create(gate):
    wid = _b7(gate)
    assert gate.commit_simulation(wid, actor=OWNER).status_code == 200


def test_manager_can_create(gate):
    wid = _b7(gate)
    assert gate.commit_simulation(wid, actor=MANAGER).status_code == 200


def test_operator_can_create(gate):
    gate.add_user("op@demo.finalis", "operator")
    wid = _b7(gate)
    assert gate.commit_simulation(
        wid, actor="op@demo.finalis").status_code == 200


def test_viewer_cannot_create(gate):
    wid = _b7(gate)
    assert gate.commit_simulation(wid, actor=VIEWER).status_code == 403


def test_viewer_can_read(gate):
    sid, _ = gate.prepared_commit_simulation()
    assert gate.cs(sid, "", actor=VIEWER).status_code == 200
    assert gate.cs(sid, "/outcome", actor=VIEWER).status_code == 200


def test_viewer_can_read_registry_and_policy(gate):
    gate.prepared_commit_simulation()
    assert gate.c.get("/ai-tools/commit-simulations/registry",
                      headers=gate.h(VIEWER)).status_code == 200
    assert gate.c.get("/ai-tools/commit-simulations/policy",
                      headers=gate.h(VIEWER)).status_code == 200


def test_viewer_can_verify(gate):
    sid, _ = gate.prepared_commit_simulation()
    assert gate.cs(sid, "/verify", actor=VIEWER,
                   method="POST").status_code == 200


def test_safe_view_hides_all_signals_for_viewer(gate):
    sid, _ = gate.prepared_commit_simulation()
    full = gate.cs(sid, "/safe", actor=OWNER).json()
    assert full["all_signals"]
    restricted = gate.cs(sid, "/safe", actor=VIEWER).json()
    assert restricted["all_signals"] == []


def test_safe_view_not_hidden_for_operator(gate):
    sid, _ = gate.prepared_commit_simulation()
    gate.add_user("op2@demo.finalis", "operator")
    safe = gate.cs(sid, "/safe", actor="op2@demo.finalis").json()
    assert safe["all_signals"]


def test_safe_view_reports_non_execution_for_viewer(gate):
    sid, _ = gate.prepared_commit_simulation()
    safe = gate.cs(sid, "/safe", actor=VIEWER).json()
    assert safe["simulation_only"] is True
    assert safe["commit_executable_now"] is False
    assert safe["is_real_commit"] is False
    assert safe["produced_external_effect"] is False
    assert safe["b9_revalidation_required"] is True


def test_safe_view_full_for_owner_reports_non_execution(gate):
    sid, _ = gate.prepared_commit_simulation()
    safe = gate.cs(sid, "/safe", actor=OWNER).json()
    assert safe["simulation_only"] is True
    assert safe["commit_executable_now"] is False
    assert safe["b9_revalidation_required"] is True
