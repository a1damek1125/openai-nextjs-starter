"""TOOL-B4 pre-action reference monitor: signal->status mapping tests.

Locks the deterministic mapping from each adverse signal to its pre-action
decision status, and the closed universe of decision statuses. Executes nothing.
"""
from finalis.ai_employee import tool_guardrails as g


def test_security_stop_signals_map():
    assert g._SIGNAL_TO_STATUS["TAMPERED"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["QUARANTINED"] == "PREACTION_QUARANTINED"
    assert g._SIGNAL_TO_STATUS["REVOKED"] == "PREACTION_REVOKED"
    assert g._SIGNAL_TO_STATUS["CROSS_TENANT"] == "PREACTION_BLOCKED"


def test_source_gate_signals_map():
    assert g._SIGNAL_TO_STATUS["TOOL_B1_BLOCKED"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["TOOL_B2_BLOCKED"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["TOOL_B3_BLOCKED"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["CONTRACT_STALE"] == "PREACTION_STALE"


def test_drift_and_breaker_signals_map():
    assert g._SIGNAL_TO_STATUS["CAPABILITY_DRIFT_DETECTED"] == \
        "PREACTION_CAPABILITY_DRIFT_DETECTED"
    assert g._SIGNAL_TO_STATUS["CIRCUIT_BREAKER_ACTIVE"] == \
        "PREACTION_CIRCUIT_BREAKER_ACTIVE"


def test_remediation_signals_map():
    # "Needs X" remediations, not hard stops.
    assert g._SIGNAL_TO_STATUS["STATE_WITNESS_STALE"] == \
        "PREACTION_NEEDS_STATE_REFRESH"
    assert g._SIGNAL_TO_STATUS["PAYLOAD_SCOPE_MISMATCH"] == \
        "PREACTION_NEEDS_REDUCED_SCOPE"
    assert g._SIGNAL_TO_STATUS["NONDELEGABLE_DECISION"] == \
        "PREACTION_NEEDS_HUMAN_APPROVAL"
    assert g._SIGNAL_TO_STATUS["APPROVAL_MISSING"] == \
        "PREACTION_NEEDS_HUMAN_APPROVAL"
    assert g._SIGNAL_TO_STATUS["CONSENT_MISSING"] == "PREACTION_NEEDS_CONSENT"


def test_denied_and_blocked_structural_signals_map():
    assert g._SIGNAL_TO_STATUS["INTENT_MISMATCH"] == "PREACTION_DENIED"
    assert g._SIGNAL_TO_STATUS["PAYLOAD_SCHEMA_MISMATCH"] == "PREACTION_DENIED"
    assert g._SIGNAL_TO_STATUS["EFFECT_FORBIDDEN"] == "PREACTION_BLOCKED"
    # Token / provider / execution attempts are all hard blocks.
    assert g._SIGNAL_TO_STATUS["TOKEN_PASSTHROUGH"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["PROVIDER_CALL_ATTEMPT"] == "PREACTION_BLOCKED"
    assert g._SIGNAL_TO_STATUS["EXECUTION_ATTEMPT"] == "PREACTION_BLOCKED"


def test_all_mapped_statuses_are_declared_decision_statuses():
    for sig, status in g._SIGNAL_TO_STATUS.items():
        assert status in g.DECISION_STATUSES, (sig, status)


def test_positive_statuses_are_exactly_the_two_non_adverse():
    assert g.POSITIVE_STATUSES == {
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY", "PREACTION_DRAFT_ONLY"}
    # Both positive statuses are members of the closed decision-status universe.
    assert g.POSITIVE_STATUSES <= g.DECISION_STATUSES
    # The two positive base signals map to exactly those two statuses.
    assert g._SIGNAL_TO_STATUS["ALLOWED_FOR_FUTURE_BROKER_ONLY"] == \
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert g._SIGNAL_TO_STATUS["DRAFT_ONLY"] == "PREACTION_DRAFT_ONLY"
