"""CORE-A5 — transition graph verifier (pure). The graph is internally valid:
declared states/events, no dangling edges, terminal states have no active
outgoing edges, and approval/completion paths cannot be bypassed."""
from finalis.ai_employee import lifecycle as L


class TestGraphVerifier:
    def test_graph_verifies_matched(self):
        assert L.verify_graph()["graph_verification_status"] == "MATCHED"

    def test_all_required_states_declared(self):
        for s in ["INTAKE_RECEIVED", "ACCEPTED", "APPROVAL_PENDING",
                  "APPROVED_READY", "RUN_READY", "RUNNING_LEDGER_ONLY",
                  "COMPLETION_CHECK_REQUIRED", "COMPLETION_BLOCKED",
                  "COMPLETED_NO_SIDE_EFFECTS", "RECONCILIATION_REQUIRED"]:
            assert s in L.STATE_SET

    def test_all_required_events_declared(self):
        for e in ["TASK_ACCEPTED", "APPROVAL_GRANT_VALIDATED",
                  "TASK_COMPLETED_NO_SIDE_EFFECTS", "COMPLETION_CHECK_REQUESTED",
                  "TASK_RECONCILIATION_REQUIRED"]:
            assert e in L.EVENT_SET

    def test_no_edge_points_to_unknown_state(self):
        for x in L.EDGES:
            assert x["from"] in L.STATE_SET and x["to"] in L.STATE_SET
            assert x["event"] in L.EVENT_SET

    def test_terminal_states_have_no_outgoing_edges(self):
        for x in L.EDGES:
            assert x["from"] not in L.TERMINAL_STATES

    def test_no_forbidden_side_effect_event_in_graph(self):
        events = {x["event"] for x in L.EDGES}
        assert not (events & L.FORBIDDEN_SIDE_EFFECT_EVENTS)
        assert L.verify_graph()["forbidden_event_violations"] == []

    def test_completion_cannot_be_reached_without_check(self):
        for x in L.EDGES:
            if x["to"] == "COMPLETED_NO_SIDE_EFFECTS":
                assert x["from"] == "COMPLETION_CHECK_REQUIRED"
                assert x["requires_completion_ready"] is True

    def test_approved_ready_requires_grant_from_pending(self):
        for x in L.EDGES:
            if x["to"] == "APPROVED_READY":
                assert x["from"] == "APPROVAL_PENDING"
                assert x["requires_approval_grant"] is True

    def test_every_non_terminal_state_has_exit(self):
        for s in L.STATES:
            if s in L.TERMINAL_STATES:
                continue
            assert any(x["from"] == s for x in L.EDGES), s

    def test_all_states_reachable(self):
        assert L.verify_graph()["unreachable_states"] == []

    def test_high_risk_edges_declare_requirements(self):
        # The two safety-critical transitions must be flagged high-risk AND
        # carry their guard requirement.
        appr = L.find_edge("APPROVAL_PENDING", "APPROVAL_GRANT_VALIDATED")
        comp = L.find_edge("COMPLETION_CHECK_REQUIRED",
                           "TASK_COMPLETED_NO_SIDE_EFFECTS")
        assert appr["high_risk"] and appr["requires_approval_grant"]
        assert comp["high_risk"] and comp["requires_completion_ready"]

    def test_verifier_detects_unknown_target_state(self):
        bad = L.EDGES + [L._e("ACCEPTED", "TASK_ACCEPTED", "MADE_UP_STATE")]
        gv = L.verify_graph(bad)
        assert gv["graph_verification_status"] == "MISMATCHED"
        assert any(e["reason"] == "unknown to_state"
                   for e in gv["invalid_edges"])

    def test_verifier_detects_terminal_origin_edge(self):
        bad = L.EDGES + [L._e("CANCELLED", "TASK_ACCEPTED", "ACCEPTED")]
        gv = L.verify_graph(bad)
        assert gv["graph_verification_status"] == "MISMATCHED"
        assert gv["terminal_state_violations"]

    def test_verifier_detects_completion_bypass(self):
        bad = L.EDGES + [L._e("ACCEPTED", "TASK_ACCEPTED",
                              "COMPLETED_NO_SIDE_EFFECTS")]
        gv = L.verify_graph(bad)
        assert gv["graph_verification_status"] == "MISMATCHED"
        assert gv["bypass_violations"]

    def test_verifier_detects_forbidden_event(self):
        bad = L.EDGES + [{"from": "ACCEPTED", "event": "PAYMENT_EXECUTED",
                          "to": "RUN_READY", "requires_approval_grant": False,
                          "requires_completion_ready": False,
                          "high_risk": False}]
        gv = L.verify_graph(bad)
        assert gv["forbidden_event_violations"]
        assert gv["graph_verification_status"] == "MISMATCHED"

    def test_graph_hash_deterministic(self):
        assert L.verify_graph()["graph_hash"] == L.verify_graph()["graph_hash"]
