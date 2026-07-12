"""Trajectory Safety Automaton (SP0005 D-0005-08, §11.4, INV-0005-03).

Where a hard trajectory rule is formalizable, it compiles to a DETERMINISTIC
automaton: a state sequence q0,a1,q1,…,an,qn is valid only if every transition
δ(q_{i-1}, a_i) = q_i is allowed. A forbidden transition (e.g. UNVERIFIED_TARGET
→ EFFECT) is a TRAJECTORY_SAFETY_VIOLATION. The automaton OBSERVES safety state;
it is not the Employee run state machine (D-0005-09).
"""
from __future__ import annotations

from .model import Finding, P0, TRAJECTORY_SAFETY_VIOLATION


def build_transition(automaton: dict) -> dict[tuple[str, str], str]:
    """(state, action) -> next_state from the automaton's allowed transitions."""
    delta: dict[tuple[str, str], str] = {}
    for t in automaton.get("transitions", []):
        delta[(t["from"], t["action"])] = t["to"]
    return delta


def validate_run(automaton: dict, states: list[str], actions: list[str]
                 ) -> list[Finding]:
    """Validate a run q0,a1,q1,...,an,qn. `states` = [q0..qn], `actions`=[a1..an].
    A transition not in δ, or a transition to a forbidden state, is a violation."""
    out: list[Finding] = []
    aid = automaton.get("automaton_id", "-")
    delta = build_transition(automaton)
    forbidden = set(tuple(f) for f in automaton.get("forbidden_transitions", []))
    if len(states) != len(actions) + 1:
        out.append(Finding(TRAJECTORY_SAFETY_VIOLATION, P0, aid,
                           "malformed run: |states| must be |actions|+1", {}))
        return out
    for i, a in enumerate(actions):
        q_prev, q_next = states[i], states[i + 1]
        if (q_prev, a) in forbidden:
            out.append(Finding(TRAJECTORY_SAFETY_VIOLATION, P0, aid,
                               f"forbidden transition ({q_prev!r},{a!r})", {}))
            continue
        expected = delta.get((q_prev, a))
        if expected is None:
            out.append(Finding(TRAJECTORY_SAFETY_VIOLATION, P0, aid,
                               f"undefined transition ({q_prev!r},{a!r}) — not in "
                               "the allowed automaton", {}))
        elif expected != q_next:
            out.append(Finding(TRAJECTORY_SAFETY_VIOLATION, P0, aid,
                               f"transition ({q_prev!r},{a!r}) must lead to "
                               f"{expected!r}, got {q_next!r}", {}))
    # required checkpoints must appear before terminal effect
    for cp in automaton.get("required_checkpoints", []):
        if cp not in states:
            out.append(Finding(TRAJECTORY_SAFETY_VIOLATION, P0, aid,
                               f"required checkpoint {cp!r} missing from run", {}))
    return out


def reaches_forbidden(automaton: dict, states: list[str], actions: list[str]
                      ) -> bool:
    return bool(validate_run(automaton, states, actions))
