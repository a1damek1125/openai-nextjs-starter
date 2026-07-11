"""ScheduleSolverAdapter boundary (SP0003 D-0003 §5.11/§5.12, AC-0003-89/90).

Finalis OWNS the program model; the solver is replaceable. SP0003 does NOT make
OR-Tools / NetworkX / any optimization library a mandatory dependency (§7 non-goal,
AC-0003-90). This module defines the adapter contract and ships a deterministic,
stdlib-only greedy reference solver. A greedy advisory schedule never claims
optimality (§23): exact RCPSP is NP-hard.
"""
from __future__ import annotations

from typing import Protocol

from .frontier import safe_parallel_batches
from .evidence import evidence_derived_complete_set


class ScheduleSolverAdapter(Protocol):
    """Replaceable boundary. An external backend (e.g. OR-Tools) may implement
    this later without SP0003 depending on it."""

    name: str
    optimal: bool

    def schedule(self, program: dict, *, scenario_id: str = "BASELINE") -> dict:
        ...


class GreedyReferenceSolver:
    """Deterministic, stdlib-only, ADVISORY (never claims optimality)."""

    name = "greedy-reference"
    optimal = False

    def schedule(self, program: dict, *, scenario_id: str = "BASELINE",
                 gate_state: dict | None = None) -> dict:
        from .scenario import compile_scenario
        active, _ = compile_scenario(program, scenario_id)
        complete = set(evidence_derived_complete_set(program))
        rounds: list[list[str]] = []
        # simulate wave scheduling: each round = a safe parallel batch of ready
        # nodes; mark them complete and repeat (bounded by node count).
        guard = 0
        prog = program
        done = set(complete)
        max_rounds = len(program.get("nodes", [])) + 1
        while guard < max_rounds:
            guard += 1
            batches = safe_parallel_batches(prog, complete=done,
                                            gate_state=gate_state, active=active)
            if not batches or not batches[0]:
                break
            wave = batches[0]
            rounds.append(sorted(wave))
            done |= set(wave)
        return {"solver": self.name, "optimal": self.optimal,
                "advisory": True, "scenario": scenario_id,
                "waves": rounds, "wave_count": len(rounds)}


DEFAULT_SOLVER = GreedyReferenceSolver()
