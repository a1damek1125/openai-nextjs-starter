"""Proof-Carrying Semantic Change Envelope (SP0002 D-0002-24, §10.5).

Deterministic, UNSIGNED evidence that a semantic epoch change satisfied the gate:
registry hashes, change-intent hash, compatibility/impact/shadow/replay/LGGT
results, P0/P1 counts. It is EVIDENCE, not authority (INV-0002-16). Same inputs
=> same envelope hash.
"""
from __future__ import annotations

from typing import Any

from . import ENVELOPE_VERSION, VALIDATOR_VERSION
from .canon import core_hash
from .epochs import registry_hash


def build_envelope(*, base_epoch: str, candidate_epoch: str,
                   base_registry: dict, candidate_registry: dict,
                   change_intent: dict, compatibility: dict, impact: dict,
                   shadow: dict, replay: dict, lggt_result: dict,
                   translation_result: dict, conformance: dict) -> dict[str, Any]:
    counts = conformance.get("counts", {})
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "base_epoch": base_epoch,
        "candidate_epoch": candidate_epoch,
        "old_registry_hash": registry_hash(base_registry),
        "new_registry_hash": registry_hash(candidate_registry),
        "change_intent_hash": core_hash(change_intent),
        "compatibility_result_hash": core_hash(compatibility),
        "impact_cone_hash": core_hash(impact),
        "shadow_evaluation_hash": core_hash(shadow),
        "historical_replay_hash": core_hash(replay),
        "mapping_validation_hash": core_hash({"lggt": lggt_result,
                                              "translation": translation_result}),
        "p0_findings": counts.get("P0", 0),
        "p1_findings": counts.get("P1", 0),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["semantic_valid"] = core["p0_findings"] == 0 and core["p1_findings"] == 0
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    env["envelope_hash"] = core_hash(core)
    return env
