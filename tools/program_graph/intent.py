"""Program Change Intent (SP0003 D-0003-25 §13.6, AC-0003-88).

A program-graph change (add/remove node, add/activate dependency, change gate,
edit scenario) is expressed as an auditable intent that moves through
PROPOSED -> VALIDATING -> IMPACT_ANALYZED -> REVIEWED -> ACCEPTED -> ACTIVE. This
validates the intent's shape; admission of the change still runs the full program
validator + impact analysis.
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_PROGRAM_SCHEMA

INTENT_STATES = ["PROPOSED", "VALIDATING", "IMPACT_ANALYZED", "REVIEWED",
                 "ACCEPTED", "ACTIVE"]
CHANGE_KINDS = {"ADD_NODE", "REMOVE_NODE", "ADD_DEPENDENCY",
                "ACTIVATE_DEPENDENCY", "DEPRECATE_DEPENDENCY", "CHANGE_GATE",
                "EDIT_SCENARIO", "UPDATE_DURATION_MODEL", "ADD_REWORK_EDGE"}


def validate_intent(intent: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = intent.get("change_id", "-")
    if not intent.get("change_id"):
        out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, "-",
                           "change intent missing change_id", {}))
    if intent.get("change_kind") not in CHANGE_KINDS:
        out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, cid,
                           f"invalid change_kind {intent.get('change_kind')!r}",
                           {}))
    state = intent.get("state", "PROPOSED")
    if state not in INTENT_STATES:
        out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, cid,
                           f"invalid intent state {state!r}", {}))
    if not intent.get("target"):
        out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, cid,
                           "change intent missing target", {}))
    return out
