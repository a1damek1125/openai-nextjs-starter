"""Canonical Loss Taxonomy (SP0005 §10.1, D-0005-04/05).

A LOSS is what we ultimately prevent (harm to a subject) — kept strictly distinct
from THREAT, HAZARD, RISK and VULNERABILITY (INV-0005-02). Loss identities are
immutable (D-0005-05); display labels may evolve.
"""
from __future__ import annotations

from .model import Finding, P0, P1, LOSS_CATEGORIES, INVALID_SAFETY_SCHEMA


def loss_index(reg: dict) -> dict[str, dict]:
    return {l["loss_id"]: l for l in reg.get("losses", [])}


def validate_losses(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for l in reg.get("losses", []):
        lid = l.get("loss_id")
        if not lid:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P0, "-",
                               "loss missing loss_id", {}))
            continue
        if lid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P0, lid,
                               "duplicate loss_id", {}))
        seen.add(lid)
        if l.get("category") not in LOSS_CATEGORIES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, lid,
                               f"invalid loss category {l.get('category')!r}", {}))
    return out
