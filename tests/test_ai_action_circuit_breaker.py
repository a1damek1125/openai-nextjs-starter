"""TOOL-B4: circuit-breaker set/list/get + its effect on decisions."""
from tests.conftest import OWNER, MANAGER, VIEWER


def test_owner_opens_breaker(gate):
    tool_id, contract = gate.preaction_tool()
    r = gate.c.post("/ai-tools/actions/circuit-breakers",
                    json={"tool_id": tool_id, "breaker_state": "OPEN",
                          "reason": "safety"}, headers=gate.h(OWNER))
    assert r.status_code == 200
    assert r.json()["breaker_state"] == "OPEN"


def test_list_and_get_breaker(gate):
    tool_id, contract = gate.preaction_tool()
    gate.open_breaker(tool_id, actor=OWNER)
    lst = gate.c.get("/ai-tools/actions/circuit-breakers",
                     headers=gate.h()).json()
    assert len(lst["circuit_breakers"]) == 1
    assert lst["circuit_breakers"][0]["tool_id"] == tool_id
    got = gate.c.get(f"/ai-tools/actions/circuit-breakers/{tool_id}",
                     headers=gate.h()).json()
    assert got["breaker_state"] == "OPEN"


def test_unknown_tool_defaults_closed(gate):
    got = gate.c.get("/ai-tools/actions/circuit-breakers/nope",
                     headers=gate.h()).json()
    assert got["breaker_state"] == "CLOSED"
    assert got["circuit_breaker_active"] is False


def test_open_breaker_blocks_submission(gate):
    tool_id, contract = gate.preaction_tool()
    gate.open_breaker(tool_id, actor=OWNER)
    d = gate.propose(tool_id, contract).json()
    assert d["decision_status"] == "PREACTION_CIRCUIT_BREAKER_ACTIVE"
    assert d["dominant_signal"] == "CIRCUIT_BREAKER_ACTIVE"


def test_closing_breaker_unblocks(gate):
    tool_id, contract = gate.preaction_tool()
    gate.open_breaker(tool_id, actor=OWNER)
    assert gate.propose(tool_id, contract).json()["dominant_signal"] == \
        "CIRCUIT_BREAKER_ACTIVE"
    gate.open_breaker(tool_id, actor=OWNER, state="CLOSED")
    d = gate.propose(tool_id, contract).json()
    assert d["dominant_signal"] != "CIRCUIT_BREAKER_ACTIVE"
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


def test_breaker_rbac_and_unknown_tool(gate):
    tool_id, contract = gate.preaction_tool()
    # manager may set a breaker; viewer may not.
    assert gate.open_breaker(tool_id, actor=MANAGER).status_code == 200
    assert gate.open_breaker(tool_id, actor=VIEWER).status_code == 403
    # setting a breaker on an unknown tool -> 404.
    assert gate.open_breaker("no-such-tool", actor=OWNER).status_code == 404
