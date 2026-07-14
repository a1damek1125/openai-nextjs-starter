"""CORE-A2 — canonical task contract hash: deterministic, excludes itself,
changes on authority / scope / purpose / subject / risk / approval / snapshot
changes; stable under UI-only label changes (labels are part of the contract
intentionally, so they are included and deterministic)."""
import pytest

from finalis.ai_employee import tasks as T


def _contract(**over):
    base = dict(
        tenant_id="t1", requester_user_id="u1", assigned_ai_employee_id="ai1",
        capability_snapshot_hash="snap-abc", task_type="case_summary",
        segment="casework", subject_type="case", subject_id="c1",
        task_purpose="p", purpose_category="CASEWORK",
        allowed_data_scopes=["case_metadata"],
        forbidden_data_scopes=list(T.ALWAYS_FORBIDDEN_DATA_SCOPES),
        allowed_output_types=["draft_summary"],
        forbidden_side_effects=["execute_payment"],
        authority_decision="ALLOWED_DRAFT_ONLY", authority_hard_fail=False,
        requires_human_approval=False, requires_consent_check=False,
        requires_evidence_check=False, requires_tool_broker=False,
        requires_run_ledger=True, risk_level="LOW", risk_reason="default",
        expires_at=None, stale_after=None, clarification_required=False,
        clarification_questions=[])
    base.update(over)
    return T.build_contract(**base)


def _h(**over):
    return T.contract_hash(_contract(**over))


def test_same_contract_same_hash():
    assert _h() == _h()


def test_key_order_independent():
    import json
    c = _contract()
    assert T.contract_hash(json.loads(json.dumps(c))) == T.contract_hash(c)


def test_hash_excludes_itself():
    c = _contract()
    assert "canonical_task_contract_hash" not in c


@pytest.mark.parametrize("field,value", [
    ("authority_decision", "APPROVAL_REQUIRED"),
    ("allowed_data_scopes", ["case_metadata", "payment_status_summary"]),
    ("forbidden_data_scopes", ["secrets"]),
    ("requires_human_approval", True),
    ("risk_level", "CRITICAL"),
    ("capability_snapshot_hash", "snap-xyz"),
    ("subject_id", "c2"),
    ("task_purpose", "different"),
])
def test_semantic_change_changes_hash(field, value):
    assert _h(**{field: value}) != _h()
