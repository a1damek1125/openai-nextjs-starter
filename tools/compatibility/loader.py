"""Assemble the compatibility program from docs/compatibility artifacts into one
dict (mirrors the SP0003..SP0006 loader pattern)."""
from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "compatibility")

FILES = (
    "FINALIS_CONTRACT_DESCRIPTORS.json",
    "FINALIS_CONTRACT_VERSIONS.json",
    "FINALIS_CONSUMER_BINDINGS.json",
    "FINALIS_COMPATIBILITY_CLAIMS.json",
    "FINALIS_HISTORICAL_CORPUS.json",
    "FINALIS_MIGRATION_GRAPH.json",
    "FINALIS_MIGRATION_PLANS.json",
    "FINALIS_DEPRECATIONS.json",
    "FINALIS_SUPPORT_WINDOWS.json",
    "FINALIS_RESERVED_IDENTIFIERS.json",
    "FINALIS_PROOF_READERS.json",
    "FINALIS_PROVIDER_PINS.json",
    "FINALIS_CHANGE_INTENTS.json",
)

LIST_KEYS = {"descriptors", "versions", "bindings", "claims", "fixtures",
             "migration_edges", "migration_plans", "deprecations",
             "support_windows", "change_intents", "workflow_changes",
             "provider_pins", "adapters", "bridges", "proof_envelopes",
             "proof_readers"}
DICT_KEYS = {"reserved_identifiers"}


def load_program(docs_dir: str = DOCS) -> dict:
    program: dict = {k: [] for k in LIST_KEYS}
    for k in DICT_KEYS:
        program[k] = {}
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
            elif k in DICT_KEYS and isinstance(v, dict):
                program[k].update(v)
            else:
                meta[k] = v
    program["_meta"] = meta
    return program
