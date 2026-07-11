"""Assemble the technology-governance program from docs/technology artifacts."""
from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "technology")

# artifact filename -> program key it populates
FILE_MAP = {
    "FINALIS_TECHNOLOGY_INVENTORY.json": "inventory",
    "FINALIS_STRATEGIC_IP_BOUNDARIES.json": "strategic_map",
    "FINALIS_TECHNOLOGY_DEPENDENCY_GRAPH.json": "dependency_graph",
    "FINALIS_TECHNOLOGY_DECISION_REGISTRY.json": "decision_registry",
    "FINALIS_EVIDENCE_REGISTRY.json": "evidence_registry",
    "FINALIS_PROVIDER_CAPABILITY_CONTRACTS.json": "contracts",
    "FINALIS_PROVIDER_CAPABILITY_PROFILES.json": "_profiles_wrap",
    "FINALIS_EXIT_READINESS.json": "_exit_wrap",
    "FINALIS_PROTOCOL_VERSION_REGISTRY.json": "protocols",
    "FINALIS_TECHNOLOGY_RADAR.json": "radar",
    "FINALIS_SUPPLY_CHAIN_STRATEGY.json": "supply_chain",
    "FINALIS_TECHNOLOGY_FITNESS.json": "_fitness_wrap",
    "FINALIS_GOLDEN_CANONICAL_WORKLOADS.json": "_corpus_wrap",
    "FINALIS_PROVIDER_SUBSTITUTION_EVIDENCE.json": "_subs_wrap",
    "FINALIS_PROVIDER_GROUPS.json": "_groups_wrap",
}


def load_program(docs_dir: str = DOCS) -> dict:
    program: dict = {}
    for fname, key in FILE_MAP.items():
        path = os.path.join(docs_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if key == "_profiles_wrap":
            program["provider_profiles"] = data.get("profiles", [])
        elif key == "_exit_wrap":
            program["exit_profiles"] = data.get("exit_profiles", [])
        elif key == "_fitness_wrap":
            program["fitness_defs"] = data.get("fitness_functions", [])
        elif key == "_corpus_wrap":
            program["golden_corpus"] = data.get("workloads", [])
        elif key == "_subs_wrap":
            program["substitution_evidence"] = data.get("substitution_evidence", [])
        elif key == "_groups_wrap":
            program["provider_groups"] = data.get("groups", [])
            program["waivers"] = data.get("waivers", [])
        else:
            program[key] = data
    return program
