"""LGGT Semantic Bridge (SP0002 D-0002-23, §20.12).

Binds a canonical concept to an LGGT predicate family under an explicit semantic
epoch + rule-pack version + typed argument contract + world assumption + source/
admission requirements. No raw free-text predicate ownership (INV-0002-15). Detects
predicate collisions: two concepts claiming the same predicate_family (P0). Does
NOT modify LGGT.
"""
from __future__ import annotations

from typing import Any

from .model import Finding, P0, P1, LGGT_MAPPING_COLLISION, SEMANTIC_EPOCH_MISMATCH

REQUIRED_FIELDS = ["concept_id", "semantic_epoch_id", "predicate_family",
                   "argument_types", "world_assumption", "rule_pack_version"]


def validate_mapping(mapping: dict) -> list[Finding]:
    out: list[Finding] = []
    for f in REQUIRED_FIELDS:
        if not mapping.get(f):
            out.append(Finding("LGGT_MAPPING_INCOMPLETE", P1,
                               mapping.get("concept_id", "-"),
                               f"LGGT mapping missing {f}", {"field": f}))
    if mapping.get("predicate_family") and not isinstance(
            mapping.get("argument_types"), list):
        out.append(Finding("LGGT_MAPPING_INCOMPLETE", P1,
                           mapping.get("concept_id", "-"),
                           "argument_types must be an explicit typed list", {}))
    return out


def detect_collisions(mappings: list[dict]) -> list[Finding]:
    """Two concepts mapping to the same predicate_family within the same epoch is
    a collision (P0)."""
    out: list[Finding] = []
    seen: dict[tuple, str] = {}
    for m in mappings:
        key = (m.get("predicate_family"), m.get("semantic_epoch_id"))
        cid = m.get("concept_id")
        if key[0] and key in seen and seen[key] != cid:
            out.append(Finding(LGGT_MAPPING_COLLISION, P0, cid,
                               f"predicate_family {key[0]} claimed by {seen[key]} "
                               f"and {cid} in epoch {key[1]}",
                               {"predicate_family": key[0], "concepts":
                                sorted([seen[key], cid])}))
        seen[key] = cid
    return out


def validate_epoch_binding(mappings: list[dict], active_epoch: str) -> list[Finding]:
    out: list[Finding] = []
    for m in mappings:
        if m.get("semantic_epoch_id") and m["semantic_epoch_id"] != active_epoch:
            out.append(Finding(SEMANTIC_EPOCH_MISMATCH, P1,
                               m.get("concept_id", "-"),
                               f"LGGT mapping bound to epoch "
                               f"{m['semantic_epoch_id']} != active {active_epoch}",
                               {}))
    return out
