"""Canonical surface record assembly (SP0008 §surfaces, D-0008-05..08).

Folds every analysis output into one canonical, self-describing record per
surface: identity + parent registry contract, grounded evidence, the criticality
vector + conjunctive verdict, effect reachability, producer/consumer sets with
certainty typing, ownership, behavioral witnesses, detector corroboration, the
readiness diagnostic, and the surface's material genome leaf. The record is the
queryable atom the CLI answers questions from, and its material leaf is what the
Contract Genome seals.
"""
from __future__ import annotations

from .canon import core_hash
from .genome import surface_material_leaf


def build_surface_record(surface, *, shape, crit_vec, crit_verdict, reach,
                         producers, consumer, owner, witnesses, corrob,
                         readiness_rec, claims) -> dict:
    """Assemble one canonical inventory record. All inputs are precomputed by
    the pipeline so this stays a pure, deterministic fold."""
    rec = {
        "surface_id": surface.surface_id,
        "surface_kind": surface.surface_kind,
        "canonical_name": surface.canonical_name,
        "contract_kind": surface.contract_kind,
        "parent_contract_id": surface.parent_contract_id,
        "identity_outcome": surface.identity_outcome,
        "state": _lifecycle_state(surface, crit_vec, witnesses),
        "evidence": [{"path": p, "line": ln} for p, ln in surface.evidence],
        "detectors": list(surface.detectors),
        "corroboration": corrob,
        "criticality": {"vector": crit_vec, "verdict": crit_verdict},
        "effect_reachability": reach,
        "producers": producers,
        "consumers": consumer,
        "ownership": owner,
        "witnesses": [w["witness_id"] for w in witnesses],
        "witness_count": len(witnesses),
        "readiness": readiness_rec,
        "claim_ids": [c.claim_id for c in claims],
        "notes": list(surface.notes),
        "material_leaf": surface_material_leaf(surface),
    }
    rec["record_hash"] = core_hash({k: rec[k] for k in rec
                                    if k != "record_hash"})
    return rec


def _lifecycle_state(surface, crit_vec, witnesses) -> str:
    """Derive the surface's lifecycle state (§13) from what is established."""
    if surface.identity_outcome in ("AMBIGUOUS_IDENTITY", "DUPLICATE_CANDIDATE"):
        return "RECONCILED"          # identity resolved but contested
    if witnesses:
        return "WITNESSED"
    if any(v != "UNKNOWN" for v in crit_vec.values()):
        return "CLASSIFIED"
    return "EVIDENCED"


def surface_index(records) -> dict:
    """Index records by several keys for O(1) CLI lookups."""
    by_id = {r["surface_id"]: r for r in records}
    by_kind: dict = {}
    by_parent: dict = {}
    for r in records:
        by_kind.setdefault(r["surface_kind"], []).append(r["surface_id"])
        by_parent.setdefault(r["parent_contract_id"], []).append(
            r["surface_id"])
    return {"by_id": by_id, "by_kind": by_kind, "by_parent": by_parent}
