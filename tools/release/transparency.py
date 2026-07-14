"""Transparency receipts over an append-only Merkle log (SP0009 §10.12,
§11.16, D-0009-33, AC-0009-163..166).

A receipt proves REGISTERED EXISTENCE AND ORDERING of a claim relative to a log
checkpoint — it never proves the claim true (ATTESTED != TRUE). Receipts are
subject-bound (the digest they register), carry the log identity and
checkpoint, and verify by Merkle inclusion proof. A missing receipt fails only
when policy requires one; an INVALID receipt always fails.
"""
from __future__ import annotations

from .canon import MerkleLog, verify_inclusion, hash_obj
from .model import Finding, P0, P1


def register(log: MerkleLog, *, subject_digest: str, claim_kind: str,
             log_identity: str) -> dict:
    """Append a claim to the log and mint its receipt."""
    entry = f"{claim_kind}:{subject_digest}"
    index = log.append(entry)
    cp = log.checkpoint()
    receipt = {
        "subject_digest": subject_digest,
        "claim_kind": claim_kind,
        "log_identity": log_identity,
        "log_checkpoint": cp,
        "log_index": index,
        "inclusion_proof": log.inclusion_proof(index),
        "status": "UNVERIFIED",
    }
    receipt["receipt_id"] = "TR-" + hash_obj(
        {k: receipt[k] for k in ("subject_digest", "claim_kind",
                                 "log_identity", "log_index")})[:20]
    return receipt


def verify_receipt(receipt: dict, *, expected_subject: str,
                   expected_log_identity: str,
                   pinned_checkpoint: dict | None = None) -> list[Finding]:
    """Verify subject binding, log identity and Merkle inclusion against an
    INDEPENDENTLY PINNED checkpoint. A receipt that carries its own checkpoint
    proves nothing — an attacker can set inclusion_proof=[] and
    checkpoint.root=leaf_hash(entry) for a size-1 forgery (red-team #5). The
    caller must supply the trusted log checkpoint; the receipt's checkpoint
    must match it. The verified receipt proves registration, not truth
    (D-0009-33)."""
    out: list[Finding] = []
    subject = str(receipt.get("receipt_id") or "-")
    if receipt.get("subject_digest") != expected_subject:
        out.append(Finding(
            "TRANSPARENCY_RECEIPT_INVALID", P0, subject,
            "receipt subject digest does not match the artifact it is "
            "presented for (receipts are subject-bound, INV-0009-28)",
            {"receipt_subject": receipt.get("subject_digest"),
             "expected": expected_subject}))
    if receipt.get("log_identity") != expected_log_identity:
        out.append(Finding(
            "TRANSPARENCY_RECEIPT_INVALID", P1, subject,
            f"receipt from unexpected log {receipt.get('log_identity')!r}",
            {}))
    checkpoint = receipt.get("log_checkpoint") or {}
    if pinned_checkpoint is not None:
        # the receipt's checkpoint must equal the independently-pinned one
        if checkpoint.get("root") != pinned_checkpoint.get("root") \
                or checkpoint.get("size") != pinned_checkpoint.get("size"):
            out.append(Finding(
                "TRANSPARENCY_RECEIPT_INVALID", P0, subject,
                "receipt checkpoint does not match the pinned trusted log "
                "checkpoint: a self-asserted checkpoint is not evidence "
                "(red-team #5)",
                {"receipt_checkpoint": checkpoint,
                 "pinned": pinned_checkpoint}))
            checkpoint = pinned_checkpoint   # verify inclusion vs the trusted
    else:
        # no pinned checkpoint supplied: an empty inclusion proof (size-1
        # self-attestation) cannot be trusted
        if not (receipt.get("inclusion_proof") or []) \
                and checkpoint.get("size", 0) <= 1:
            out.append(Finding(
                "TRANSPARENCY_RECEIPT_INVALID", P1, subject,
                "receipt presents an empty inclusion proof with no pinned "
                "checkpoint to verify against: registration cannot be "
                "confirmed", {}))
    entry = f"{receipt.get('claim_kind')}:{receipt.get('subject_digest')}"
    if not verify_inclusion(entry, receipt.get("inclusion_proof") or [],
                            checkpoint):
        out.append(Finding(
            "TRANSPARENCY_RECEIPT_INVALID", P0, subject,
            "Merkle inclusion proof does not verify against the checkpoint: "
            "forged or corrupted receipt", {}))
    return out


def policy_findings(receipts: list, *, required: bool,
                    subject_digest: str) -> list[Finding]:
    """Missing transparency evidence fails only when policy requires it
    (§11.16)."""
    out: list[Finding] = []
    if required and not receipts:
        out.append(Finding(
            "TRANSPARENCY_RECEIPT_MISSING", P0, subject_digest,
            "policy requires a transparency receipt for this artifact and "
            "none is present", {}))
    return out
