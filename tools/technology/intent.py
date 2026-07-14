"""Technology Change Intent (SP0004 D-0004-73, §10, AC-0004-123).

A technology-significant change declares what changed (decision/provider/protocol/
contract), the affected capabilities/data/program SPs, and whether migration or
replay is required plus its exit impact. Admission still runs the full validator +
impact cone.
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_TDR

CHANGE_KINDS = {"DECISION_CHANGED", "PROVIDER_CHANGED", "PROTOCOL_CHANGED",
                "CONTRACT_CHANGED", "DEPENDENCY_ADDED", "DEPENDENCY_RETIRED"}


def validate_intent(intent: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = intent.get("change_id", "-")
    if not intent.get("change_id"):
        out.append(Finding(INVALID_TDR, P1, "-", "change intent missing change_id",
                           {}))
    if intent.get("change_kind") not in CHANGE_KINDS:
        out.append(Finding(INVALID_TDR, P1, cid,
                           f"invalid change_kind {intent.get('change_kind')!r}",
                           {}))
    if not intent.get("target"):
        out.append(Finding(INVALID_TDR, P1, cid, "change intent missing target",
                           {}))
    # a migration-requiring change must declare replay + exit impact
    if intent.get("migration_required") and "exit_impact" not in intent:
        out.append(Finding(INVALID_TDR, P1, cid,
                           "migration-requiring change must declare exit_impact",
                           {}))
    return out
