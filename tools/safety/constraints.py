"""Safety Constraint Registry (SP0005 §10, D-0005-06).

A safety constraint is what must hold to keep a hazard from becoming a loss. Each
constraint links to hazard(s) it addresses; the closure check (hazards.py) ensures
every critical hazard has one.
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_SAFETY_SCHEMA


def validate_constraints(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    hazards = {h["hazard_id"] for h in reg.get("hazards", [])}
    seen: set[str] = set()
    for c in reg.get("constraints", []):
        cid = c.get("constraint_id")
        if not cid:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, "-",
                               "constraint missing constraint_id", {}))
            continue
        if cid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                               "duplicate constraint_id", {}))
        seen.add(cid)
        for hz in c.get("hazard_refs", []):
            if hz not in hazards:
                out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                                   f"constraint references unknown hazard "
                                   f"{hz!r}", {}))
    return out
