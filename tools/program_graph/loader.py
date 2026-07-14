"""Assemble the canonical program object from the separate docs/program artifacts
(SP0003 §Deliverables). Each artifact contributes disjoint top-level keys; the
loader merges them into one in-memory program dict. Canonical data stays split on
disk (INV-0003-17) but is analysed as a whole.
"""
from __future__ import annotations

import json
import os

# artifact file -> loaded verbatim; disjoint top-level keys merged
ARTIFACTS = [
    "FINALIS_1000_PROGRAM_REGISTRY.json",
    "FINALIS_1000_PROGRAM_HYPERGRAPH.json",
    "FINALIS_1000_SCENARIO_REGISTRY.json",
    "FINALIS_1000_GATE_GRAPH.json",
    "FINALIS_1000_RESOURCE_CONFLICT_GRAPH.json",
    "FINALIS_1000_REWORK_GRAPH.json",
    "FINALIS_1000_RISK_CORRELATION_GRAPH.json",
    "FINALIS_1000_COMPLETION_EVIDENCE_GRAPH.json",
    "FINALIS_1000_TEMPORAL_CONSTRAINTS.json",
]

MERGE_LIST_KEYS = {
    "nodes", "hyperedges", "threshold_gates", "scenarios", "gates",
    "gate_bindings", "conflicts", "rework_edges", "risk_correlations",
    "completion_evidence", "temporal_constraints", "duration_models",
    "uncertainties",
}

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "program")


def load_program_bundle(docs_dir: str = DOCS) -> dict:
    program: dict = {k: [] for k in MERGE_LIST_KEYS}
    meta: dict = {}
    for fname in ARTIFACTS:
        path = os.path.join(docs_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for k, v in data.items():
            if k in MERGE_LIST_KEYS and isinstance(v, list):
                program[k].extend(v)
            else:
                meta[k] = v
    program["_meta"] = meta
    return program
