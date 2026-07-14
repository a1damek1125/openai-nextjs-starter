"""Proof-Carrying Program Plan Envelope (SP0003 D-0003-43, §10.11/§11.25,
INV-0003-20).

A deterministic envelope over the canonical program structure AND the derived
analyses that were validated together. Volatile display metadata is excluded, so
the same program state always yields the same envelope hash (AC-0003-92) and a
scenario/hypergraph/gate/evidence-significant change changes it
(AC-0003-93/94/95). It is EVIDENCE, not execution authority (INV-0003-20): it
proves which model + analyses were validated together, not that the future will
occur as forecast.
"""
from __future__ import annotations

from .canon import core_hash, sha256_hex, canonical_json
from .registry import registry_hash
from .hypergraph import default_active
from .graphalgo import precedence_pairs

ENVELOPE_VERSION = "2.0.0"
VALIDATOR_VERSION = "sp0003-v2"


def _h(obj) -> str:
    return core_hash(obj)


def build_envelope(program: dict, *, base_commit: str = "",
                   scenario_id: str = "BASELINE",
                   derived: dict | None = None) -> dict:
    """Assemble the envelope. `derived` optionally carries critical_path /
    criticality / dominator / cut_set / voi result objects to bind them to this
    validated state."""
    derived = derived or {}
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "base_commit": base_commit,
        "scenario": scenario_id,
        "program_registry_hash": registry_hash(program),
        "dependency_hypergraph_hash": _h(program.get("hyperedges", [])),
        "scenario_hash": _h(program.get("scenarios", [])),
        "gate_graph_hash": _h(program.get("gates", [])),
        # gate_bindings + threshold_gates are first-class readiness inputs — a
        # change to either (e.g. un-guarding a safety gate) MUST change the
        # envelope (red-team SWARM-L Finding 3, AC-0003-93/95).
        "gate_binding_hash": _h(program.get("gate_bindings", [])),
        "threshold_gate_hash": _h(program.get("threshold_gates", [])),
        "uncertainty_hash": _h(program.get("uncertainties", [])),
        "conflict_graph_hash": _h(program.get("conflicts", [])),
        "rework_graph_hash": _h(program.get("rework_edges", [])),
        "risk_graph_hash": _h(program.get("risk_correlations", [])),
        "temporal_constraint_hash": _h(program.get("temporal_constraints", [])),
        "completion_evidence_hash": _h(program.get("completion_evidence", [])),
        "duration_model_hash": _h(program.get("duration_models", [])),
        "critical_path_hash": _h(derived.get("critical_path")),
        "criticality_hash": _h(derived.get("criticality")),
        "dominator_hash": _h(derived.get("dominators")),
        "cut_set_hash": _h(derived.get("cut_set")),
        "voi_model_hash": _h(derived.get("voi")),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env
