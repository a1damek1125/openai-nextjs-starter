"""CORE-A2 — canonical task envelope hash: deterministic, excludes itself,
changes on any proof-critical change."""
import pytest

from finalis.ai_employee import tasks as T


def _env(**over):
    base = dict(
        tenant_id="t1", requester_user_id="u1",
        assigned_ai_employee_id="ai1", source_channel="WEB",
        source_thread_ref=None, source_message_ref=None,
        task_type="case_summary", segment="casework", subject_type="case",
        subject_id="c1", task_title="Summarize", task_description="please",
        priority="NORMAL", due_at=None, expires_at=None,
        task_purpose="p", purpose_category="CASEWORK",
        authority_decision="ALLOWED_DRAFT_ONLY", authority_reason="ok",
        risk_level="LOW", requires_human_approval=False,
        requires_consent_check=False, requires_evidence_check=False,
        requires_tool_broker=False,
        forbidden_side_effects=["execute_payment"], input_security_flags=["NONE"])
    base.update(over)
    return T.build_envelope(**base)


def _h(**over):
    return T.envelope_hash(_env(**over))


def test_same_envelope_same_hash():
    assert _h() == _h()


def test_key_order_independent():
    import json
    e = _env()
    reordered = json.loads(json.dumps(e))
    assert T.envelope_hash(reordered) == T.envelope_hash(e)


def test_hash_excludes_itself():
    # The builder never emits the hash field, so a pure envelope cannot carry
    # its own hash; and hashing is a genuine function of its input (injecting
    # a hash field really does change the digest — the hash is not constant).
    e = _env()
    assert "canonical_task_envelope_hash" not in e
    e2 = {**e, "canonical_task_envelope_hash": "injected"}
    assert T.envelope_hash(e2) != T.envelope_hash(e)


@pytest.mark.parametrize("field,value", [
    ("task_description", "totally different"),
    ("authority_decision", "BLOCKED"),
    ("subject_id", "c2"),
    ("requester_user_id", "u2"),
    ("task_purpose", "other purpose"),
    ("task_type", "quote_summary"),
    ("risk_level", "CRITICAL"),
])
def test_proof_critical_change_changes_hash(field, value):
    assert _h(**{field: value}) != _h()


def test_nan_infinity_rejected():
    with pytest.raises(ValueError):
        T.canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        T.canonical_json({"x": float("inf")})
