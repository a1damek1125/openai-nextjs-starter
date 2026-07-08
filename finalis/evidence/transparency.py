"""Local Merkle transparency ledger (V-E, Gap 6).

Tamper-evident root anchoring for evidence chain events — local,
deterministic, append-only. No blockchain, no external timestamping, no
Sigstore/Rekor. Roots can be exported later, but nothing is anchored
externally now. Deterministic leaf ordering: (tenant, evidence, ts, id).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional

LEAF_PREFIX = b"FINALIS_EVIDENCE_LEAF_V1"
NODE_PREFIX = b"FINALIS_EVIDENCE_NODE_V1"


def _sha(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
        h.update(b"|")
    return h.hexdigest()


def leaf_hash(*, tenant_id: str, evidence_id: str, event_id: str,
              event_type: str, event_timestamp: str,
              previous_event_hash: str, event_payload_hash: str) -> str:
    return _sha(LEAF_PREFIX, tenant_id.encode(), evidence_id.encode(),
                event_id.encode(), event_type.encode(),
                event_timestamp.encode(), previous_event_hash.encode(),
                event_payload_hash.encode())


def parent_hash(left: str, right: str) -> str:
    return _sha(NODE_PREFIX, left.encode(), right.encode())


def merkle_root(leaves: list[str]) -> str:
    """Standard binary Merkle root; odd node is promoted (duplicated)."""
    if not leaves:
        return _sha(NODE_PREFIX, b"EMPTY")
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(parent_hash(left, right))
        level = nxt
    return level[0]


@dataclass
class EvidenceMerkleLeaf:
    tenant_id: str
    evidence_id: str
    event_id: str
    leaf_hash: str
    position: int


@dataclass
class EvidenceMerkleProof:
    leaf_hash: str
    root: str
    path: list                          # [(sibling_hash, is_right), ...]
    index: int
    size: int


@dataclass
class EvidenceMerkleRoot:
    tenant_id: str
    root: str
    size: int
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = ""


def build_proof(leaves: list[str], index: int) -> EvidenceMerkleProof:
    """Inclusion proof for leaves[index] against merkle_root(leaves)."""
    if not leaves or index < 0 or index >= len(leaves):
        raise ValueError("index out of range")
    path = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            if i == idx or i + 1 == idx:
                if idx == i:            # our node is left → sibling right
                    path.append((right, True))
                else:                   # our node is right → sibling left
                    path.append((left, False))
                idx = len(nxt)
            nxt.append(parent_hash(left, right))
        level = nxt
    return EvidenceMerkleProof(leaf_hash=leaves[index],
                               root=merkle_root(leaves), path=path,
                               index=index, size=len(leaves))


def verify_proof(proof: EvidenceMerkleProof, *,
                 expected_root: Optional[str] = None) -> bool:
    h = proof.leaf_hash
    for sibling, sibling_is_right in proof.path:
        h = parent_hash(h, sibling) if sibling_is_right \
            else parent_hash(sibling, h)
    root = expected_root if expected_root is not None else proof.root
    return h == root


def consistency_proof_ok(old_leaves: list[str],
                         new_leaves: list[str]) -> bool:
    """Append-only consistency: new must extend old (prefix preserved)
    and the old root must be reproducible from the first len(old) leaves."""
    if len(new_leaves) < len(old_leaves):
        return False
    if new_leaves[:len(old_leaves)] != old_leaves:
        return False
    return merkle_root(new_leaves[:len(old_leaves)]) \
        == merkle_root(old_leaves)
