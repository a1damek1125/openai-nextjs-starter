"""Architecture Change Intent Contract (SP0001 D-0001-03/04, §10.3).

Change intent explains intended evolution. It is NOT authority: it cannot waive a
hard invariant (D-0001-04, INV-0001-06). This module validates an intent document
and classifies observed deltas against it (declared vs undeclared drift).
"""
from __future__ import annotations

from typing import Any

CHANGE_TYPES = {"INTERNAL_IMPLEMENTATION", "CAPABILITY_EXTENSION",
                "NEW_CAPABILITY", "DECLARED_REPLACEMENT", "ARCHITECTURE_MIGRATION"}

# An intent that "declares" one of these is trying to waive a hard invariant.
FORBIDDEN_INTENT_MARKERS = {
    "bypass_tenant_isolation", "open_effect_gate", "mutate_historical_migration",
    "model_as_authority", "external_content_as_authority", "second_source_of_truth",
}

REQUIRED_FIELDS = ["change_id", "sp_id", "base_commit", "target_capabilities",
                   "change_type"]


def validate_intent(intent: dict) -> list[str]:
    errors: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in intent:
            errors.append(f"missing required field: {f}")
    ct = intent.get("change_type")
    if ct is not None and ct not in CHANGE_TYPES:
        errors.append(f"invalid change_type: {ct}")
    if not isinstance(intent.get("target_capabilities", []), list):
        errors.append("target_capabilities must be a list")
    # D-0001-04: intent can never authorize a hard-invariant bypass.
    declared = set(intent.get("expected_effect_boundary_changes", [])) \
        | set(intent.get("non_goals", [])) | set(intent.get("waives", []))
    for marker in FORBIDDEN_INTENT_MARKERS:
        if marker in intent.get("waives", []):
            errors.append(f"intent cannot waive hard invariant: {marker}")
    return errors


def classify_delta(intent: dict | None, delta: dict) -> dict[str, Any]:
    """Classify architecture delta as declared or UNDECLARED_ARCHITECTURE_DRIFT."""
    intent = intent or {}
    target = set(intent.get("target_capabilities", []))
    new_caps = set(intent.get("new_capabilities", []))
    declared_routes = set(intent.get("expected_route_changes", []))
    declared_tables = set(intent.get("expected_data_changes", []))
    declared_deps = set(tuple(x) if isinstance(x, list) else x
                        for x in intent.get("expected_dependency_changes", []))

    undeclared: list[dict[str, Any]] = []

    for cap in delta.get("new_capabilities", []):
        if cap not in new_caps:
            undeclared.append({"type": "UNDECLARED_NEW_CAPABILITY", "id": cap})
    for ns in delta.get("new_routes", []):
        owner = delta.get("route_owner", {}).get(ns)
        if ns not in declared_routes and owner not in target:
            undeclared.append({"type": "UNDECLARED_ROUTE", "id": ns})
    for tb in delta.get("new_tables", []):
        if tb not in declared_tables:
            undeclared.append({"type": "UNDECLARED_TABLE", "id": tb})
    for e in delta.get("new_capability_edges", []):
        te = tuple(e)
        if te not in declared_deps and e[0] not in target:
            undeclared.append({"type": "UNDECLARED_DEPENDENCY", "edge": list(e)})

    return {"declared": bool(intent),
            "undeclared_drift": sorted(undeclared, key=lambda d: str(d)),
            "is_clean": len(undeclared) == 0}
