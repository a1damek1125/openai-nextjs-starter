"""Completion Evidence Graph — completion is EVIDENCE-DERIVED (SP0003 D-0003-15,
§10, INV-0003-14).

A node is not COMPLETE because a status field says so. COMPLETE requires
completion evidence: a final commit, an acceptance matrix, P0/P1=0, test
evidence, and a mission report / required proof envelopes. A node declared
COMPLETE without sufficient evidence is COMPLETION_EVIDENCE_MISSING (AC-0003-32/33)
and is NOT admitted to the satisfying-completion set that downstream hard
prerequisites read.
"""
from __future__ import annotations

from .model import (Finding, P0, P1, COMPLETION_EVIDENCE_MISSING,
                    SATISFYING_STATES)

# minimum evidence kinds an SP-type node must cite to be genuinely COMPLETE
REQUIRED_EVIDENCE_KINDS = {"final_commit", "acceptance_matrix", "test_evidence",
                           "p0p1_status"}
# lighter node types (docs / milestones) need at least one evidence ref
LIGHT_NODE_TYPES = {"DOC", "MILESTONE", "GATE_NODE"}


def evidence_index(program: dict) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for ev in program.get("completion_evidence", []):
        idx.setdefault(ev.get("node_id"), []).append(ev)
    return idx


def has_sufficient_evidence(node: dict, evidences: list[dict]) -> bool:
    kinds = {e.get("kind") for e in evidences}
    if node.get("node_type") in LIGHT_NODE_TYPES:
        return len(evidences) >= 1
    return REQUIRED_EVIDENCE_KINDS.issubset(kinds)


def validate_completion_evidence(program: dict) -> list[Finding]:
    """Any node whose status is COMPLETE must have sufficient completion
    evidence (D-0003-15). Fake COMPLETE without evidence -> P0."""
    out: list[Finding] = []
    idx = evidence_index(program)
    for n in program.get("nodes", []):
        if n.get("status") in SATISFYING_STATES:
            evs = idx.get(n["node_id"], [])
            if not has_sufficient_evidence(n, evs):
                have = sorted({e.get("kind") for e in evs})
                out.append(Finding(COMPLETION_EVIDENCE_MISSING, P0,
                                   n["node_id"],
                                   "node is COMPLETE but lacks sufficient "
                                   f"completion evidence (have={have})",
                                   {"have": have}))
    return out


def evidence_derived_complete_set(program: dict) -> set[str]:
    """The set of nodes that are LEGITIMATELY complete: status COMPLETE AND
    sufficient evidence. This — not the raw status field — is what hard
    prerequisites read (D-0003-15/16)."""
    idx = evidence_index(program)
    out: set[str] = set()
    for n in program.get("nodes", []):
        if n.get("status") in SATISFYING_STATES and \
                has_sufficient_evidence(n, idx.get(n["node_id"], [])):
            out.add(n["node_id"])
    return out


def evidence_coverage(program: dict) -> dict:
    idx = evidence_index(program)
    total = 0
    covered = 0
    for n in program.get("nodes", []):
        if n.get("status") in SATISFYING_STATES:
            total += 1
            if has_sufficient_evidence(n, idx.get(n["node_id"], [])):
                covered += 1
    return {"complete_nodes": total, "evidence_backed": covered,
            "coverage": round(covered / total, 4) if total else 1.0}
