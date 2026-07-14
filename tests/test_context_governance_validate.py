"""TOOL-B10 validate: the kernel invariant self-check must pass clean."""
from tools.context_governance import validate as v


def test_self_check_passes_clean():
    assert v.self_check() == []


def test_validate_reports_ok():
    res = v.validate()
    assert res["ok"] is True
    assert res["violations"] == []
    assert res["checked"] == len(v.INVARIANTS)


def test_invariants_enumerated():
    assert any("informs, never authorizes" in i for i in v.INVARIANTS)
    assert any("generator cannot self-certify" in i for i in v.INVARIANTS)
    assert any("non-compensatory" in i for i in v.INVARIANTS)
