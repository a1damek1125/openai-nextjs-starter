"""EMP-A1 v1: clarification gate (section 16) + approval precondition
(section 17). Missing critical data is never guessed — it produces typed
clarification questions (deterministic minimum-question planning, budgeted).
Approval is a hard precondition: NONE needs none; STANDARD/DUAL_CONTROL require
a typed, bound approval record whose action/targets/scope cover the work, is
unexpired/unrevoked, and (for dual control) carries >=2 approvers. Natural
language statements are NOT approvals. No LLM ever supplies a missing value.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


def _reply(**over):
    """A customer_reply_draft request whose required message_intent is present
    (so it is not blocked on clarification) — used to drive the approval gate."""
    base = dict(work_type="customer_reply_draft",
                requested_target_refs=["case:E-1"],
                canonical_parameters={"target": "case:E-1",
                                      "message_intent": "reply"})
    base.update(over)
    return k.evaluate(**base)


# --- clarification gate (section 16) ---------------------------------------
def test_clarapp_no_missing_no_clarification():
    plan = wi.plan_clarification(intent={"missing_fields": []})
    assert plan["clarification_required"] is False
    assert plan["questions"] == []
    assert plan["signal"] == "INTAKE_VALID"


def test_clarapp_missing_data_not_guessed():
    o = k.evaluate(work_type="customer_reply_draft",
                   canonical_parameters={"target": "case:E-1"})
    assert o["clarification"]["clarification_required"] is True
    assert o["clarification"]["llm_supplied_values"] is False
    assert o["intent"]["guesses_critical_values"] is False


def test_clarapp_typed_questions_shape():
    plan = wi.plan_clarification(intent={"missing_fields": ["message_intent"]})
    q = plan["questions"][0]
    assert q["field_key"] == "message_intent"
    assert q["template_id"] == "clarify_field"
    assert q["question_id"].startswith("q-")
    assert plan["llm_supplied_values"] is False


def test_clarapp_question_ids_deterministic():
    a = wi.plan_clarification(intent={"missing_fields": ["a", "b", "c"]})
    b = wi.plan_clarification(intent={"missing_fields": ["a", "b", "c"]})
    ids_a = [q["question_id"] for q in a["questions"]]
    ids_b = [q["question_id"] for q in b["questions"]]
    assert ids_a == ids_b


def test_clarapp_questions_ordered_by_field_key():
    plan = wi.plan_clarification(intent={"missing_fields": ["charlie", "alpha",
                                                            "bravo"]})
    keys = [q["field_key"] for q in plan["questions"]]
    assert keys == ["alpha", "bravo", "charlie"]


def test_clarapp_truncated_to_budget_with_uncovered():
    missing = ["e5", "d4", "c3", "b2", "a1"]
    plan = wi.plan_clarification(intent={"missing_fields": missing},
                                 question_budget=2)
    assert [q["field_key"] for q in plan["questions"]] == ["a1", "b2"]
    assert plan["covered_blockers"] == ["a1", "b2"]
    assert plan["uncovered_blockers"] == ["c3", "d4", "e5"]


def test_clarapp_disposition_needs_clarification():
    o = k.evaluate(work_type="customer_reply_draft",
                   canonical_parameters={"target": "case:E-1"})
    assert o["disposition"] == "NEEDS_CLARIFICATION"
    assert o["resulting_state"] == "NEEDS_CLARIFICATION"
    assert "CLARIFICATION_REQUIRED" in o["reason_codes"]


# --- approval precondition (section 17) ------------------------------------
def test_clarapp_none_class_no_approval_required():
    ap = k.clean()["approval"]
    assert ap["approval_required"] is False
    assert ap["approval_valid"] is True
    assert ap["approval_class"] == "NONE"


def test_clarapp_standard_needs_approval():
    o = _reply()
    assert o["disposition"] == "NEEDS_APPROVAL"
    assert o["resulting_state"] == "NEEDS_APPROVAL"
    assert o["approval"]["approval_class"] == "STANDARD"
    assert "APPROVAL_REQUIRED" in o["reason_codes"]


def test_clarapp_dual_control_single_approver_rejected():
    o = k.evaluate(work_type="compliance_escalation",
                   canonical_parameters={"target": "case:E-1"},
                   approval_record={"action": "compliance_escalation",
                                    "targets": ["case:E-1"],
                                    "scope": ["case:E-1"],
                                    "approver_count": 1})
    assert o["disposition"] == "NEEDS_APPROVAL"
    assert o["approval"]["approval_class"] == "DUAL_CONTROL"
    assert "APPROVAL_REQUIRED" in o["reason_codes"]


def test_clarapp_valid_dual_approval_admits():
    o = k.evaluate(work_type="compliance_escalation",
                   canonical_parameters={"target": "case:E-1"},
                   approval_record={"action": "compliance_escalation",
                                    "targets": ["case:E-1"],
                                    "scope": ["case:E-1"],
                                    "approver_count": 2})
    assert o["approval"]["approval_valid"] is True
    assert o["disposition"] == "ADMIT_READY"
    assert "ADMIT_READY" in o["reason_codes"]


def test_clarapp_wrong_action_mismatch():
    o = _reply(approval_record={"action": "WRONG_ACTION",
                                "targets": ["case:E-1"],
                                "scope": ["case:E-1"]})
    assert o["disposition"] == "NEEDS_APPROVAL"
    assert "APPROVAL_ACTION_MISMATCH" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False


def test_clarapp_wrong_target_mismatch():
    o = _reply(approval_record={"action": "customer_reply_draft",
                                "targets": ["case:OTHER"],
                                "scope": ["case:E-1", "case:OTHER"]})
    assert "APPROVAL_TARGET_MISMATCH" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False


def test_clarapp_narrow_scope_exceeded():
    o = _reply(approval_record={"action": "customer_reply_draft",
                                "targets": ["case:E-1"],
                                "scope": ["case:ONLY_THIS"]})
    assert "APPROVAL_SCOPE_EXCEEDED" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False


def test_clarapp_expired_approval():
    o = _reply(approval_record={"action": "customer_reply_draft",
                                "targets": ["case:E-1"],
                                "scope": ["case:E-1"], "expired": True})
    assert "APPROVAL_EXPIRED" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False


def test_clarapp_revoked_approval():
    o = _reply(approval_record={"action": "customer_reply_draft",
                                "targets": ["case:E-1"],
                                "scope": ["case:E-1"], "revoked": True})
    assert "APPROVAL_REVOKED" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False


def test_clarapp_natural_language_not_an_approval():
    o = _reply(approval_record={"action": "customer_reply_draft",
                                "targets": ["case:E-1"],
                                "scope": ["case:E-1"],
                                "natural_language_only": True})
    assert "APPROVAL_NOT_BOUND" in o["reason_codes"]
    assert o["approval"]["approval_valid"] is False
    assert o["disposition"] == "NEEDS_APPROVAL"


# --- API layer -------------------------------------------------------------
def test_clarapp_api_request_clarification(gate):
    wid, _ = gate.admitted_work()
    r = gate.wki(wid, "/request-clarification", method="POST")
    assert r.status_code == 200
    j = r.json()
    assert j["llm_supplied_values"] is False
    assert "clarification_plan" in j


def test_clarapp_api_respond_clarification(gate):
    wid, _ = gate.admitted_work()
    r = gate.wki(wid, "/respond-clarification", method="POST",
                answers={"message_intent": "reply"})
    assert r.status_code == 200
    assert r.json()["recorded"] is True


def test_clarapp_api_bind_approval(gate):
    wid, _ = gate.admitted_work()
    r = gate.wki(wid, "/bind-approval", method="POST",
                refs=["approval:signed:1"])
    assert r.status_code == 200
    assert r.json()["approval_bound"] is True
