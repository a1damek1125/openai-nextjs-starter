"""Twin manifest validation tests (SP0001 §20.1, AC-05/07/08/19)."""
from __future__ import annotations

from tools.architecture.manifest import validate_twin
from tests._arch_helpers import cap, mini_twin


def test_valid_twin_passes():
    twin = mini_twin([cap("crm"), cap("evidence")])
    assert validate_twin(twin) == []


def test_missing_required_twin_field_fails():
    twin = mini_twin([cap("crm")])
    del twin["effect_gates"]
    assert any("effect_gates" in e for e in validate_twin(twin))


def test_duplicate_capability_id_fails():
    twin = mini_twin([cap("crm"), cap("crm")])
    assert any("duplicate capability id" in e for e in validate_twin(twin))


def test_missing_owner_fails():
    twin = mini_twin([cap("crm")])
    twin["capabilities"][0]["canonical_owner"] = ""
    assert any("no canonical owner" in e for e in validate_twin(twin))


def test_path_traversal_rejected():
    c = cap("crm", paths=["../etc/passwd"])
    twin = mini_twin([c])
    assert any("path traversal" in e for e in validate_twin(twin))


def test_absolute_path_rejected():
    c = cap("crm", paths=["/abs/root"])
    twin = mini_twin([c])
    assert any("path traversal" in e for e in validate_twin(twin))


def test_route_namespace_double_declaration_fails():
    twin = mini_twin([cap("crm", routes=["/crm"]), cap("x", routes=["/crm"])])
    assert any("route namespace /crm" in e for e in validate_twin(twin))


def test_table_namespace_double_declaration_fails():
    twin = mini_twin([cap("crm", tables=["crm_"]), cap("x", tables=["crm_"])])
    assert any("table namespace crm_" in e for e in validate_twin(twin))


def test_real_declared_twin_validates():
    import json
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    twin = json.load(open(os.path.join(
        root, "docs/architecture/FINALIS_1000_ARCHITECTURE_TWIN.json")))
    assert validate_twin(twin) == []


def test_declared_and_observed_twins_are_separate():
    # the declared twin file is marked DECLARED; the observer never writes it
    import json
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    twin = json.load(open(os.path.join(
        root, "docs/architecture/FINALIS_1000_ARCHITECTURE_TWIN.json")))
    assert twin["twin_kind"] == "DECLARED"
