"""TOOL-B10 boundary: no live external effect; unknown operations fail closed."""
from tools.context_governance import boundary as b


def test_pure_compute_is_permitted():
    assert b.classify_effect("PURE_COMPUTE") == "PERMITTED"
    assert b.assert_pure(["PURE_COMPUTE"]) is True


def test_forbidden_effects_are_forbidden():
    for op in ("EMAIL_SEND", "SLACK_POST", "PAYMENT", "CRM_MUTATION",
               "TOOL_EXECUTION", "MCP_CALL", "A2A_CALL", "DB_MIGRATION",
               "MEMORY_WRITEBACK", "NETWORK", "SECRET_EMIT"):
        assert b.classify_effect(op) == "FORBIDDEN", op


def test_unknown_operation_fails_closed():
    assert b.classify_effect("SOMETHING_UNSEEN") == "UNKNOWN"


def test_boundary_findings_flag_forbidden_and_unknown():
    fs = b.boundary_findings(["EMAIL_SEND", "MYSTERY", "PURE_COMPUTE"])
    kinds = {f.kind for f in fs}
    assert "LIVE_EFFECT_ATTEMPTED" in kinds
    assert "BOUNDARY_VIOLATION" in kinds
    assert all(f.severity == "P0" for f in fs)


def test_assert_pure_false_for_any_nonpure():
    assert b.assert_pure(["PURE_COMPUTE", "EMAIL_SEND"]) is False
