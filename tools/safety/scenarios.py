"""Safety Scenario Compiler (SP0005 D-0005-63..69, §11.7, INV-0005-11).

Combines hazard × attack × initial state × authority × tools × memory × channel ×
target × context mutation × provider failure × human-oversight into executable
safety cases. Combinatorial generation is BOUNDED — pairwise / risk-prioritized /
known-dangerous / adversarial with explicit coverage reporting, never the full
Cartesian product (D-0005-64, AC-0005-154). Every executable scenario carries a
verification predicate grounded in OBSERVABLE evidence (D-0005-65/66,
AC-0005-155/156). A generated scenario never becomes canonical policy by itself
(D-0005-67).
"""
from __future__ import annotations

from itertools import combinations

from .model import Finding, P1, INVALID_SAFETY_SCHEMA

# oracle kinds acceptable for a scenario's verification predicate (observable)
OBSERVABLE_ORACLES = {"ENVIRONMENT_STATE", "ARTIFACT_CRYPTO_EVIDENCE",
                      "INDEPENDENT_FORMAL_RULE_CHECKER", "EFFECT_LEDGER",
                      "DATABASE_STATE", "TOOL_CALL_STATE", "AUDIT_EVENT"}


def validate_scenario(s: dict) -> list[Finding]:
    out: list[Finding] = []
    sid = s.get("scenario_id", "-")
    if not s.get("verification_predicate"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "executable scenario has no verification predicate "
                           "(AC-0005-155)", {}))
    if "initial_state" not in s:
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "scenario missing initial_state", {}))
    if not s.get("expected_safety_property"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "scenario missing expected_safety_property", {}))
    # verification must use observable evidence, not agent self-report
    oracle = s.get("verification_oracle")
    if oracle is not None and oracle not in OBSERVABLE_ORACLES:
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           f"verification oracle {oracle!r} is not observable "
                           "(AC-0005-156)", {}))
    # effectful scenarios default to NO_EXTERNAL_EFFECT
    if s.get("effect_mode", "NO_EXTERNAL_EFFECT") != "NO_EXTERNAL_EFFECT":
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "scenario declares an external effect mode — SP0005 "
                           "opens no effects (INV-0005-27)", {}))
    return out


def pairwise(dimensions: dict[str, list]) -> list[dict]:
    """Bounded 2-wise (pairwise) coverage over named dimensions. Guarantees every
    pair of values across two dimensions appears in at least one case, without the
    full Cartesian product (D-0005-64)."""
    keys = sorted(dimensions)
    if not keys:
        return []
    # greedy pairwise: cover all value-pairs across dimension pairs
    required_pairs = set()
    for ki, kj in combinations(keys, 2):
        for vi in dimensions[ki]:
            for vj in dimensions[kj]:
                required_pairs.add((ki, vi, kj, vj))
    cases: list[dict] = []
    # simple greedy: iterate a bounded product of first values + rotate
    import itertools
    all_cases = itertools.product(*(dimensions[k] for k in keys))
    for combo in all_cases:
        case = dict(zip(keys, combo))
        covers = set()
        for ki, kj in combinations(keys, 2):
            covers.add((ki, case[ki], kj, case[kj]))
        new = covers - set()
        if covers & required_pairs:
            cases.append(case)
            required_pairs -= covers
        if not required_pairs:
            break
    return cases


def coverage_report(scenarios: list[dict]) -> dict:
    """Multi-dimensional coverage — never one unexplained percentage (D-0005-69)."""
    dims = {}
    for key in ("hazard_refs", "authority_state", "attack_method", "channel",
                "provider_failures"):
        vals = set()
        for s in scenarios:
            v = s.get(key)
            if isinstance(v, list):
                vals.update(str(x) for x in v)
            elif v is not None:
                vals.add(str(v))
        dims[key + "_covered"] = len(vals)
    dims["scenario_count"] = len(scenarios)
    return dims
