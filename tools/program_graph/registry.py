"""Canonical Program Registry + schema validation (SP0003 §10, D-0003-04/15/34).

Validates program nodes and prerequisite hyperedges at the schema level and
enforces the hard evidence invariants that do NOT depend on graph compilation:

  * every node id is unique and well-typed (AC-0003-05/06);
  * every hyperedge references existing nodes, is not self-referential, and
    carries a valid logic/type/status (AC-0003-08);
  * SP numbering NEVER implies a dependency — only explicit hyperedges do
    (D-0003-04, INV-0003-04): there is simply no numbering-derived edge here;
  * an ACTIVE hard dependency MUST carry rationale, failure-if-bypassed and
    evidence, else it is UNPROVEN_HARD_DEPENDENCY (AC-0003-12/13/14, INV-0003-02);
  * an LLM/model-admitted dependency may never be ACTIVE on its own
    (AC-0003-70, INV-0003-02) — LLMs propose, they do not activate.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .canon import hash_obj
from .model import (Finding, Report, P0, P1, P2, NODE_TYPES, NODE_STATES,
                    STATUS_SOURCES, DEPENDENCY_LOGIC, DEPENDENCY_TYPES,
                    DEPENDENCY_STATES, BLOCKING_DEPENDENCY_STATES,
                    INVALID_PROGRAM_SCHEMA, UNKNOWN_NODE, DUPLICATE_NODE,
                    INVALID_HYPEREDGE, SELF_DEPENDENCY, UNPROVEN_HARD_DEPENDENCY,
                    LLM_DEPENDENCY_ACTIVATION)

# An ACTIVE hard dependency must be admitted by a HUMAN / architecture authority.
# This is an ALLOWLIST (not a model-name denylist): any other provenance — a model
# id like "gpt-4o", "o3", "claude-opus", an "LLM-assisted" note, a list, or a
# missing value — fails the gate, so no LLM/model admission can slip through by
# renaming (red-team SWARM-L Finding 1, INV-0003-02).
HUMAN_ADMISSION = {"ARCHITECTURE_REVIEW", "HUMAN_REVIEW", "PROGRAM_ARCHITECT",
                   "ROADMAP_LOCK", "AUDIT", "HUMAN", "ARCHITECTURE_BOARD"}


def load_program(path: str) -> dict:
    """Load the canonical program object from a JSON file."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def node_index(program: dict) -> dict[str, dict]:
    return {n["node_id"]: n for n in program.get("nodes", [])}


def validate_nodes(program: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for n in program.get("nodes", []):
        nid = n.get("node_id")
        if not nid:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P0, "-",
                               "node missing node_id", {}))
            continue
        if nid in seen:
            out.append(Finding(DUPLICATE_NODE, P0, nid,
                               "duplicate node_id", {}))
        seen.add(nid)
        if n.get("node_type") not in NODE_TYPES:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, nid,
                               f"invalid node_type {n.get('node_type')!r}", {}))
        if n.get("status") not in NODE_STATES:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, nid,
                               f"invalid status {n.get('status')!r}", {}))
        src = n.get("status_source")
        if src is not None and src not in STATUS_SOURCES:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, nid,
                               f"invalid status_source {src!r}", {}))
    return out


def validate_hyperedges(program: dict) -> list[Finding]:
    out: list[Finding] = []
    nodes = set(node_index(program))
    seen_ids: set[str] = set()
    for e in program.get("hyperedges", []):
        eid = e.get("dependency_id", "-")
        if eid in seen_ids:
            out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                               "duplicate dependency_id", {}))
        seen_ids.add(eid)
        head = e.get("head_node")
        tails = e.get("tail_nodes", [])
        if head not in nodes:
            out.append(Finding(UNKNOWN_NODE, P0, eid,
                               f"head_node {head!r} not a known node", {}))
        if not tails:
            out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                               "hyperedge has no tail_nodes", {}))
        for t in tails:
            if t not in nodes:
                out.append(Finding(UNKNOWN_NODE, P0, eid,
                                   f"tail_node {t!r} not a known node", {}))
            if t == head:
                out.append(Finding(SELF_DEPENDENCY, P0, eid,
                                   f"node {t!r} depends on itself", {}))
        logic = e.get("logic")
        if logic not in DEPENDENCY_LOGIC:
            out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                               f"invalid logic {logic!r}", {}))
        if logic == "AT_LEAST_K_OF_N":
            k = e.get("threshold_k")
            n_distinct = len(set(tails))
            # range-check against DISTINCT tails (duplicates cannot pad a
            # threshold, red-team SWARM-L Finding 2)
            if not isinstance(k, int) or k < 1 or k > n_distinct:
                out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                                   f"threshold_k {k!r} invalid for {n_distinct} "
                                   "distinct tails", {}))
            if len(tails) != n_distinct:
                out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                                   "duplicate tail_nodes in threshold hyperedge",
                                   {}))
        if e.get("dependency_type") not in DEPENDENCY_TYPES:
            out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                               f"invalid dependency_type "
                               f"{e.get('dependency_type')!r}", {}))
        if e.get("status") not in DEPENDENCY_STATES:
            out.append(Finding(INVALID_HYPEREDGE, P1, eid,
                               f"invalid dependency status {e.get('status')!r}",
                               {}))
    return out


def validate_active_evidence(program: dict) -> list[Finding]:
    """INV-0003-02: no ACTIVE hard dependency without evidence, rationale and a
    declared failure-if-bypassed; and no LLM-admitted ACTIVE dependency."""
    out: list[Finding] = []
    for e in program.get("hyperedges", []):
        if e.get("status") not in BLOCKING_DEPENDENCY_STATES:
            continue
        eid = e.get("dependency_id", "-")
        if not e.get("reason"):
            out.append(Finding(UNPROVEN_HARD_DEPENDENCY, P0, eid,
                               "ACTIVE hard dependency lacks rationale "
                               "(AC-0003-12)", {}))
        if not e.get("failure_if_bypassed"):
            out.append(Finding(UNPROVEN_HARD_DEPENDENCY, P0, eid,
                               "ACTIVE hard dependency lacks failure_if_bypassed "
                               "(AC-0003-14)", {}))
        if not e.get("evidence_refs"):
            out.append(Finding(UNPROVEN_HARD_DEPENDENCY, P0, eid,
                               "ACTIVE hard dependency lacks evidence_refs "
                               "(AC-0003-13)", {}))
        admitted = e.get("admitted_by")
        norm = admitted.strip().upper() if isinstance(admitted, str) else None
        if norm not in HUMAN_ADMISSION:
            out.append(Finding(LLM_DEPENDENCY_ACTIVATION, P0, eid,
                               f"dependency admitted_by={admitted!r} is not a "
                               "recognized human/architecture authority; an "
                               "ACTIVE hard dependency cannot be admitted by an "
                               "LLM/model or unattributed source (AC-0003-70)",
                               {}))
    return out


def validate_registry(program: dict, *, check_evidence: bool = True) -> Report:
    rep = Report()
    rep.extend(validate_nodes(program))
    rep.extend(validate_hyperedges(program))
    if check_evidence:
        rep.extend(validate_active_evidence(program))
    rep.metrics["node_count"] = len(program.get("nodes", []))
    rep.metrics["hyperedge_count"] = len(program.get("hyperedges", []))
    return rep


def registry_hash(program: dict) -> str:
    """Deterministic hash over nodes (ordered by node_id) — canonical identity of
    the program structure, excluding derived analytics (INV-0003-17)."""
    nodes = sorted(program.get("nodes", []), key=lambda n: n["node_id"])
    return hash_obj(nodes)
