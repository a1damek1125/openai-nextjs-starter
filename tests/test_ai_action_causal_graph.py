"""TOOL-B4 Causal Pre-Action Reference Monitor — causal action graph tests.

The causal action graph is a deterministic DAG of the prerequisites a FUTURE
broker execution would depend on. A clean proposal establishes every node; a
missing prerequisite (e.g. no contract) leaves a node UNKNOWN, makes the graph
incomplete, and yields CAUSAL_GRAPH_INCOMPLETE -> PREACTION_DENIED.
"""
from finalis.ai_employee import tool_guardrails as g

_CREATED = "2026-01-01T00:00:00Z"
_VALID_STATUSES = {"SATISFIED", "UNSATISFIED", "UNKNOWN"}


def _mkprop(gate, tool_id, contract, contract_id=None, **over):
    body = gate.clean_proposal_body(tool_id, contract, **over)
    return g.build_action_proposal(
        proposal_id="p1", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"] if contract_id is None
        else contract_id,
        raw=body, actor_id="u1", actor_type="human", created_at=_CREATED)


def _ev(gate, tool_id, base_contract, proposal, **over):
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    kw = dict(proposal=proposal, head=head, quality_report=quality,
              contract=base_contract, broker_readiness=None,
              circuit_breaker=None,
              prior_decision=None, role_authority=["READ"], policy=None,
              usage=None, decision_id="d1", tenant_id=gate.tid, actor_id="u1",
              actor_type="human", created_at=_CREATED,
              allowed_purposes=["CASE_TRIAGE"])
    kw.update(over)
    return g.evaluate_proposal(**kw)


def test_clean_proposal_graph_complete_all_nodes_satisfied(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract, _mkprop(gate, tool_id, contract))
    cg = d["causal_action_graph"]
    assert cg["graph_complete"] is True
    assert cg["signal"] is None
    assert cg["unsatisfied_nodes"] == []
    # Exactly the documented node set, all SATISFIED.
    assert [n["node"] for n in cg["nodes"]] == g._CAUSAL_NODES
    assert len(cg["nodes"]) == 17
    assert all(n["status"] == "SATISFIED" for n in cg["nodes"])
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


def test_node_statuses_are_valid_values(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract, _mkprop(gate, tool_id, contract))
    for n in d["causal_action_graph"]["nodes"]:
        assert n["node"] in g._CAUSAL_NODES
        assert n["status"] in _VALID_STATUSES


def test_no_contract_makes_graph_incomplete_and_denies(gate):
    tool_id, contract = gate.preaction_tool()
    # A proposal evaluated with NO authoritative contract: CONTRACT_PRESENT
    # cannot be established -> UNKNOWN -> incomplete -> CAUSAL_GRAPH_INCOMPLETE.
    proposal = _mkprop(gate, tool_id, contract, contract_id="")
    d = _ev(gate, tool_id, contract, proposal, contract=None)
    cg = d["causal_action_graph"]
    assert cg["graph_complete"] is False
    assert cg["signal"] == "CAUSAL_GRAPH_INCOMPLETE"
    contract_node = [n for n in cg["nodes"]
                     if n["node"] == "CONTRACT_PRESENT"][0]
    assert contract_node["status"] == "UNKNOWN"
    assert "CONTRACT_PRESENT" in cg["unsatisfied_nodes"]
    assert d["dominant_signal"] == "CAUSAL_GRAPH_INCOMPLETE"
    assert d["decision_status"] == "PREACTION_DENIED"


def test_bad_intent_marks_intent_node_unsatisfied(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract, intent="NOT_A_PURPOSE"))
    cg = d["causal_action_graph"]
    intent_node = [n for n in cg["nodes"]
                   if n["node"] == "INTENT_ALIGNED"][0]
    assert intent_node["status"] == "UNSATISFIED"
    assert "INTENT_ALIGNED" in cg["unsatisfied_nodes"]
    # An UNSATISFIED node (not UNKNOWN) does not itself make the graph
    # incomplete; the specific INTENT_MISMATCH signal dominates instead.
    assert cg["graph_complete"] is True
    assert d["dominant_signal"] == "INTENT_MISMATCH"


def test_build_causal_action_graph_direct_unknown_node(gate):
    # A prerequisite whose truth cannot be established is UNKNOWN and makes the
    # graph incomplete (fail-closed).
    node_status = {name: "SATISFIED" for name in g._CAUSAL_NODES}
    node_status["CONTRACT_PRESENT"] = "UNKNOWN"
    graph = g.build_causal_action_graph(
        head={}, quality_report={}, contract=None, broker_readiness={},
        node_status=node_status)
    assert graph["graph_complete"] is False
    assert graph["signal"] == "CAUSAL_GRAPH_INCOMPLETE"
    assert "CONTRACT_PRESENT" in graph["unsatisfied_nodes"]
    # A fully-satisfied node map completes the graph.
    complete = g.build_causal_action_graph(
        head={}, quality_report={}, contract={}, broker_readiness={},
        node_status={name: "SATISFIED" for name in g._CAUSAL_NODES})
    assert complete["graph_complete"] is True
    assert complete["signal"] is None


def test_causal_graph_subread_endpoint(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract)
    pid = d["proposal_id"]
    r = gate.pa(pid, path="/causal-graph")
    assert r.status_code == 200
    body = r.json()
    assert body["proposal_id"] == pid
    cg = body["causal_action_graph"]
    assert [n["node"] for n in cg["nodes"]] == g._CAUSAL_NODES
    assert cg["graph_complete"] is True


def test_submit_for_tool_without_contract_denies(gate):
    # An admitted tool with NO contract at all: the monitor cannot bind a
    # contract -> CONTRACT_PRESENT UNKNOWN -> CAUSAL_GRAPH_INCOMPLETE.
    tool_id = gate.contract_tool()
    body = {"tool_id": tool_id, "action_path": "search",
            "intent": "CASE_TRIAGE", "payload": {"query": "hi"}}
    d = gate.propose(body=body).json()
    assert d["decision_status"] == "PREACTION_DENIED"
    assert d["dominant_signal"] == "CAUSAL_GRAPH_INCOMPLETE"
    assert d["executes_nothing"] is True
    assert d["causal_action_graph"]["graph_complete"] is False
