"""CORE-A4.2 — approval decision model + decision hashing + decision-gate
validation (pure + API). A decision records who decided, what they saw, and
what they acknowledged; it executes nothing."""
import math

import pytest

from finalis.ai_employee import approval_decisions as D

from conftest import OWNER2, MANAGER, VIEWER


def _decision(**over):
    kw = dict(
        approval_decision_id="d1", approval_request_id="ar1", tenant_id="t1",
        run_id="r1", task_id="k1", decider_user_id="u1", decider_role="owner",
        decision="APPROVE", decision_reason="looks fine",
        approval_request_hash_snapshot="rq", approval_package_hash_snapshot="pk",
        approval_challenge_hash_snapshot="ch",
        approval_precondition_hash_snapshot="pre", viewed_package_hash="pk",
        acknowledgements={"risk_acknowledged": True}, challenge_passed=True,
        decision_time="2026-07-08T00:00:00Z")
    kw.update(over)
    return D.build_decision(**kw)


class TestDecisionHashPure:
    def test_actor_type_is_human(self):
        assert _decision()["decider_actor_type"] == "HUMAN_USER"

    def test_hash_excludes_itself(self):
        d = _decision()
        d2 = dict(d, decision_hash="x", decision_chain_hash="y")
        assert D.decision_hash(d) == D.decision_hash(d2)

    def test_hash_excludes_decision_time(self):
        assert D.decision_hash(_decision(decision_time="a")) \
            == D.decision_hash(_decision(decision_time="b"))

    def test_changed_decision_changes_hash(self):
        assert _decision(decision="APPROVE")["decision_hash"] \
            != _decision(decision="REJECT")["decision_hash"]

    def test_changed_approver_changes_hash(self):
        assert _decision(decider_user_id="u1")["decision_hash"] \
            != _decision(decider_user_id="u2")["decision_hash"]

    def test_changed_acknowledgement_changes_hash(self):
        assert _decision(acknowledgements={"risk_acknowledged": True})[
            "decision_hash"] != _decision(
            acknowledgements={"risk_acknowledged": False})["decision_hash"]

    def test_key_order_irrelevant(self):
        assert D.canonical_json({"b": 1, "a": 2}) \
            == D.canonical_json({"a": 2, "b": 1})

    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            D.build_decision(
                approval_decision_id="d", approval_request_id="ar",
                tenant_id="t", run_id="r", task_id="k", decider_user_id="u",
                decider_role="owner", decision="APPROVE", decision_reason="x",
                approval_request_hash_snapshot="a",
                approval_package_hash_snapshot="b",
                approval_challenge_hash_snapshot="c",
                approval_precondition_hash_snapshot="d",
                viewed_package_hash="b",
                acknowledgements={"x": math.nan}, challenge_passed=True,
                decision_time="t")

    def test_unknown_decision_rejected(self):
        with pytest.raises(ValueError):
            _decision(decision="SET_LEGAL")

    def test_chain_links_previous(self):
        first = _decision(approval_decision_id="d1")
        second = D.build_decision(
            approval_decision_id="d2", approval_request_id="ar1",
            tenant_id="t1", run_id="r1", task_id="k1", decider_user_id="u1",
            decider_role="owner", decision="REVOKE", decision_reason="x",
            approval_request_hash_snapshot="rq",
            approval_package_hash_snapshot="pk",
            approval_challenge_hash_snapshot="ch",
            approval_precondition_hash_snapshot="pre", viewed_package_hash="pk",
            acknowledgements={}, challenge_passed=False, decision_time="t",
            previous_decision_hash=first["decision_hash"])
        assert second["decision_chain_hash"] != first["decision_chain_hash"]


class TestRoleSatisfies:
    def test_owner_satisfies_manager(self):
        assert D.role_satisfies("owner", "manager") is True

    def test_manager_does_not_satisfy_owner(self):
        assert D.role_satisfies("manager", "owner") is False

    def test_viewer_and_ai_worker_satisfy_nothing(self):
        assert D.role_satisfies("viewer", "manager") is False
        assert D.role_satisfies("ai_worker", "manager") is False


class TestDecisionApi:
    def test_approve_records_decision_fields(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        r = gate.approve(ap, challenge=False).json()
        d = r["approval_decision"]
        assert d["decider_actor_type"] == "HUMAN_USER"
        assert d["decider_user_id"]
        assert d["decision"] == "APPROVE"
        assert d["decision_hash"]
        assert d["viewed_package_hash"] == ap["approval_package_hash"]
        assert d["acknowledgements"]

    def test_viewed_hash_mismatch_rejected(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        r = gate.approve(ap, challenge=False, viewed="deadbeef")
        assert r.status_code == 422

    def test_challenge_required_but_not_passed_rejected(self, gate):
        ap, _ = gate.make_request("merge_proposal")   # HIGH -> challenge
        r = gate.approve(ap, challenge=False)
        assert r.status_code == 422

    def test_missing_acknowledgement_rejected(self, gate):
        ap, _ = gate.make_request("merge_proposal")
        acks = {a: True for a in ap["policy_decision_capsule"][
            "required_acknowledgements"]}
        first = sorted(acks)[0]
        acks[first] = False
        r = gate.approve(ap, challenge=True, acks=acks)
        assert r.status_code == 422

    def test_reject_is_terminal(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/reject",
                        json={"decision_reason": "no"},
                        headers=gate.h(OWNER2))
        assert r.status_code == 200
        assert r.json()["approval_status"] == "REJECTED"
        # a rejected request cannot then be approved
        assert gate.approve(ap, challenge=False).status_code == 409

    def test_request_changes_records_decision(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/changes",
                        json={"decision_reason": "fix tone"},
                        headers=gate.h(OWNER2))
        assert r.json()["approval_status"] == "CHANGES_REQUESTED"
        assert r.json()["approval_decision"]["decision"] == "REQUEST_CHANGES"
