"""Bounded State-Space Explorer (SP0006 §9.14, §11 formal proofs, D-0006-65,
INV state-safety). A standard-library, deterministic bounded model checker for the
small finite models that back Finalis governance safety arguments: the governed
work state machine, authority monotonicity along a delegation path, budget
conservation, independence-of-approval, and cancellation-barrier containment.

It is HONEST about its limits (D-0006-65, MODEL_CHECK_LIMIT_REACHED): a search that
is truncated by the state or depth bound is NEVER reported as a proof. Only an
exhaustive search that observed no violation yields verdict HOLDS; a truncated
search yields INCONCLUSIVE_TRUNCATED, and a discovered violation yields VIOLATED
together with the shortest counterexample path to the violating state.

Governance tooling only; product runtime must never import it (INV-0006-46). It
opens NO external effect (INV-0006-47).
"""
from __future__ import annotations

from collections import deque
from typing import Callable

from .model import (EXECUTABLE_STATES, NON_EXECUTABLE_STATES)
from .canon import core_hash
from .statemachine import TRANSITIONS

# verdicts (D-0006-65). HOLDS requires an exhaustive, untruncated search.
HOLDS = "HOLDS"
VIOLATED = "VIOLATED"
INCONCLUSIVE_TRUNCATED = "INCONCLUSIVE_TRUNCATED"

# truncation reasons (MODEL_CHECK_LIMIT_REACHED semantics)
COMPLETE = "COMPLETE"
MAX_STATES_REACHED = "MAX_STATES_REACHED"
MAX_DEPTH_REACHED = "MAX_DEPTH_REACHED"


def _key(state) -> str:
    """States are hashed via the canonical core hash so that structurally equal
    states (order-independent dicts) collapse to a single visited node."""
    return core_hash(state)


def _reconstruct(k: str, parent: dict, state_of: dict) -> list:
    path = []
    cur = k
    while cur is not None:
        path.append(state_of[cur])
        cur = parent[cur]
    path.reverse()
    return path


def explore(initial, transitions_fn: Callable, invariant_fn: Callable, *,
            max_states: int = 100000, max_depth: int = 1000) -> dict:
    """Breadth-first exploration of a finite model (AC-0006-184, AC-0006-186).

    ``transitions_fn(state) -> list[state]`` and ``invariant_fn(state) -> bool``.
    BFS guarantees the counterexample is the SHORTEST path (fewest transitions) to
    a violating state (AC-0006-185). Bounded by ``max_states`` (distinct states)
    and ``max_depth`` (transition depth). Truncation is reported honestly: a
    truncated search never returns verdict HOLDS (AC-0006-186, D-0006-65).

    Returns ``{"explored", "invariant_holds", "counterexample", "truncated",
    "reason", "verdict"}``. ``invariant_holds`` is True/False for a conclusive
    search and None ("UNKNOWN-style") when the search was truncated.
    """
    init_key = _key(initial)
    parent: dict = {init_key: None}
    state_of: dict = {init_key: initial}
    depth_of: dict = {init_key: 0}
    visited = {init_key}
    queue = deque([init_key])

    explored = 0
    max_states_hit = False
    max_depth_hit = False

    while queue:
        k = queue.popleft()
        s = state_of[k]
        explored += 1

        # invariant check first — a violation is dispositive and never truncated.
        if not invariant_fn(s):
            return {
                "explored": explored,
                "invariant_holds": False,
                "counterexample": _reconstruct(k, parent, state_of),
                "truncated": False,
                "reason": COMPLETE,
                "verdict": VIOLATED,
            }

        if depth_of[k] >= max_depth:
            # cannot expand deeper; if this node HAS successors we are truncating.
            if transitions_fn(s):
                max_depth_hit = True
            continue

        for nxt in transitions_fn(s):
            nk = _key(nxt)
            if nk in visited:
                continue
            if len(visited) >= max_states:
                max_states_hit = True
                continue
            visited.add(nk)
            parent[nk] = k
            state_of[nk] = nxt
            depth_of[nk] = depth_of[k] + 1
            queue.append(nk)

    truncated = max_states_hit or max_depth_hit
    if truncated:
        reason = MAX_STATES_REACHED if max_states_hit else MAX_DEPTH_REACHED
        # HONESTY: a truncated search is inconclusive, never a proof (D-0006-65).
        return {
            "explored": explored,
            "invariant_holds": None,
            "counterexample": None,
            "truncated": True,
            "reason": reason,
            "verdict": INCONCLUSIVE_TRUNCATED,
        }
    return {
        "explored": explored,
        "invariant_holds": True,
        "counterexample": None,
        "truncated": False,
        "reason": COMPLETE,
        "verdict": HOLDS,
    }


# ---------------------------------------------------------------------------
# Ready-made model builders. Each returns (initial, transitions_fn, invariant_fn)
# so it can be handed straight to explore(). A ``violating`` flag builds a
# deliberately-unsafe variant so tests can obtain a counterexample.
# ---------------------------------------------------------------------------

def work_state_model():
    """Governed work state machine over statemachine.TRANSITIONS (AC-0006-190
    cancellation is covered separately; this covers the never-run/never-resume
    safety of the whole machine).

    A state is ``{"cur": <state>, "prev": <state|None>}``. The invariant forbids
    any edge taken FROM a non-executable state INTO an executable state (a
    terminal/blocked state re-entering execution). Because TRANSITIONS is fail-
    closed and correct, an exhaustive search returns HOLDS.
    """
    initial = {"cur": "DRAFT", "prev": None}

    def transitions_fn(s):
        return [{"cur": nxt, "prev": s["cur"]}
                for nxt in sorted(TRANSITIONS.get(s["cur"], set()))]

    def invariant_fn(s):
        prev, cur = s["prev"], s["cur"]
        if prev is None:
            return True
        # a non-executable (terminal/blocked) state must never enter execution.
        return not (prev in NON_EXECUTABLE_STATES and cur in EXECUTABLE_STATES)

    return initial, transitions_fn, invariant_fn


