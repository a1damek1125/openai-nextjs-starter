"""Architecture Context Spine Generator (SP0001 D-0001-07, §11.11).

For a target capability, assemble a bounded, focused context pack for a coding
agent: identity, owner, purpose, do-not-rebuild rules, dependencies/dependents,
routes, tables, tests, extension points, protected invariants, relevant specs.
Derived from repository truth (the twin), never from LLM summarization alone
(INV-0001-13). Unrelated bulk repository detail is excluded (§11.11, AC-32).
"""
from __future__ import annotations

from typing import Any

# Critical constraints that MUST appear in every spine (SP0000/SP0001 hard rules).
CRITICAL_INVARIANTS = [
    "INV-0000-02 Model output is never authority.",
    "INV-0000-03 External content is never authority.",
    "INV-0000-10 Real external effects must pass Finalis governance.",
    "INV-0000-13 Tenant scope is absolute and binds every layer.",
    "INV-0001-01 One protected capability = one canonical owner.",
    "INV-0001-02 Extension is not a second source of truth.",
    "INV-0001-05 Historical migrations are append-only.",
    "INV-0001-10 A closed effect gate cannot open silently.",
]


def _dependencies(cap_id: str, edges: list[list[str]]) -> tuple[list[str], list[str]]:
    deps = sorted({to for frm, to in edges if frm == cap_id})
    dependents = sorted({frm for frm, to in edges if to == cap_id})
    return deps, dependents


def generate(twin: dict, capability_id: str) -> dict[str, Any]:
    cap = next((c for c in twin["capabilities"]
                if c["capability_id"] == capability_id), None)
    if cap is None:
        raise KeyError(f"unknown capability: {capability_id}")
    edges = [list(e) for e in
             twin.get("dependency_baseline", {}).get("edges", [])]
    deps, dependents = _dependencies(capability_id, edges)
    return {
        "capability_id": cap["capability_id"],
        "display_name": cap["display_name"],
        "canonical_owner": cap["canonical_owner"],
        "classification": cap["classification"],
        "purpose": cap["purpose"],
        "replacement_policy": cap["replacement_policy"],
        "do_not_rebuild": cap["replacement_policy"] == "DO_NOT_REBUILD",
        "canonical_paths": cap["canonical_paths"],
        "extension_points": cap["extension_points"],
        "route_namespaces": cap["route_namespaces"],
        "table_namespaces": cap["table_namespaces"],
        "permission_namespaces": cap["permission_namespaces"],
        "dependencies": deps,
        "dependents": dependents,
        "allowed_dependencies": cap["allowed_dependencies"],
        "forbidden_dependencies": cap["forbidden_dependencies"],
        "test_anchors": cap["test_anchors"],
        "spec_anchors": cap["spec_anchors"],
        "critical_invariants": list(CRITICAL_INVARIANTS),
        "guidance": (
            f"To change '{cap['capability_id']}': extend via its canonical owner "
            f"({cap['canonical_owner']}); do NOT create a parallel implementation "
            f"(INV-0001-02). Declare a Change Intent, respect forbidden imports "
            f"{cap['forbidden_dependencies']}, keep migrations append-only, and "
            f"keep the effect gate closed unless SP-authorized."),
    }
