"""TOOL-B7: RBAC — creating a write-intent draft requires case.update; reading
requires case.read; the /safe view hides all_signals from restricted roles."""
from tests.conftest import OWNER, MANAGER, VIEWER


def test_owner_can_create(gate):
    b6rid, _ = gate.b6_runtime_outcome(requester=OWNER)
    assert gate.write_intent(b6rid, actor=OWNER).status_code == 200


def test_manager_can_create(gate):
    b6rid, _ = gate.b6_runtime_outcome(requester=MANAGER)
    assert gate.write_intent(b6rid, actor=MANAGER).status_code == 200


def test_viewer_cannot_create(gate):
    b6rid, _ = gate.b6_runtime_outcome(requester=OWNER)
    assert gate.write_intent(b6rid, actor=VIEWER).status_code == 403


def test_viewer_can_read(gate):
    wid, _ = gate.prepared_write_intent()
    assert gate.wi(wid, "", actor=VIEWER).status_code == 200
    assert gate.wi(wid, "/outcome", actor=VIEWER).status_code == 200


def test_viewer_can_read_registry_and_policy(gate):
    gate.prepared_write_intent()
    assert gate.c.get("/ai-tools/write-intents/registry",
                      headers=gate.h(VIEWER)).status_code == 200
    assert gate.c.get("/ai-tools/write-intents/policy",
                      headers=gate.h(VIEWER)).status_code == 200


def test_safe_view_hides_all_signals_for_viewer(gate):
    wid, _ = gate.prepared_write_intent()
    full = gate.wi(wid, "/safe", actor=OWNER).json()
    assert full["all_signals"]
    restricted = gate.wi(wid, "/safe", actor=VIEWER).json()
    assert restricted["all_signals"] == []


def test_safe_view_not_hidden_for_operator(gate):
    # Operator is NOT in the restricted set (viewer/technician/accountant), so
    # its safe view still exposes all_signals — contrast with the viewer.
    wid, _ = gate.prepared_write_intent()
    gate.add_user("op2@demo.finalis", "operator")
    safe = gate.wi(wid, "/safe", actor="op2@demo.finalis").json()
    assert safe["all_signals"]
    assert gate.wi(wid, "/safe", actor=VIEWER).json()["all_signals"] == []


def test_safe_view_still_reports_non_execution_for_restricted(gate):
    wid, _ = gate.prepared_write_intent()
    safe = gate.wi(wid, "/safe", actor=VIEWER).json()
    assert safe["draft_only"] is True
    assert safe["is_commit"] is False
    assert safe["is_execution"] is False
    assert safe["commit_executable_now"] is False
    assert safe["produced_external_effect"] is False


def test_safe_view_full_for_owner_reports_non_execution(gate):
    wid, _ = gate.prepared_write_intent()
    safe = gate.wi(wid, "/safe", actor=OWNER).json()
    assert safe["draft_only"] is True
    assert safe["commit_executable_now"] is False


def test_verify_requires_case_read_only(gate):
    wid, _ = gate.prepared_write_intent()
    # A viewer (case.read) may verify.
    assert gate.wi(wid, "/verify", actor=VIEWER,
                   method="POST").status_code == 200


def test_added_operator_can_create(gate):
    gate.add_user("op@demo.finalis", "operator")
    b6rid, _ = gate.b6_runtime_outcome(requester="op@demo.finalis")
    assert gate.write_intent(b6rid, actor="op@demo.finalis").status_code == 200
