"""Assemble the safety program from docs/safety artifacts into one dict."""
from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "safety")

# artifact file -> the top-level key(s) it contributes (merged into one program)
FILES = {
    "FINALIS_LOSS_TAXONOMY.json": None,
    "FINALIS_HAZARD_REGISTRY.json": None,
    "FINALIS_THREAT_REGISTRY.json": None,
    "FINALIS_UNSAFE_CONTROL_ACTIONS.json": None,
    "FINALIS_SAFETY_CONSTRAINTS.json": None,
    "FINALIS_CONTROL_BARRIER_GRAPH.json": None,
    "FINALIS_ACTION_SAFETY_CONTRACTS.json": None,
    "FINALIS_TRAJECTORY_SAFETY_CONTRACTS.json": None,
    "FINALIS_TRAJECTORY_SAFETY_AUTOMATA.json": None,
    "FINALIS_SAFETY_PROOF_OBLIGATIONS.json": None,
    "FINALIS_ASSURANCE_CASES.json": None,
    "FINALIS_SAFETY_EVIDENCE.json": None,
    "FINALIS_REGULATORY_SOURCE_REGISTRY.json": None,
    "FINALIS_HIGH_IMPACT_USE_CASES.json": None,
    "FINALIS_HUMAN_REVIEW_PACKETS.json": None,
    "FINALIS_SAFETY_SCENARIOS.json": None,
    "FINALIS_INCIDENTS.json": None,
    "FINALIS_NEAR_MISSES.json": None,
}

# top-level list keys we merge across files
LIST_KEYS = {"losses", "hazards", "threats", "unsafe_control_actions",
             "constraints", "controls", "independence_claims", "action_contracts",
             "trajectory_contracts", "automata", "proof_obligations", "claims",
             "defeaters", "evidence", "sources", "use_cases", "review_packets",
             "scenarios", "incidents", "near_misses"}


def load_program(docs_dir: str = DOCS) -> dict:
    program: dict = {k: [] for k in LIST_KEYS}
    meta: dict = {}
    for fname in FILES:
        path = os.path.join(docs_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for k, v in data.items():
            if k in LIST_KEYS and isinstance(v, list):
                program[k].extend(v)
            else:
                meta[k] = v
    program["_meta"] = meta
    return program
