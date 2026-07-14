"""Action Safety Contract + Trajectory Safety Contract (SP0005 §10.3/§10.4,
D-0005-10/07).

An Action Safety Contract declares what must hold for an effect-bearing action:
preconditions, authority requirements, safety invariants, proof obligations,
target/data/trajectory constraints, irreversibility, required control class,
revalidation triggers and post-effect verification. A Trajectory Safety Contract
constrains SEQUENCES: forbidden sequences, allowed transitions, required
checkpoints, authority accumulation and required postconditions — because a safe
action can participate in an unsafe trajectory (INV-0005-03).
"""
from __future__ import annotations

from .model import (Finding, P1, IRREVERSIBILITY, OBLIGATION_TYPES,
                    CONTROL_CLASSES, INVALID_ACTION_SAFETY_CONTRACT,
                    INVALID_TRAJECTORY_CONTRACT)


def validate_action_contract(c: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = c.get("contract_id", "-")
    if not c.get("action_type"):
        out.append(Finding(INVALID_ACTION_SAFETY_CONTRACT, P1, cid,
                           "action contract missing action_type", {}))
    if c.get("irreversibility_class") not in IRREVERSIBILITY:
        out.append(Finding(INVALID_ACTION_SAFETY_CONTRACT, P1, cid,
                           f"invalid irreversibility_class "
                           f"{c.get('irreversibility_class')!r}", {}))
    rc = c.get("required_control_class")
    if rc is not None and rc not in CONTROL_CLASSES:
        out.append(Finding(INVALID_ACTION_SAFETY_CONTRACT, P1, cid,
                           f"invalid required_control_class {rc!r}", {}))
    for po in c.get("proof_obligations", []):
        pt = po if isinstance(po, str) else po.get("obligation_type")
        if pt not in OBLIGATION_TYPES:
            out.append(Finding(INVALID_ACTION_SAFETY_CONTRACT, P1, cid,
                               f"invalid proof obligation type {pt!r}", {}))
    # an effect-bearing / irreversible contract must declare revalidation triggers
    if c.get("irreversibility_class") in ("IRREVERSIBLE", "PARTIALLY_REVERSIBLE") \
            and not c.get("revalidation_triggers"):
        out.append(Finding(INVALID_ACTION_SAFETY_CONTRACT, P1, cid,
                           "irreversible action contract without revalidation "
                           "triggers (AC-0005-025)", {}))
    return out


def validate_trajectory_contract(c: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = c.get("trajectory_contract_id", "-")
    if not c.get("scope"):
        out.append(Finding(INVALID_TRAJECTORY_CONTRACT, P1, cid,
                           "trajectory contract missing scope", {}))
    # allowed_transitions must reference declared state variables
    states = set(c.get("state_variables", []))
    for tr in c.get("allowed_transitions", []):
        for k in ("from", "to"):
            if states and tr.get(k) not in states:
                out.append(Finding(INVALID_TRAJECTORY_CONTRACT, P1, cid,
                                   f"transition {k}={tr.get(k)!r} not a declared "
                                   "state variable", {}))
    return out
