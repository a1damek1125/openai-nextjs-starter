"""Assemble the governed-work program from docs/governed_work artifacts into one
dict (mirrors the SP0003/0004/0005 loader pattern)."""
from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "governed_work")

# artifact files that contribute list-keyed content merged into one program
FILES = (
    "FINALIS_WORK_ORDERS.json",
    "FINALIS_CANDIDATE_INTENTS.json",
    "FINALIS_EXECUTION_IDENTITIES.json",
    "FINALIS_CAPABILITY_LEASES.json",
    "FINALIS_DELEGATION_EDGES.json",
    "FINALIS_BUDGET_LEDGERS.json",
    "FINALIS_APPROVAL_TOKENS.json",
    "FINALIS_APPROVAL_TOPOLOGY.json",
    "FINALIS_OUTCOME_CONTRACTS.json",
    "FINALIS_OUTCOME_EVIDENCE.json",
    "FINALIS_OUTCOME_DEFEATERS.json",
    "FINALIS_RECURRING_WORK_CONTRACTS.json",
    "FINALIS_EXECUTION_PLANS.json",
    "FINALIS_ACCOUNTABILITY_CHAINS.json",
)

LIST_KEYS = {"work_orders", "candidate_intents", "execution_identities",
             "leases", "delegation_edges", "budget_ledgers", "approval_tokens",
             "approval_topologies", "outcome_contracts", "outcome_evidence",
             "outcome_defeaters", "recurring_contracts", "plans",
             "accountability_chains", "reassignments", "identities"}


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
