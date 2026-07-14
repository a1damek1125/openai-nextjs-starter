"""Readiness Engine (SP0003 D-0003-16/17, §11).

Ready(v) = ReadyPrereq(v) AND RequiredGatesPass(v)

Prerequisite readiness evaluates the hypergraph AND/OR/threshold semantics under
the compiled scenario; gate readiness requires every binding hard gate to pass.
Resource conflicts are NOT applied here — they are a scheduling concern, applied
when forming a safe parallel batch (frontier.py), because absence of a hard edge
does not prove safe parallelism (INV-0003-05) and a resource conflict is not hard
precedence (INV-0003-06).
"""
from __future__ import annotations

from typing import Callable

from .hypergraph import default_active, prerequisite_ready
from .gates import required_gates_pass
from .evidence import evidence_derived_complete_set


def ready_nodes(program: dict, *, complete: set[str] | None = None,
                gate_state: dict | None = None,
                active: Callable[[dict], bool] = default_active) -> set[str]:
    """Nodes that are Ready: prerequisite-satisfied AND gate-passing, and not
    themselves already complete/in-progress."""
    complete = evidence_derived_complete_set(program) if complete is None \
        else complete
    gate_state = gate_state or {}
    out: set[str] = set()
    for n in program.get("nodes", []):
        nid = n["node_id"]
        if nid in complete:
            continue
        if n.get("status") in ("IN_PROGRESS", "SUPERSEDED", "CANCELLED"):
            continue
        if prerequisite_ready(program, nid, complete, active) and \
                required_gates_pass(program, nid, gate_state):
            out.add(nid)
    return out


def prerequisite_ready_nodes(program: dict, *, complete: set[str] | None = None,
                             active: Callable[[dict], bool] = default_active
                             ) -> set[str]:
    """Prerequisite-only readiness (ignores gates) — the RAW ready set before
    gate + resource filtering."""
    complete = evidence_derived_complete_set(program) if complete is None \
        else complete
    out: set[str] = set()
    for n in program.get("nodes", []):
        nid = n["node_id"]
        if nid in complete:
            continue
        if prerequisite_ready(program, nid, complete, active):
            out.add(nid)
    return out
