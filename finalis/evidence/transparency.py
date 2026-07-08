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


# ---------------------------------------------------------------------------
# Finalis Evidence Transparency Log Core (EVIDENCE-MERKLE-C1).
#
# The system persists the full ordered leaf list for every root checkpoint,
# so append-only consistency is verified AUTHORITATIVELY by full-leaf
# recomputation (prefix relation is tree-shape independent). Alongside that,
# a compact RFC 9162 / RFC 6962 consistency proof is generated over the
# canonical Merkle Tree Head (mth) and server-verified before a VERIFIED
# verdict is returned. No blockchain, no external notarization, no external
# transparency service — Finalis-owned, local, deterministic.
# ---------------------------------------------------------------------------
SUPPORTED_HASH_ALGORITHMS = {"sha256", "sha-256"}


def _largest_pow2_lt(n: int) -> int:
    """Largest power of two strictly smaller than n (n >= 2)."""
    k = 1
    while (k << 1) < n:
        k <<= 1
    return k


def mth(leaves: list[str]) -> str:
    """RFC 9162 canonical Merkle Tree Head (power-of-two split, no odd-node
    duplication). Used only for the compact consistency proof; the stored
    checkpoint `root` keeps Finalis' existing construction."""
    n = len(leaves)
    if n == 0:
        return _sha(NODE_PREFIX, b"EMPTY")
    if n == 1:
        return leaves[0]
    k = _largest_pow2_lt(n)
    return parent_hash(mth(leaves[:k]), mth(leaves[k:]))


def _subproof(m: int, leaves: list[str], b: bool) -> list[str]:
    n = len(leaves)
    if m == n:
        return [] if b else [mth(leaves)]
    k = _largest_pow2_lt(n)
    if m <= k:
        return _subproof(m, leaves[:k], b) + [mth(leaves[k:])]
    return _subproof(m - k, leaves[k:], False) + [mth(leaves[:k])]


def consistency_proof(m: int, leaves: list[str]) -> list[str]:
    """RFC 6962/9162 consistency proof PROOF(m, D[n]) — the compact node set
    that proves the size-m tree is a prefix of the size-n tree. Empty for the
    trivial m==0 / m==n cases; deterministic for a given (m, leaves)."""
    n = len(leaves)
    if m <= 0 or m >= n:
        return []
    return _subproof(m, leaves, True)


def verify_consistency(first_size: int, second_size: int, first_hash: str,
                       second_hash: str, proof: list[str]) -> bool:
    """RFC 6962 consistency-proof verifier: reconstruct both the old and new
    canonical tree heads from `proof` and confirm they match. Pure, no I/O."""
    if first_size < 0 or second_size < 0 or first_size > second_size:
        return False
    if first_size == second_size:
        return first_hash == second_hash and len(proof) == 0
    if first_size == 0:
        return len(proof) == 0
    nodes = list(proof)
    fn, sn = first_size - 1, second_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    if fn == 0:
        seed = first_hash
    else:
        if not nodes:
            return False
        seed = nodes[0]
        nodes = nodes[1:]
    node1 = node2 = seed
    for c in nodes:
        if sn == 0:
            return False
        if (fn & 1) or (fn == sn):
            node1 = parent_hash(c, node1)
            node2 = parent_hash(c, node2)
            while fn != 0 and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            node2 = parent_hash(node2, c)
        fn >>= 1
        sn >>= 1
    return node1 == first_hash and node2 == second_hash and sn == 0


# Consistency-report statuses (server-authoritative).
CONSISTENCY_STATUSES = {
    "VERIFIED", "NOT_VERIFIED", "PROOF_MISSING", "ROOT_NOT_FOUND",
    "INVALID_RANGE", "UNSUPPORTED_ALGORITHM", "SERVER_REVIEW_REQUIRED"}


@dataclass
class ConsistencyReport:
    status: str
    append_only_verified: bool
    proof_nodes: list
    reason: str
    previous_tree_hash: str = ""
    current_tree_hash: str = ""


def consistency_report(*, old_leaves: list, old_root: str, old_size: int,
                       new_leaves: list, new_root: str, new_size: int,
                       algorithm: str = "sha256") -> ConsistencyReport:
    """Authoritative append-only verdict between two stored checkpoints.

    VERIFIED requires ALL of: supported algorithm; previous_size <=
    current_size; full historical leaf order present on both sides; the
    previous leaf list is a byte-exact prefix of the current one; both stored
    roots recompute from their leaves (tamper check); and the compact RFC 9162
    consistency proof reconstructs both canonical tree heads."""
    if algorithm.lower() not in SUPPORTED_HASH_ALGORITHMS:
        return ConsistencyReport(
            "UNSUPPORTED_ALGORITHM", False, [],
            f"hash algorithm '{algorithm}' is not supported — verification "
            "refused")
    if old_size > new_size:
        return ConsistencyReport(
            "INVALID_RANGE", False, [],
            "Merkle consistency proof requires previous tree size <= "
            "current tree size.")
    # Historical leaf order must be fully present to reconstruct a proof.
    if len(old_leaves) != old_size or len(new_leaves) != new_size:
        return ConsistencyReport(
            "PROOF_MISSING", False, [],
            "Historical leaf order is missing, so consistency proof cannot "
            "be reconstructed.")
    # Stored roots must recompute from their own leaves (tamper detection).
    if merkle_root(old_leaves) != old_root \
            or merkle_root(new_leaves) != new_root:
        return ConsistencyReport(
            "NOT_VERIFIED", False, [],
            "A stored root does not match its recorded leaves — append-only "
            "consistency is not verified.")
    old_th, new_th = mth(old_leaves), mth(new_leaves)
    if old_size == new_size:
        ok = old_leaves == new_leaves
        return ConsistencyReport(
            "VERIFIED" if ok else "NOT_VERIFIED", ok, [],
            "Trivial same-root consistency: identical tree size and leaves."
            if ok else "Roots of equal size differ — not append-only.",
            old_th, new_th)
    if new_leaves[:old_size] != old_leaves:
        return ConsistencyReport(
            "NOT_VERIFIED", False, [],
            "Previous root is not part of the current append-only history "
            "(leaf prefix does not match).", old_th, new_th)
    proof = consistency_proof(old_size, new_leaves)
    if not verify_consistency(old_size, new_size, old_th, new_th, proof):
        return ConsistencyReport(
            "SERVER_REVIEW_REQUIRED", False, proof,
            "Generated consistency proof failed server-side verification.",
            old_th, new_th)
    return ConsistencyReport(
        "VERIFIED", True, proof,
        "Server-verified append-only extension: previous tree is a prefix "
        "of the current tree.", old_th, new_th)
