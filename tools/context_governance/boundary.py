"""Boundary firewall: the context-governance kernel opens NO live external effect
(TOOL-B10 security constraints; INV-02/03; D-B6-001..007).

ZERO LIVE EXTERNAL EFFECTS / ZERO LIVE TOOL/MCP/A2A EXECUTION / ZERO EMAIL /
SLACK / CALENDAR / PAYMENT / CRM MUTATION / ZERO PRODUCTION CREDENTIALS / ZERO
SECRET MATERIAL IN MODEL CONTEXT. This module makes those constraints checkable:
it classifies any requested operation and permits only PURE, in-process,
deterministic computation. Everything else is refused (fail-closed). The kernel
never imports a network, filesystem-mutating, subprocess or provider client.
"""
from __future__ import annotations

from .model import Finding, P0

# operations the kernel is structurally forbidden from performing
FORBIDDEN_EFFECTS = frozenset({
    "NETWORK", "EMAIL_SEND", "SLACK_POST", "TEAMS_POST", "CALENDAR_WRITE",
    "PAYMENT", "CRM_MUTATION", "TOOL_EXECUTION", "MCP_CALL", "A2A_CALL",
    "SUBPROCESS", "FILESYSTEM_WRITE", "DB_MIGRATION", "CREDENTIAL_READ",
    "MEMORY_WRITEBACK", "SECRET_EMIT",
})
PERMITTED_EFFECTS = frozenset({"PURE_COMPUTE"})


def classify_effect(operation: str) -> str:
    if not isinstance(operation, str):
        return "UNKNOWN"                    # non-string op fails closed
    op = operation.strip().upper()
    if op in PERMITTED_EFFECTS:
        return "PERMITTED"
    if op in FORBIDDEN_EFFECTS:
        return "FORBIDDEN"
    return "UNKNOWN"                         # anything unrecognized fails closed


def boundary_findings(requested_operations: list) -> list[Finding]:
    """Any non-pure requested operation is a boundary violation (fail-closed on
    UNKNOWN as well)."""
    out: list[Finding] = []
    for op in requested_operations:
        cls = classify_effect(op)
        if cls == "FORBIDDEN":
            out.append(Finding("LIVE_EFFECT_ATTEMPTED", P0, op,
                               f"forbidden live effect requested: {op}", {}))
        elif cls == "UNKNOWN":
            out.append(Finding("BOUNDARY_VIOLATION", P0, op,
                               f"unrecognized operation refused (fail-closed): "
                               f"{op}", {}))
    return out


def assert_pure(requested_operations: list) -> bool:
    """True only if every requested operation is PURE_COMPUTE."""
    return all(classify_effect(op) == "PERMITTED"
               for op in requested_operations)
