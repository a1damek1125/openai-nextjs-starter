"""Proof-Carrying Change Envelope (SP0001 D-0001-13, §11.10).

Deterministic, UNSIGNED attestation of what the architecture validation checked
and its result. Establishes CONTENT INTEGRITY (same inputs => same envelope,
INV-0001-12); it is EVIDENCE, not authority (INV-0001-08), and NOT organizational
identity — cryptographic signing is deferred to KMS (D-0001-14).
"""
from __future__ import annotations

from typing import Any

from . import ENVELOPE_VERSION, VALIDATOR_VERSION
from .canon import core_hash


def build_envelope(*, base_commit: str, source_commit: str,
                   declared_twin: dict, observed: dict,
                   architecture_delta: dict, conformance: dict,
                   change_intent: dict | None = None,
                   waiver_set: list[str] | None = None,
                   test_evidence: list[str] | None = None) -> dict[str, Any]:
    counts = conformance.get("counts", {})
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "base_commit": base_commit,
        "source_commit": source_commit,
        "change_intent_hash": core_hash(change_intent) if change_intent else None,
        "declared_architecture_hash": core_hash(declared_twin),
        "observed_architecture_hash": core_hash(observed),
        "architecture_delta_hash": core_hash(architecture_delta),
        "migration_integrity": "PASS" if not any(
            f["kind"] == "MIGRATION_MUTATION" and f["severity"] in ("P0", "P1")
            for f in conformance.get("findings", [])) else "FAIL",
        "effect_gate": "PASS" if not any(
            f["kind"] == "EFFECT_GATE_VIOLATION"
            for f in conformance.get("findings", [])) else "FAIL",
        "p0_findings": counts.get("P0", 0),
        "p1_findings": counts.get("P1", 0),
        "waiver_set_hash": core_hash(sorted(waiver_set or [])),
        "validator_version": VALIDATOR_VERSION,
        "test_evidence": sorted(test_evidence or []),
    }
    envelope = dict(core)
    envelope["architecture_valid"] = (core["p0_findings"] == 0
                                      and core["p1_findings"] == 0)
    envelope["classification"] = "EVIDENCE_NOT_AUTHORITY"
    envelope["envelope_hash"] = core_hash(core)
    return envelope
