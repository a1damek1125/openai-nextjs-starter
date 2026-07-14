"""Gate Graph — Boolean hard gates kept SEPARATE from dependency logic
(SP0003 D-0003-12, §11 readiness, INV-0003-09/12).

A gate is Boolean: no probability or criticality score can override it
(INV-0003-12). Global safety/governance/human-review gates are SCENARIO-INVARIANT
— a scenario selection can never deactivate them (INV-0003-09, §17.1). Gates guard
nodes; a node is gate-ready only when every required gate that binds it passes.
"""
from __future__ import annotations

from typing import Callable

from .model import (Finding, P0, P1, GATE_TYPES, GLOBAL_GATE_TYPES,
                    GATE_BYPASS, GATE_BYPASS_RISK, INVALID_PROGRAM_SCHEMA)


def gate_index(program: dict) -> dict[str, dict]:
    return {g["gate_id"]: g for g in program.get("gates", [])}


def validate_gates(program: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for g in program.get("gates", []):
        gid = g.get("gate_id")
        if not gid:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, "-",
                               "gate missing gate_id", {}))
            continue
        if gid in seen:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, gid,
                               "duplicate gate_id", {}))
        seen.add(gid)
        if g.get("gate_type") not in GATE_TYPES:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1, gid,
                               f"invalid gate_type {g.get('gate_type')!r}", {}))
    return out


def validate_gate_bindings(program: dict) -> list[Finding]:
    """gate_bindings reference real nodes and real gates (red-team SWARM-L
    Finding 3 — bindings were previously unchecked and un-hashed)."""
    out: list[Finding] = []
    nodes = {n["node_id"] for n in program.get("nodes", [])}
    gids = set(gate_index(program))
    for b in program.get("gate_bindings", []):
        if b.get("node_id") not in nodes:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1,
                               str(b.get("gate_id", "-")),
                               f"gate_binding references unknown node "
                               f"{b.get('node_id')!r}", {}))
        if b.get("gate_id") not in gids:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1,
                               str(b.get("node_id", "-")),
                               f"gate_binding references unknown gate "
                               f"{b.get('gate_id')!r}", {}))
    return out


def required_gates_for(program: dict, node_id: str) -> list[dict]:
    """Gates that bind (guard) a node, via `gate_bindings` or a gate's
    `guarded_nodes` list."""
    gidx = gate_index(program)
    out: list[dict] = []
    for b in program.get("gate_bindings", []):
        if b.get("node_id") == node_id and b.get("gate_id") in gidx:
            out.append(gidx[b["gate_id"]])
    for g in program.get("gates", []):
        if node_id in g.get("guarded_nodes", []):
            out.append(g)
    # dedupe by gate_id, keep deterministic order
    dedup = {g["gate_id"]: g for g in out}
    return [dedup[k] for k in sorted(dedup)]


def gate_passes(gate: dict, gate_state: dict) -> bool:
    """A gate passes iff its recorded state is PASS. Unknown/absent = fail-closed
    (never silently pass, §18 no silent fallback to PASS)."""
    return gate_state.get(gate["gate_id"]) == "PASS"


def required_gates_pass(program: dict, node_id: str, gate_state: dict) -> bool:
    return all(gate_passes(g, gate_state)
               for g in required_gates_for(program, node_id))


def scenario_invariant_gates(program: dict) -> list[dict]:
    """Global gates that a scenario cannot deactivate (INV-0003-09)."""
    return [g for g in program.get("gates", [])
            if g.get("gate_type") in GLOBAL_GATE_TYPES
            or g.get("scenario_invariant") is True]


def detect_gate_bypass(program: dict, active) -> list[Finding]:
    """A scenario-bound dependency must NOT be the only thing standing between a
    node and a global safety gate: global gates must bind their node regardless
    of scenario. If a global gate is marked scenario_condition-bound, that is a
    GATE_BYPASS (INV-0003-09/§17.1)."""
    out: list[Finding] = []
    for g in program.get("gates", []):
        if g.get("gate_type") in GLOBAL_GATE_TYPES and g.get("scenario_condition"):
            out.append(Finding(GATE_BYPASS, P0, g.get("gate_id", "-"),
                               "global gate is scenario-bound and could be "
                               "bypassed by scenario selection", {}))
    return out
