"""Hazard Registry + traceability closure (SP0005 §10.2, D-0005-41, §11.9,
INV-0005-14).

A HAZARD is a system state that can lead to a LOSS (distinct from threat/loss/
risk, INV-0005-02). A critical hazard is closure-complete only when it maps to a
loss AND a safety constraint AND (a control OR an explicit hard block), with
test/evidence/claim linkage (§11.9). An uncontrolled critical hazard is a hard
failure (AC-0005-019, INV-0005-14).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, CRITICALITY, CRITICAL_LEVELS, HAZARD_STATUS,
                    INVALID_SAFETY_SCHEMA, UNCONTROLLED_CRITICAL_HAZARD,
                    ASSURANCE_COVERAGE_GAP)


def hazard_index(reg: dict) -> dict[str, dict]:
    return {h["hazard_id"]: h for h in reg.get("hazards", [])}


def validate_hazards(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for h in reg.get("hazards", []):
        hid = h.get("hazard_id")
        if not hid:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P0, "-",
                               "hazard missing hazard_id", {}))
            continue
        if hid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P0, hid,
                               "duplicate hazard_id", {}))
        seen.add(hid)
        if h.get("criticality") not in CRITICALITY:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, hid,
                               f"invalid criticality {h.get('criticality')!r}", {}))
        st = h.get("status", "ACTIVE")
        if st not in HAZARD_STATUS:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, hid,
                               f"invalid hazard status {st!r}", {}))
    return out


def traceability(program: dict) -> list[Finding]:
    """Every ACTIVE critical hazard must close: loss + constraint + (control OR
    hard block) + test/evidence/claim linkage. Otherwise UNCONTROLLED (P0) or
    ASSURANCE_COVERAGE_GAP (P1)."""
    out: list[Finding] = []
    losses = {l["loss_id"] for l in program.get("losses", [])}
    constraints_by_hazard: dict[str, list[str]] = {}
    for c in program.get("constraints", []):
        for hz in c.get("hazard_refs", []):
            constraints_by_hazard.setdefault(hz, []).append(c["constraint_id"])
    controls_by_hazard: dict[str, list[str]] = {}
    for c in program.get("controls", []):
        for hz in c.get("hazard_refs", []):
            controls_by_hazard.setdefault(hz, []).append(c["control_id"])
    claims_by_hazard: dict[str, list[str]] = {}
    for cl in program.get("claims", []):
        for hz in cl.get("hazard_refs", []):
            claims_by_hazard.setdefault(hz, []).append(cl["claim_id"])

    for h in program.get("hazards", []):
        if h.get("status", "ACTIVE") != "ACTIVE":
            continue
        if h.get("criticality") not in CRITICAL_LEVELS:
            continue
        hid = h["hazard_id"]
        # loss linkage
        if not (set(h.get("loss_refs", [])) & losses):
            out.append(Finding(ASSURANCE_COVERAGE_GAP, P1, hid,
                               "critical hazard maps to no known loss "
                               "(AC-0005-016)", {}))
        # constraint linkage
        if hid not in constraints_by_hazard:
            out.append(Finding(ASSURANCE_COVERAGE_GAP, P1, hid,
                               "critical hazard has no safety constraint "
                               "(AC-0005-017)", {}))
        # control OR explicit hard block. A hard block must be an explicit
        # boolean True — a truthy string ("false"/"no"/"TODO") must NEVER count
        # as a real block (SWARM-N E1; INV-0005-14, "UNKNOWN IS NOT SAFE").
        has_control = hid in controls_by_hazard
        hard_block = h.get("hard_block") is True
        if not has_control and not hard_block:
            out.append(Finding(UNCONTROLLED_CRITICAL_HAZARD, P0, hid,
                               "critical hazard has neither a control nor an "
                               "explicit hard block (AC-0005-018/019, "
                               "INV-0005-14)", {}))
        # test/evidence/claim linkage
        if hid not in claims_by_hazard and not hard_block:
            out.append(Finding(ASSURANCE_COVERAGE_GAP, P1, hid,
                               "critical hazard has no assurance claim linkage "
                               "(AC-0005-092)", {}))
    return out