def authority_monotonicity_model(*, violating: bool = False, root: int = 3,
                                 max_depth: int = 4):
    """Delegation chain where authority is an integer opset magnitude; a child
    lease must be <= its parent (D-0006 §12.1). Invariant: authority is monotone
    non-increasing along the delegation path (AC-0006-187).

    ``violating=True`` lets a child request parent+1 (authority amplification),
    which the explorer catches as a shortest counterexample ``[..., higher]``.
    """
    initial = {"path": [root]}

    def transitions_fn(s):
        path = s["path"]
        if len(path) >= max_depth:
            return []
        last = path[-1]
        children = list(range(0, last + 1))          # attenuated: 0..parent
        if violating:
            children.append(last + 1)                # amplification (unsafe)
        return [{"path": path + [c]} for c in children]

    def invariant_fn(s):
        p = s["path"]
        return all(p[i + 1] <= p[i] for i in range(len(p) - 1))

    return initial, transitions_fn, invariant_fn


def budget_conservation_model(*, violating: bool = False, total: int = 6):
    """Reservation / consumption ledger (D-0006 §12.2). Invariant: at every
    reachable state ``consumed + reserved <= total`` (AC-0006-188).

    Actions: reserve one unit, or consume one reserved unit. The safe guard keeps
    reservations within ``total``; ``violating=True`` relaxes the guard so an
    over-commitment (``consumed + reserved > total``) becomes reachable.
    """
    initial = {"reserved": 0, "consumed": 0, "total": total}

    def transitions_fn(s):
        r, c, t = s["reserved"], s["consumed"], s["total"]
        outs = []
        limit = t if not violating else t + 2        # unsafe variant over-reserves
        if r + c < limit:
            outs.append({"reserved": r + 1, "consumed": c, "total": t})
        if r > 0:
            outs.append({"reserved": r - 1, "consumed": c + 1, "total": t})
        return outs

    def invariant_fn(s):
        return s["consumed"] + s["reserved"] <= s["total"]

    return initial, transitions_fn, invariant_fn


def no_self_approval_model(*, violating: bool = False):
    """Role-assignment model for independence of approval (D-0006 §12, no self-
    approval). Invariant: when independence is required, ``approver != proposer``
    (AC-0006-189).

    Safe variant only ever assigns an approver distinct from the proposer;
    ``violating=True`` also offers the proposer as a candidate approver.
    """
    proposer = "u1"
    candidates = ["u2", "u3"] + (["u1"] if violating else [])
    initial = {"proposer": proposer, "approver": None,
               "independence_required": True}

    def transitions_fn(s):
        if s["approver"] is not None:
            return []
        return [{"proposer": s["proposer"], "approver": a,
                 "independence_required": s["independence_required"]}
                for a in candidates]

    def invariant_fn(s):
        if s["independence_required"] and s["approver"] is not None:
            return s["approver"] != s["proposer"]
        return True

    return initial, transitions_fn, invariant_fn


def cancellation_model(*, violating: bool = False, max_actions: int = 2):
    """Cancellation-barrier containment (§13.5, AC-0006-190). Once the barrier is
    NEW_ACTIONS_BLOCKED, no new action state may be entered. Invariant: no action
    was started after the block.

    Safe variant refuses to start a new action while blocked; ``violating=True``
    allows it, setting the ``started_after_block`` flag the invariant forbids.
    """
    initial = {"barrier": "OPEN", "actions_started": 0,
               "started_after_block": False}

    def transitions_fn(s):
        outs = []
        b = s["barrier"]
        started = s["actions_started"]
        flag = s["started_after_block"]
        # start a new action
        if started < max_actions:
            if b == "OPEN":
                outs.append({"barrier": b, "actions_started": started + 1,
                             "started_after_block": flag})
            elif violating:      # unsafe: start an action while blocked
                outs.append({"barrier": b, "actions_started": started + 1,
                             "started_after_block": True})
        # engage the cancellation barrier
        if b == "OPEN":
            outs.append({"barrier": "NEW_ACTIONS_BLOCKED",
                         "actions_started": started,
                         "started_after_block": flag})
        return outs

    def invariant_fn(s):
        return not s["started_after_block"]

    return initial, transitions_fn, invariant_fn


# deterministic ordering of the model suite
_MODELS = (
    ("work_state_model", work_state_model),
    ("authority_monotonicity_model", authority_monotonicity_model),
    ("budget_conservation_model", budget_conservation_model),
    ("no_self_approval_model", no_self_approval_model),
    ("cancellation_model", cancellation_model),
)


def run_all_models(*, max_states: int = 100000, max_depth: int = 1000) -> dict:
    """Run every safe model builder through explore() and return a deterministic
    ``{model_name: result}`` summary (AC-0006-184..190)."""
    summary: dict = {}
    for name, builder in _MODELS:
        initial, transitions_fn, invariant_fn = builder()
        summary[name] = explore(initial, transitions_fn, invariant_fn,
                                max_states=max_states, max_depth=max_depth)
    return summary
