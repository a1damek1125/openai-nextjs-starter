"""Scenario Registry + conditional-dependency compilation (SP0003 D-0003-06/07/08,
§11.3).

A dependency may be scenario-bound: it activates only when a declared, VERSIONED
scenario variable satisfies a DECLARATIVE condition (D-0003-06/INV-0003-10) —
never free-form prose, never executable code. Compiling `Program Hypergraph +
Scenario` yields a Scenario Execution Graph whose active-edge predicate is used by
every downstream analysis (D-0003-08). Scenarios are not full roadmap copies;
they are conditional projections (D-0003-07).
"""
from __future__ import annotations

from typing import Any, Callable

from .model import (Finding, P0, P1, CONDITION_OPERATORS,
                    BLOCKING_DEPENDENCY_STATES, UNKNOWN_SCENARIO_VARIABLE,
                    SCENARIO_CONDITION_ERROR)


def eval_condition(cond: dict, variables: dict) -> tuple[bool, Finding | None]:
    """Evaluate a single declarative condition against scenario variables.
    Unknown variable or bad operator is an ERROR (fail-closed: returns False)."""
    if not cond:
        return True, None
    var = cond.get("variable")
    op = cond.get("operator")
    val = cond.get("value")
    if var not in variables:
        return False, Finding(UNKNOWN_SCENARIO_VARIABLE, P1, var or "-",
                              f"scenario variable {var!r} not declared", {})
    if op not in CONDITION_OPERATORS:
        return False, Finding(SCENARIO_CONDITION_ERROR, P1, var or "-",
                              f"invalid operator {op!r}", {})
    actual = variables[var]
    if op == "EQUALS":
        return actual == val, None
    if op == "NOT_EQUALS":
        return actual != val, None
    if op in ("IN", "NOT_IN"):
        # a malformed IN/NOT_IN (missing / non-list value) must NEVER silently
        # drop a hard dependency — it is a fail-closed ERROR with a diagnostic
        # (red-team SWARM-L Finding 4). Non-list `value` could also trigger
        # unintended substring membership.
        if not isinstance(val, list):
            return False, Finding(SCENARIO_CONDITION_ERROR, P1, var or "-",
                                  f"{op} condition requires a list value, got "
                                  f"{type(val).__name__}", {})
        return (actual in val) if op == "IN" else (actual not in val), None
    return False, Finding(SCENARIO_CONDITION_ERROR, P1, var or "-",
                          f"unhandled operator {op!r}", {})


def scenario_variables(program: dict, scenario_id: str) -> dict:
    for s in program.get("scenarios", []):
        if s.get("scenario_id") == scenario_id:
            return dict(s.get("variables", {}))
    return {}


def active_predicate(program: dict, scenario_id: str
                     ) -> Callable[[dict], bool]:
    """Return an edge-active predicate for the given scenario: an edge is active
    iff its status is blocking AND (it has no scenario_condition OR the condition
    holds under the scenario's variables)."""
    variables = scenario_variables(program, scenario_id)

    def active(edge: dict) -> bool:
        if edge.get("status") not in BLOCKING_DEPENDENCY_STATES:
            return False
        cond = edge.get("scenario_condition")
        if not cond:
            return True
        ok, _ = eval_condition(cond, variables)
        return ok

    return active


def compile_scenario(program: dict, scenario_id: str):
    """Return (active_predicate, findings). Deterministic (D-0003-17): the same
    program + scenario always produces the same active-edge set."""
    findings: list[Finding] = []
    variables = scenario_variables(program, scenario_id)
    known = {s.get("scenario_id") for s in program.get("scenarios", [])}
    if scenario_id not in known:
        findings.append(Finding(SCENARIO_CONDITION_ERROR, P0, scenario_id,
                                f"unknown scenario {scenario_id!r}", {}))
    for e in program.get("hyperedges", []):
        cond = e.get("scenario_condition")
        if cond:
            _, err = eval_condition(cond, variables)
            if err is not None:
                findings.append(err)
    return active_predicate(program, scenario_id), findings
