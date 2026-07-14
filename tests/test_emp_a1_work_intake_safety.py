"""EMP-A1 v1: deterministic safety kernel — intake validation, source gating,
principal binding, secret/cross-tenant firewall, unregistered/target rejection.
The safety kernel is authoritative (no LLM/model) and fails closed.
"""
from tests import _emp_a1_kernel as k


def _denied(over, disposition, code):
    o = k.evaluate(**over)
    assert o["disposition"] == disposition
    assert code in o["reason_codes"]
    assert o["safety_denied"] is True
    # No external effect even on a denial.
    assert o["run_created"] is False and o["outbox_released"] is False
    return o


def test_disabled_source_rejected():
    _denied({"source_type": "SLACK"}, "REJECTED", "SOURCE_DISABLED")


def test_unknown_source_rejected():
    _denied({"source_type": "NOPE"}, "REJECTED", "SOURCE_SCHEMA_INVALID")


def test_missing_schema_version_rejected():
    _denied({"source_schema_version": None}, "REJECTED",
            "SOURCE_SCHEMA_INVALID")


def test_unbound_principal_rejected():
    _denied({"source_principal_id": None, "authenticated_principal_id": None},
            "REJECTED", "PRINCIPAL_NOT_BOUND")


def test_inactive_principal_rejected():
    _denied({"principal_active": False}, "REJECTED", "PRINCIPAL_INACTIVE")


def test_secret_material_quarantined():
    _denied({"raw_payload": {"api_key": "sk-abc"}}, "QUARANTINED",
            "SECRET_MATERIAL_DETECTED")


def test_cross_tenant_target_quarantined():
    _denied({"requested_target_refs": ["case:X:OTHER_TENANT"]}, "QUARANTINED",
            "CROSS_TENANT_REFERENCE")


def test_cross_tenant_request_quarantined():
    _denied({"tenant_id": "OTHER"}, "QUARANTINED", "CROSS_TENANT_REFERENCE")


def test_missing_idempotency_key_rejected():
    _denied({"idempotency_key": None}, "REJECTED", "IDEMPOTENCY_KEY_INVALID")


def test_unregistered_work_type_rejected():
    _denied({"work_type": "nope"}, "REJECTED", "INTENT_WORK_TYPE_UNREGISTERED")


def test_invalid_target_type_rejected():
    _denied({"requested_target_refs": ["banana:1"],
             "canonical_parameters": {"target": "banana:1"}}, "REJECTED",
            "TARGET_REFERENCE_INVALID")


def test_missing_field_needs_clarification():
    o = k.evaluate(work_type="customer_reply_draft",
                   canonical_parameters={"target": "case:E-1"})
    assert o["disposition"] == "NEEDS_CLARIFICATION"
    assert "CLARIFICATION_REQUIRED" in o["reason_codes"]


def test_intake_valid_on_clean():
    v = k.clean()["validation"]
    assert v["intake_valid"] is True
    assert v["no_secret_material"] is True
    assert v["principal_bound"] is True


# --- API layer -------------------------------------------------------------
def test_api_disabled_source_rejected(gate):
    o = gate.submit_work(source_type="SLACK").json()
    assert o["disposition"] == "REJECTED"


def test_api_secret_quarantined(gate):
    o = gate.submit_work(raw_payload={"password": "hunter2"}).json()
    assert o["disposition"] == "QUARANTINED"
    assert o["work_item"]["work_item_state"] == "QUARANTINED"
