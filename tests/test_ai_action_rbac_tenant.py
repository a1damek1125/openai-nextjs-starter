"""TOOL-B4: RBAC + tenant isolation on the pre-action monitor surface."""
from tests.conftest import OWNER, MANAGER, VIEWER, OTHER_OWNER


def test_viewer_can_read_but_not_submit(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    pid = d["proposal_id"]
    # reads require case.read -> viewer allowed.
    assert gate.c.get("/ai-tools/actions/proposals",
                      headers=gate.h(VIEWER)).status_code == 200
    assert gate.pa(pid, actor=VIEWER).status_code == 200
    assert gate.pa(pid, "/decision", actor=VIEWER).status_code == 200
    # submit requires case.update -> viewer forbidden.
    assert gate.propose(tool_id, contract, actor=VIEWER).status_code == 403


def test_cross_tenant_proposal_isolation(gate):
    # A proposal created in tenant A is invisible (404) to tenant B's owner.
    tool_id, contract = gate.preaction_tool()
    pid = gate.propose(tool_id, contract).json()["proposal_id"]
    assert gate.pa(pid, actor=OTHER_OWNER).status_code == 404
    assert gate.pa(pid, "/decision", actor=OTHER_OWNER).status_code == 404
    assert gate.pa(pid, "/safe", actor=OTHER_OWNER).status_code == 404


def test_cross_tenant_tool_in_body_404(gate):
    # A tool_id belonging to tenant A, referenced in a proposal submitted by
    # tenant B, is not found (server-side truth is tenant-scoped).
    tool_id, contract = gate.preaction_tool()
    assert gate.propose(tool_id, contract, actor=OTHER_OWNER).status_code == 404


def test_circuit_breaker_rbac(gate):
    tool_id, contract = gate.preaction_tool()
    # viewer cannot set a breaker.
    assert gate.open_breaker(tool_id, actor=VIEWER).status_code == 403
    # an AI worker can never clear/open its own stop.
    gate.add_user("ai@demo.finalis", "ai_worker")
    r = gate.c.post("/ai-tools/actions/circuit-breakers",
                    json={"tool_id": tool_id, "breaker_state": "OPEN"},
                    headers=gate.h("ai@demo.finalis"))
    assert r.status_code == 403
    # owner may set it.
    ok = gate.open_breaker(tool_id, actor=OWNER)
    assert ok.status_code == 200
    assert ok.json()["breaker_state"] == "OPEN"


def test_safe_view_redaction_by_role(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.propose(tool_id, contract).json()["proposal_id"]
    # viewer is a restricted role -> signals redacted.
    assert gate.pa(pid, "/safe", actor=VIEWER).json()["all_signals"] == []
    # a non-restricted role (operator) sees the signals.
    gate.add_user("op@demo.finalis", "operator")
    seen = gate.pa(pid, "/safe", actor="op@demo.finalis").json()["all_signals"]
    assert seen == ["ALLOWED_FOR_FUTURE_BROKER_ONLY"]


def test_reevaluate_requires_case_update(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.propose(tool_id, contract).json()["proposal_id"]
    # viewer cannot reevaluate (case.update); owner can.
    assert gate.pa(pid, "/reevaluate", actor=VIEWER,
                   method="POST").status_code == 403
    assert gate.pa(pid, "/reevaluate", actor=OWNER,
                   method="POST").status_code == 200
