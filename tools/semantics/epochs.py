"""Semantic Epochs — bitemporal, deterministic (SP0002 D-0002-04/05, §11.4).

An epoch is an immutable snapshot of canonical concept meanings + relationships.
EpochHash is deterministic over the ordered semantic cores (ordered by immutable
concept identity). Bitemporal: VALID time (when applicable) vs TRANSACTION time
(when recorded) — so historical records interpret under their original epoch
(INV-0002-12).
"""
from __future__ import annotations

from typing import Any

from .canon import canonical_json, sha256_hex, semantic_core

EPOCH_STATES = {"DRAFT", "VALIDATING", "SHADOW", "REPLAYED", "APPROVED",
                "ACTIVE", "SUPERSEDED", "REJECTED"}
# lifecycle transitions (D-0002 §13.2)
EPOCH_TRANSITIONS = {
    "DRAFT": {"VALIDATING"},
    "VALIDATING": {"SHADOW", "REJECTED"},
    "SHADOW": {"REPLAYED", "REJECTED"},
    "REPLAYED": {"APPROVED", "REJECTED"},
    "APPROVED": {"ACTIVE"},
    "ACTIVE": {"SUPERSEDED"},
    "SUPERSEDED": set(),
    "REJECTED": set(),
}


def registry_hash(registry: dict) -> str:
    """Deterministic hash over concept semantic cores, ordered by concept_id."""
    concepts = sorted(registry.get("concepts", []),
                      key=lambda c: c["concept_id"])
    cores = [semantic_core(c) for c in concepts]
    return sha256_hex(canonical_json(cores))


def epoch_hash(epoch: dict, registry: dict) -> str:
    core = {
        "semantic_epoch_id": epoch.get("semantic_epoch_id"),
        "parent_epoch_id": epoch.get("parent_epoch_id"),
        "registry_hash": registry_hash(registry),
    }
    return sha256_hex(canonical_json(core))


def is_valid_epoch_transition(frm: str, to: str) -> bool:
    return to in EPOCH_TRANSITIONS.get(frm, set())


def interpret_under(record: dict, epochs: list[dict]) -> str | None:
    """Return the semantic_epoch_id a historical record must be interpreted under:
    its own recorded epoch (INV-0002-12), NOT the current epoch."""
    if record.get("semantic_epoch_id"):
        return record["semantic_epoch_id"]
    # fall back to the epoch ACTIVE at the record's transaction time (valid time)
    ts = record.get("recorded_at") or record.get("created_at")
    if ts is None:
        return None
    candidates = [e for e in epochs
                  if e.get("valid_from") and e["valid_from"] <= ts
                  and (e.get("valid_until") is None or e["valid_until"] > ts)]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e["valid_from"])["semantic_epoch_id"]


def detect_epoch_downgrade(current_epoch_id: str, requested_epoch_id: str,
                           epochs: list[dict]) -> bool:
    """True if a request tries to use an epoch OLDER than the active one for a
    NEW write (epoch downgrade / confusion, SP0002 §17).

    Fails CLOSED: an unknown current or requested epoch is treated as suspicious
    (returns True) rather than silently allowed (red-team B2). Ordering uses a
    deterministic total order (valid_from, recorded_at, semantic_epoch_id) so
    equal timestamps do not make the verdict input-order-dependent (red-team B3).
    """
    order = {e["semantic_epoch_id"]: i for i, e in enumerate(sorted(
        epochs, key=lambda e: (e.get("valid_from", ""), e.get("recorded_at", ""),
                               e.get("semantic_epoch_id", ""))))}
    if current_epoch_id not in order or requested_epoch_id not in order:
        return True   # fail closed on unknown epoch
    return order[requested_epoch_id] < order[current_epoch_id]
