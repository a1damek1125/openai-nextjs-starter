"""Deterministic canonical JSON + SHA-256 hashing for the Governed Work,
Delegated Autonomy & Outcome Accountability Constitution (SP0006 §11.2/11.3,
D-0006-02/07).

Two distinct identities are computed (D-0006-02): a `semantic_work_hash` over the
canonical MEANING of the work (goal/scope/constraints/outcome/purpose/capability/
risk — excluding execution identity and timestamps) and a `work_instance_hash`
over the execution instance (work_order_id/tenant/requester/owner/source/
recurrence/issue/expiry + the semantic hash). Two semantically equivalent jobs
share the semantic identity while remaining distinct execution instances.

Fingerprints and proof envelopes digest a CANONICAL serialization (sorted keys,
no whitespace, no NaN) with volatile presentation stripped, so every hash is
bit-reproducible (AC-0006-192). Governance tooling only; product runtime must
never import it (INV-0006-46). It opens NO external effect (INV-0006-47).
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


# volatile / presentation keys excluded from hashed cores
VOLATILE_KEYS = frozenset({
    "display_name", "label", "notes", "editor_notes", "_comment", "description",
    "retrieved_at", "generated_at", "ui_hint", "color", "raw_content",
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


# --- semantic vs instance work identity (D-0006-02, §11.2/11.3) ------------
# ONLY these fields define the canonical MEANING of the work; execution identity
# and timestamps are deliberately excluded so semantically equivalent work shares
# a semantic hash.
SEMANTIC_FIELDS = ("semantic_epoch", "canonical_goal", "allowed_scope",
                   "forbidden_scope", "constraints", "outcome_contract",
                   "privacy_purpose", "capability_ceiling", "risk_requirements")
# the execution instance binds identity + provenance + time to the semantic hash.
INSTANCE_FIELDS = ("work_order_id", "tenant_id", "requester_id",
                   "accountable_owner_id", "source_reference",
                   "recurrence_instance", "issued_at", "expires_at")


def semantic_work_hash(work: dict) -> str:
    """H_s over canonical work meaning (D-0006-02, §11.2). Order-independent and
    free of execution identity / timestamps."""
    core = {f: work.get(f) for f in SEMANTIC_FIELDS}
    return core_hash(core)


def work_instance_hash(work: dict) -> str:
    """H_i over the execution instance (§11.3), bound to the semantic hash. Two
    equivalent jobs share H_s but differ in H_i (different tenant/recurrence/
    issue-time)."""
    core = {f: work.get(f) for f in INSTANCE_FIELDS}
    core["semantic_work_hash"] = work.get("semantic_work_hash") \
        or semantic_work_hash(work)
    return core_hash(core)


# --- action / target fingerprints for approval binding (D-0006-32) ---------
# An approval binds the exact material action; a material change (target, amount,
# recipient, effect) must change the fingerprint (INV-0006-23/24/25).
def action_fingerprint(action: dict) -> str:
    """Fail-CLOSED: hash the whole action minus known-volatile keys so any
    material value (including one placed at the action root) changes it."""
    return core_hash(action if isinstance(action, dict) else {"_action": action})


TARGET_MATERIAL_FIELDS = ("target_type", "target_id", "recipient", "account",
                          "file", "phone_number", "amount", "document")


def target_fingerprint(action: dict) -> str:
    tgt = action.get("target", action) if isinstance(action, dict) else action
    core = {f: tgt.get(f) if isinstance(tgt, dict) else None
            for f in TARGET_MATERIAL_FIELDS}
    return core_hash(core)


def material_parameters_hash(params: Any) -> str:
    return core_hash(params)
