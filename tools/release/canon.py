"""Deterministic canonical JSON, SHA-256 and Merkle log primitives for the
Release Assurance kernel (SP0009 §11.11, §12, D-0009-03).

Every candidate genome, gate configuration fingerprint, evidence claim,
manifest, attestation and proof envelope digests a CANONICAL serialization
(sorted keys, compact, no NaN) with volatile presentation stripped, so release
truth is bit-reproducible and any material change moves the digest. The small
append-only Merkle log supports transparency receipts (inclusion proofs) without
deploying any external log infrastructure.

Governance tooling only; never imported by product code; opens no external
effect; never emits secret values.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_obj(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


VOLATILE_KEYS = frozenset({
    "display_name", "label", "notes", "_comment", "description",
    "observed_at", "generated_at", "ui_hint", "color",
})


def strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items()
                if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def core_hash(obj: Any) -> str:
    return sha256_hex(canonical_json(strip_volatile(obj)))


# --- append-only Merkle log for transparency receipts (§11.16, D-0009-33) ---
def _leaf_hash(entry: str) -> str:
    return sha256_hex("L\x00" + entry)


def _node_hash(a: str, b: str) -> str:
    return sha256_hex("N\x00" + a + "\x00" + b)


class MerkleLog:
    """A minimal RFC6962-style append-only log: leaves are entry hashes; the
    checkpoint is (size, root). Inclusion proofs verify an entry against a
    checkpoint. Deterministic, in-memory, standard library only."""

    def __init__(self) -> None:
        self._leaves: list[str] = []

    def append(self, entry: str) -> int:
        self._leaves.append(_leaf_hash(entry))
        return len(self._leaves) - 1

    @property
    def size(self) -> int:
        return len(self._leaves)

    def root(self) -> str:
        return self._subtree_root(0, self.size)

    def _subtree_root(self, lo: int, hi: int) -> str:
        n = hi - lo
        if n == 0:
            return sha256_hex("EMPTY_LOG")
        if n == 1:
            return self._leaves[lo]
        k = 1
        while k * 2 < n:
            k *= 2
        return _node_hash(self._subtree_root(lo, lo + k),
                          self._subtree_root(lo + k, hi))

    def checkpoint(self) -> dict:
        return {"size": self.size, "root": self.root()}

    def inclusion_proof(self, index: int) -> list:
        """Sibling path for leaf `index` against the current tree."""
        if not (0 <= index < self.size):
            raise IndexError(index)
        proof: list = []

        def walk(lo: int, hi: int, idx: int) -> None:
            n = hi - lo
            if n <= 1:
                return
            k = 1
            while k * 2 < n:
                k *= 2
            if idx < lo + k:
                walk(lo, lo + k, idx)
                proof.append(("R", self._subtree_root(lo + k, hi)))
            else:
                walk(lo + k, hi, idx)
                proof.append(("L", self._subtree_root(lo, lo + k)))

        walk(0, self.size, index)
        return proof


def verify_inclusion(entry: str, proof: list, checkpoint: dict) -> bool:
    """Verify an inclusion proof against a checkpoint root. Pure function —
    a forged proof or wrong checkpoint simply fails."""
    h = _leaf_hash(entry)
    for side, sib in proof:
        if side == "R":
            h = _node_hash(h, sib)
        elif side == "L":
            h = _node_hash(sib, h)
        else:
            return False
    return h == checkpoint.get("root")
