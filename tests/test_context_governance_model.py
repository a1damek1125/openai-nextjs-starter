"""TOOL-B10 model: four-valued lattice, taint join, Finding/Report, reason codes."""
import pytest

from tools.context_governance import model as m


def test_claim_state_four_valued():
    assert m.claim_state(True, False) == m.SUPPORTED_ONLY
    assert m.claim_state(False, True) == m.REFUTED_ONLY
    assert m.claim_state(True, True) == m.BOTH
    assert m.claim_state(False, False) == m.NEITHER


def test_truthy_non_true_is_not_support():
    # a truthy string / int must NOT be read as support (strict `is True`)
    assert m.claim_state("yes", False) == m.NEITHER
    assert m.claim_state(1, 0) == m.NEITHER


def test_only_supported_only_closes_critical():
    assert m.closes_critical(m.SUPPORTED_ONLY) is True
    assert m.closes_critical(m.BOTH) is False
    assert m.closes_critical(m.NEITHER) is False
    assert m.closes_critical(m.REFUTED_ONLY) is False


def test_both_is_not_true_neither_is_not_false():
    assert m.BOTH != m.SUPPORTED_ONLY
    assert m.NEITHER != m.REFUTED_ONLY


def test_taint_join_takes_more_severe():
    assert m.taint_join("EXTERNAL", "QUARANTINED") == "QUARANTINED"
    assert m.taint_join("QUARANTINED", "EXTERNAL") == "QUARANTINED"
    assert m.taint_join("UNTAINTED", "TOOL_OUTPUT") == "TOOL_OUTPUT"


def test_taint_join_is_commutative_over_lattice():
    for a in m.TAINT_LEVELS:
        for b in m.TAINT_LEVELS:
            assert m.taint_join(a, b) == m.taint_join(b, a)


def test_finding_rejects_unknown_reason_code():
    with pytest.raises(ValueError):
        m.Finding("NOT_A_REAL_CODE", m.P0, "s", "msg")


def test_finding_rejects_bad_severity():
    with pytest.raises(ValueError):
        m.Finding("ENTITLEMENT_MISSING", "PX", "s", "msg")


def test_report_valid_iff_no_p0_p1():
    f0 = m.Finding("ENTITLEMENT_MISSING", m.P0, "s", "m")
    f1 = m.Finding("CLAIM_BOTH", m.P1, "s", "m")
    f2 = m.Finding("CONFORMAL_GUARANTEE_DISABLED", m.P2, "s", "m")
    assert m.report([]).valid is True
    assert m.report([f2]).valid is True
    assert m.report([f1]).valid is False
    assert m.report([f0]).valid is False


def test_report_counts_and_as_dict():
    r = m.report([m.Finding("CLAIM_BOTH", m.P1, "s", "m")])
    d = r.as_dict()
    assert d["counts"]["P1"] == 1 and d["valid"] is False


def test_reason_codes_are_frozen_and_populated():
    assert isinstance(m.REASON_CODES, frozenset)
    assert "AUTHORITY_INFERENCE_REJECTED" in m.REASON_CODES
    assert "GENERATOR_SELF_CERTIFICATION" in m.REASON_CODES
