"""Compatibility / Migration / Rollback / Deprecation Proof Envelopes
(SP0007 §10.12/10.13, D-0007-33/34, AC-0007-191..196).

Envelopes bind the material evolution artifacts by hash into deterministic,
bit-reproducible records. A proof envelope is EVIDENCE, never authority
(INV-0007-46): it cannot authorize a migration, a cutover, or a removal. A
contract change changes the proof hash (AC-0007-195); a transformer change
changes the migration proof (AC-0007-196). Authority-implying keys are rejected
by an allowlist-style hint scan (a blocklist of a few names is bypassable).
"""
from __future__ import annotations

from .model import Finding, P1, PROOF_ENVELOPE_MISMATCH
from .canon import canonical_json, core_hash, sha256_hex

ENVELOPE_VERSION = "1.0.0"
VALIDATOR_VERSION = "sp0007-compat-validator-1"


def _h(obj) -> str:
    return core_hash(obj) if obj is not None else ""


def _seal(core: dict) -> dict:
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env


def compatibility_proof_envelope(*, descriptor, producer_version,
                                 consumer_binding, compatibility_vector,
                                 historical_corpus=None, semantic_analysis=None,
                                 behavioral_analysis=None, replay_result=None,
                                 security_result=None) -> dict:
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "envelope_kind": "COMPATIBILITY",
        "contract_descriptor_hash": _h(descriptor),
        "producer_version_hash": _h(producer_version),
        "consumer_binding_hash": _h(consumer_binding),
        "compatibility_vector_hash": _h(compatibility_vector),
        "historical_corpus_hash": _h(historical_corpus),
        "semantic_analysis_hash": _h(semantic_analysis),
        "behavioral_analysis_hash": _h(behavioral_analysis),
        "replay_result_hash": _h(replay_result),
        "security_result_hash": _h(security_result),
        "validator_version": VALIDATOR_VERSION,
    }
    return _seal(core)


def migration_proof_envelope(*, migration_plan, source_state=None,
                             target_state=None, transformer=None,
                             checkpoint_manifest=None, loss_vector=None,
                             round_trip_result=None, replay_result=None,
                             rollback_result=None,
                             consumer_verification=None) -> dict:
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "envelope_kind": "MIGRATION",
        "migration_plan_hash": _h(migration_plan),
        "source_state_hash": _h(source_state),
        "target_state_hash": _h(target_state),
        "transformer_hash": _h(transformer),
        "checkpoint_manifest_hash": _h(checkpoint_manifest),
        "loss_vector_hash": _h(loss_vector),
        "round_trip_result_hash": _h(round_trip_result),
        "replay_result_hash": _h(replay_result),
        "rollback_result_hash": _h(rollback_result),
        "consumer_verification_hash": _h(consumer_verification),
        "validator_version": VALIDATOR_VERSION,
    }
    return _seal(core)


def rollback_proof_envelope(*, rollback_plan, inverse_transformer=None,
                            round_trip_result=None, boundary=None) -> dict:
    core = {"envelope_version": ENVELOPE_VERSION, "envelope_kind": "ROLLBACK",
            "rollback_plan_hash": _h(rollback_plan),
            "inverse_transformer_hash": _h(inverse_transformer),
            "round_trip_result_hash": _h(round_trip_result),
            "boundary_hash": _h(boundary),
            "validator_version": VALIDATOR_VERSION}
    return _seal(core)


def deprecation_proof_envelope(*, notice, consumer_inventory=None,
                               migration_evidence=None, support_window=None,
                               sunset_gate_result=None) -> dict:
    core = {"envelope_version": ENVELOPE_VERSION, "envelope_kind": "DEPRECATION",
            "notice_hash": _h(notice),
            "consumer_inventory_hash": _h(consumer_inventory),
            "migration_evidence_hash": _h(migration_evidence),
            "support_window_hash": _h(support_window),
            "sunset_gate_hash": _h(sunset_gate_result),
            "validator_version": VALIDATOR_VERSION}
    return _seal(core)


# an envelope's structural fields: metadata + kind + validator + any *_hash.
# ALLOWLIST (fail-closed) — any key outside this shape may be smuggling
# authority/semantics into an evidence record and is rejected, since a blocklist
# of authority synonyms is bypassable (SWARM-M E7; INV-0007-46).
_ALLOWED_META = frozenset({"envelope_version", "envelope_kind",
                           "validator_version", "envelope_hash",
                           "classification"})


def validate_envelope(envelope: dict) -> list[Finding]:
    """Recompute the hash; reject any non-structural key. Proof is evidence, not
    authority (INV-0007-46); old envelopes are never silently reinterpreted."""
    out: list[Finding] = []
    eid = envelope.get("envelope_kind", "-")
    core = {k: v for k, v in envelope.items()
            if k not in ("envelope_hash", "classification")}
    if envelope.get("envelope_hash") \
            and envelope["envelope_hash"] != sha256_hex(canonical_json(core)):
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                           "envelope hash does not match its content", {}))
    if envelope.get("classification") not in (None, "EVIDENCE_NOT_AUTHORITY"):
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                           "envelope must be EVIDENCE_NOT_AUTHORITY", {}))
    for key in envelope:
        if key in _ALLOWED_META or key.endswith("_hash"):
            continue
        out.append(Finding(PROOF_ENVELOPE_MISMATCH, P1, eid,
                           f"envelope carries a non-structural key {key!r} — an "
                           "envelope is a hash-only evidence record, never "
                           "authority (INV-0007-46)", {}))
    return out
