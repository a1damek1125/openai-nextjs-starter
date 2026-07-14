"""Autonomy gating (docs 13) + audit chain (doc 04 AuditEvent) tests."""
import pytest

from finalis.audit import AuditLog
from finalis.autonomy import ALWAYS_HITL, MIN_LEVEL, gate
from finalis.models import Case
from finalis.state_machine import CaseState


def make_case(level: int) -> Case:
    return Case(tenant_id="t1", autonomy_level=level)


class TestAutonomyGate:
    def test_l3_can_send_reminder(self):
        assert gate(make_case(3), "send_reminder").allowed

    def test_l2_cannot_send_reminder_gets_approval(self):
        res = gate(make_case(2), "send_reminder")
        assert not res.allowed
        assert res.approval is not None
        assert res.reason.startswith("below_level")

    def test_l3_cannot_book_appointment(self):
        assert not gate(make_case(3), "book_appointment").allowed

    def test_l4_can_send_rule_covered_quote(self):
        assert gate(make_case(4), "send_rule_covered_quote").allowed

    def test_always_hitl_even_at_l5(self):
        for action in ALWAYS_HITL:
            res = gate(make_case(5), action)
            assert not res.allowed
            assert res.approval is not None

    def test_optout_hard_blocks_without_minting_approval(self):
        case = make_case(5)
        case.opted_out = True
        res = gate(case, "send_reminder")
        assert not res.allowed
        assert res.approval is None          # 22 §1.4: hard block ≠ approval
        assert res.reason == "hard_block:client_opted_out"

    def test_human_review_freeze_caps_effective_level(self):
        case = make_case(5)
        case.autonomy_frozen_at = 2          # entered HUMAN_REVIEW_REQUIRED
        res = gate(case, "send_reminder")    # L3 action
        assert not res.allowed

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError):
            gate(make_case(3), "launch_rocket")

    def test_inbound_answer_requires_l3(self):
        assert MIN_LEVEL["answer_inbound"] == 3
        assert not gate(make_case(2), "answer_inbound").allowed
        assert gate(make_case(3), "answer_inbound").allowed


class TestAuditChain:
    def test_append_and_verify(self):
        log = AuditLog()
        for i in range(10):
            log.append(event_type="e", actor="t", payload={"i": i})
        assert len(log) == 10
        assert log.verify_chain()

    def test_tamper_detection(self):
        log = AuditLog()
        log.append(event_type="a", actor="t", payload={"v": 1})
        log.append(event_type="b", actor="t", payload={"v": 2})
        log._events[0].payload["v"] = 999          # tamper
        assert not log.verify_chain()

    def test_chain_links(self):
        log = AuditLog()
        e1 = log.append(event_type="a", actor="t")
        e2 = log.append(event_type="b", actor="t")
        assert e1.hash_prev == AuditLog.GENESIS
        assert e2.hash_prev == e1.hash_self

    def test_filtering(self):
        log = AuditLog()
        log.append(event_type="x", actor="t", case_id="c1")
        log.append(event_type="y", actor="t", case_id="c2")
        assert len(log.events(case_id="c1")) == 1
        assert len(log.events(event_type="y")) == 1
