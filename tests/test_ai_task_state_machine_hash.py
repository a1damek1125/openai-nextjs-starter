"""CORE-A5 — deterministic lifecycle/transition/completion hashing (pure).
Every hash excludes itself, is key-order independent, changes with covered
content, and rejects NaN/Infinity."""
import math

import pytest

from finalis.ai_employee import lifecycle as L


def _ctx(**over):
    ctx = dict(tenant_id="t", task_id="k", run_id=None, from_state="ACCEPTED",
               event="DRAFT_CREATED", actor_id="u", actor_type="human",
               actor_role="owner", expected_version=1, version_match=True,
               contract_hash="c", envelope_hash="e", approval_grant_hash=None,
               idempotency_key=None, tenant_match=True, actor_authorized=True,
               contract_hash_match=True, envelope_hash_match=True)
    ctx.update(over)
    return ctx


class TestCanonical:
    def test_key_order_irrelevant(self):
        assert L.canonical_json({"b": 1, "a": 2}) \
            == L.canonical_json({"a": 2, "b": 1})

    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            L.canonical_json({"x": math.nan})

    def test_infinity_rejected(self):
        with pytest.raises(ValueError):
            L.canonical_json({"x": math.inf})


class TestTransitionInputHash:
    def test_same_input_same_hash(self):
        assert L.transition_input_hash(_ctx()) \
            == L.transition_input_hash(_ctx())

    def test_changed_from_state_changes_hash(self):
        assert L.transition_input_hash(_ctx(from_state="ACCEPTED")) \
            != L.transition_input_hash(_ctx(from_state="RUN_READY"))

    def test_changed_event_changes_hash(self):
        assert L.transition_input_hash(_ctx(event="DRAFT_CREATED")) \
            != L.transition_input_hash(_ctx(event="TASK_CANCELLED"))

    def test_changed_actor_changes_hash(self):
        assert L.transition_input_hash(_ctx(actor_id="u1")) \
            != L.transition_input_hash(_ctx(actor_id="u2"))

    def test_changed_tenant_changes_hash(self):
        assert L.transition_input_hash(_ctx(tenant_id="t1")) \
            != L.transition_input_hash(_ctx(tenant_id="t2"))

    def test_changed_contract_hash_changes_hash(self):
        assert L.transition_input_hash(_ctx(contract_hash="a")) \
            != L.transition_input_hash(_ctx(contract_hash="b"))

    def test_changed_grant_hash_changes_hash(self):
        assert L.transition_input_hash(_ctx(approval_grant_hash="g1")) \
            != L.transition_input_hash(_ctx(approval_grant_hash="g2"))


class TestOutputHash:
    def test_changed_guard_result_changes_output(self):
        d1 = L.decide_transition(_ctx())
        d2 = L.decide_transition(_ctx(from_state="APPROVAL_PENDING",
                                      event="APPROVAL_GRANT_VALIDATED",
                                      approval_grant_validation_status="NONE"))
        assert L.transition_output_hash(d1) != L.transition_output_hash(d2)


class TestTransitionHash:
    def _rec(self, **over):
        rec = {"tenant_id": "t", "task_id": "k", "from_state": "ACCEPTED",
               "to_state": "DRAFT_READY", "transition_event": "DRAFT_CREATED",
               "transition_status": "ALLOWED", "guard_vector_hash": "gv",
               "transition_hash": "x", "previous_transition_hash": "p",
               "transition_chain_hash": "c", "created_at": "t0",
               "honesty_labels": ["a"], "task_state_hash_after": "s"}
        rec.update(over)
        return rec

    def test_excludes_itself_and_volatile(self):
        a = self._rec(transition_hash="x", transition_chain_hash="c1",
                      created_at="t1", task_state_hash_after="s1")
        b = self._rec(transition_hash="y", transition_chain_hash="c2",
                      created_at="t2", task_state_hash_after="s2")
        assert L.transition_hash(a) == L.transition_hash(b)

    def test_changed_from_state_changes_hash(self):
        assert L.transition_hash(self._rec(from_state="ACCEPTED")) \
            != L.transition_hash(self._rec(from_state="RUN_READY"))

    def test_changed_to_state_changes_hash(self):
        assert L.transition_hash(self._rec(to_state="DRAFT_READY")) \
            != L.transition_hash(self._rec(to_state="REVIEW_READY"))

    def test_chain_hash_links_previous(self):
        h = L.transition_hash(self._rec())
        assert L.transition_chain_hash("prevA", h) \
            != L.transition_chain_hash("prevB", h)


class TestTaskStateHash:
    def _snap(self, **over):
        snap = {"task_id": "k", "tenant_id": "t", "lifecycle_state": "ACCEPTED",
                "task_version": 1, "task_contract_hash": "c",
                "completion_status": "NOT_CHECKED", "task_state_hash": "x",
                "updated_at": "t0", "honesty_labels": ["a"]}
        snap.update(over)
        return snap

    def test_excludes_itself_and_updated_at(self):
        assert L.task_state_hash(self._snap(task_state_hash="x",
                                            updated_at="t1")) \
            == L.task_state_hash(self._snap(task_state_hash="y",
                                            updated_at="t2"))

    def test_changes_with_state(self):
        assert L.task_state_hash(self._snap(lifecycle_state="ACCEPTED")) \
            != L.task_state_hash(self._snap(lifecycle_state="DRAFT_READY"))

    def test_changes_with_version(self):
        assert L.task_state_hash(self._snap(task_version=1)) \
            != L.task_state_hash(self._snap(task_version=2))


class TestCompletionHash:
    def _task(self, **over):
        t = {"task_id": "k", "tenant_id": "t", "task_type": "case_summary",
             "requires_human_approval": False, "requires_evidence_check": False,
             "requires_consent_check": False, "subject_id": None,
             "requires_run_ledger": False}
        t.update(over)
        return t

    def test_criteria_hash_deterministic(self):
        c1 = L.evaluate_completion(self._task(), {})
        c2 = L.evaluate_completion(self._task(), {})
        assert c1["completion_criteria_hash"] == c2["completion_criteria_hash"]

    def test_result_hash_changes_when_blocker_changes(self):
        ready = L.evaluate_completion(self._task(), {})
        blocked = L.evaluate_completion(
            self._task(requires_human_approval=True),
            {"approval_grant_validation_status": "NONE"})
        assert ready["completion_result_hash"] \
            != blocked["completion_result_hash"]

    def test_postcondition_hash_changes(self):
        ctx = _ctx()
        d = L.decide_transition(ctx)
        p1 = L.build_postconditions(ctx, d, applied=True)
        p2 = L.build_postconditions(ctx, d, applied=False)
        assert L.hash_post(p1) != L.hash_post(p2)
