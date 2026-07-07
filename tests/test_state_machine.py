"""State machine tests — validates finalis.state_machine against docs 03 §2/§4
and the machine-readable docs/finalis-ai/state-machine.finalis.json."""
import json
import random
from pathlib import Path

import pytest

from finalis.audit import AuditLog
from finalis.models import Case
from finalis.state_machine import (
    ACTIVE_STATES, CLOSED_REOPENABLE_STATES, PARKED_STATES, TERMINAL_STATES,
    TRANSITIONS, CaseState, IllegalTransition, is_legal, transition,
)

JSON_PATH = Path(__file__).resolve().parents[1] / "docs" / "finalis-ai" / \
    "state-machine.finalis.json"


def make_case(**kw) -> Case:
    return Case(tenant_id="t1", **kw)


class TestStateSets:
    def test_17_states(self):
        assert len(CaseState) == 17

    def test_partition_is_complete_and_disjoint(self):
        union = ACTIVE_STATES | TERMINAL_STATES | CLOSED_REOPENABLE_STATES | PARKED_STATES
        assert union == set(CaseState)
        assert not (ACTIVE_STATES & TERMINAL_STATES)
        assert not (TERMINAL_STATES & CLOSED_REOPENABLE_STATES)

    def test_terminals_have_no_exits(self):
        assert TRANSITIONS[CaseState.COMPLETED] == set()
        assert TRANSITIONS[CaseState.ABANDONED] == set()

    def test_all_states_reachable_from_new_contact(self):
        seen, frontier = {CaseState.NEW_CONTACT}, [CaseState.NEW_CONTACT]
        while frontier:
            nxt = frontier.pop()
            for t in TRANSITIONS[nxt]:
                if t not in seen:
                    seen.add(t)
                    frontier.append(t)
        assert seen == set(CaseState), f"unreachable: {set(CaseState) - seen}"

    def test_every_non_terminal_has_an_exit(self):
        for s in set(CaseState) - TERMINAL_STATES:
            assert TRANSITIONS[s], f"{s} is a dead end"


class TestTransitions:
    def test_legal_happy_path(self):
        case = make_case()
        audit = AuditLog()
        path = [CaseState.INTAKE_IN_PROGRESS, CaseState.QUALIFIED,
                CaseState.WAITING_FOR_DOCUMENTS, CaseState.DOCUMENT_ANALYSIS,
                CaseState.QUOTE_PREPARATION, CaseState.OFFER_SENT,
                CaseState.FOLLOW_UP_ACTIVE, CaseState.WON]
        for to in path:
            transition(case, to, actor="test", reason="happy", audit_log=audit)
        assert case.state is CaseState.WON
        # 03 §2 invariant 4: every transition wrote an AuditEvent.
        assert len(audit.events(event_type="case.state_changed")) == len(path)
        assert audit.verify_chain()

    def test_illegal_transition_rejected(self):
        case = make_case()  # NEW_CONTACT
        with pytest.raises(IllegalTransition):
            transition(case, CaseState.WON, actor="test", reason="cheat",
                       audit_log=AuditLog())

    def test_terminal_states_reject_everything(self):
        for terminal in TERMINAL_STATES:
            for to in CaseState:
                assert not is_legal(terminal, to)

    def test_escalation_interrupt_from_any_active_state(self):
        for s in ACTIVE_STATES - {CaseState.HUMAN_REVIEW_REQUIRED}:
            assert is_legal(s, CaseState.HUMAN_REVIEW_REQUIRED,
                            escalation_interrupt=True)

    def test_escalation_interrupt_not_from_terminal(self):
        assert not is_legal(CaseState.COMPLETED, CaseState.HUMAN_REVIEW_REQUIRED,
                            escalation_interrupt=True)

    def test_stop_optout_closure_edge_from_any_non_terminal(self):
        """H2 fix: STOP in OFFER_SENT/NEGOTIATION/etc. must be legal."""
        for s in set(CaseState) - TERMINAL_STATES:
            assert is_legal(s, CaseState.ABANDONED, hard_opt_out=True), s

    def test_followup_exhaustion_closure_edge(self):
        assert is_legal(CaseState.FOLLOW_UP_ACTIVE, CaseState.ABANDONED,
                        followup_exhausted=True)

    def test_human_review_freezes_autonomy_at_2(self):
        case = make_case(autonomy_level=4)
        audit = AuditLog()
        transition(case, CaseState.HUMAN_REVIEW_REQUIRED, actor="system",
                   reason="escalation", audit_log=audit,
                   escalation_interrupt=True)
        assert case.effective_autonomy == 2
        transition(case, CaseState.INTAKE_IN_PROGRESS, actor="human",
                   reason="resolved", audit_log=audit)
        assert case.effective_autonomy == 4

    def test_hard_optout_suppresses_permanently(self):
        case = make_case(state=CaseState.OFFER_SENT)
        transition(case, CaseState.ABANDONED, actor="system", reason="STOP",
                   audit_log=AuditLog(), hard_opt_out=True)
        assert case.opted_out is True

    def test_random_walk_never_violates_invariants(self):
        """Property test: 500 random legal walks keep audit chain + legality."""
        rng = random.Random(42)
        for _ in range(50):
            case = make_case()
            audit = AuditLog()
            for _step in range(20):
                options = sorted(TRANSITIONS[case.state], key=lambda s: s.value)
                if not options:
                    break
                to = rng.choice(options)
                transition(case, to, actor="walk", reason="rand",
                           audit_log=audit)
            assert audit.verify_chain()


class TestJsonConsistency:
    """The machine-readable JSON and the Python table must agree exactly."""

    @pytest.fixture()
    def spec(self):
        if not JSON_PATH.exists():
            pytest.skip("state-machine.finalis.json not present")
        return json.loads(JSON_PATH.read_text())

    def test_same_state_set(self, spec):
        assert set(spec["states"].keys()) == {s.value for s in CaseState}

    def test_same_transitions(self, spec):
        # The JSON may compress HUMAN_REVIEW_REQUIRED's exits as a wildcard
        # ("ANY_ACTIVE"); expand it before comparing.
        json_pairs = set()
        for t in spec["transitions"]:
            if t["to"] == "ANY_ACTIVE":
                for s in ACTIVE_STATES - {CaseState.HUMAN_REVIEW_REQUIRED}:
                    json_pairs.add((t["from"], s.value))
            else:
                json_pairs.add((t["from"], t["to"]))
        py_pairs = {(f.value, t.value)
                    for f, targets in TRANSITIONS.items() for t in targets}
        assert json_pairs == py_pairs, (
            f"json-only: {sorted(json_pairs - py_pairs)}; "
            f"py-only: {sorted(py_pairs - json_pairs)}")

    def test_global_edges_present(self, spec):
        names = {e["name"] for e in spec["global_edges"]}
        assert "escalation_interrupt" in names
        assert "closure_edge" in names
