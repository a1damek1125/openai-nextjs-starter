"""Bounded Migration State-Space Explorer (SP0007 §20.34, D-0007-67).

A standard-library bounded explorer for the small finite models the constitution
cares about: the migration-plan state machine, checkpoint/restart, dual-write
transitions, deprecation/sunset, and the rollback boundary. It enumerates
reachable states, detects invariant violations, returns the SHORTEST
counterexample path (BFS), bounds states/depth, and reports truncation HONESTLY
— a truncated search is INCONCLUSIVE_TRUNCATED, never claimed as proof
(ANALYSIS_LIMIT_REACHED / MODEL_CHECK_LIMIT_REACHED semantics).
"""
from __future__ import annotations

from collections import deque

from .canon import core_hash


def explore(initial, transitions_fn, invariant_fn, *, max_states: int = 100000,
            max_depth: int = 1000) -> dict:
    """BFS over hashable-via-core_hash states. Returns explored count, verdict
    in {HOLDS, VIOLATED, INCONCLUSIVE_TRUNCATED}, shortest counterexample path
    on violation, and honest truncation."""
    seen = {core_hash(initial)}
    queue = deque([(initial, [initial], 0)])
    explored = 0
    truncated = False
    reason = "COMPLETE"
    while queue:
        state, path, depth = queue.popleft()
        explored += 1
        if not invariant_fn(state):
            return {"explored": explored, "verdict": "VIOLATED",
                    "invariant_holds": False, "counterexample": path,
                    "truncated": False, "reason": "COMPLETE"}
        if explored >= max_states:
            truncated, reason = True, "MAX_STATES_REACHED"
            break
        if depth >= max_depth:
            truncated, reason = True, "MAX_DEPTH_REACHED"
            continue
        for nxt in transitions_fn(state):
            h = core_hash(nxt)
            if h not in seen:
                seen.add(h)
                queue.append((nxt, path + [nxt], depth + 1))
    if truncated:
        return {"explored": explored, "verdict": "INCONCLUSIVE_TRUNCATED",
                "invariant_holds": None, "counterexample": None,
                "truncated": True, "reason": reason}
    return {"explored": explored, "verdict": "HOLDS", "invariant_holds": True,
            "counterexample": None, "truncated": False, "reason": "COMPLETE"}


# --- model 1: migration plan state machine (§13.3) ---------------------------
_PLAN_EDGES = {
    "DRAFT": ["REVIEWED"], "REVIEWED": ["APPROVED"],
    "APPROVED": ["EXPANDING"], "EXPANDING": ["MIGRATING", "PAUSED", "FAILED"],
    "MIGRATING": ["VERIFYING", "PAUSED", "FAILED"],
    "VERIFYING": ["CONTRACT_READY", "FAILED", "ROLLBACK_READY"],
    "CONTRACT_READY": ["COMPLETED"], "COMPLETED": [],
    "PAUSED": ["MIGRATING", "FAILED"],
    "FAILED": ["ROLLBACK_READY", "FORWARD_FIX_REQUIRED", "QUARANTINED"],
    "ROLLBACK_READY": ["ROLLING_BACK"], "ROLLING_BACK": ["FAILED", "DRAFT"],
    "FORWARD_FIX_REQUIRED": [], "QUARANTINED": [],
}


def migration_plan_model(*, violating: bool = False):
    """Invariant: COMPLETED is reached only through CONTRACT_READY, and no state
    reaches COMPLETED from FAILED/QUARANTINED."""
    edges = {k: list(v) for k, v in _PLAN_EDGES.items()}
    if violating:
        edges["FAILED"] = edges["FAILED"] + ["COMPLETED"]
    initial = {"state": "DRAFT", "via_contract_ready": False}

    def transitions(s):
        out = []
        for nxt in edges.get(s["state"], []):
            out.append({"state": nxt,
                        "via_contract_ready": s["via_contract_ready"]
                        or nxt == "CONTRACT_READY"})
        return out

    def invariant(s):
        if s["state"] == "COMPLETED":
            return s["via_contract_ready"]
        return True

    return initial, transitions, invariant


# --- model 2: checkpoint / restart (§11.7, D-0007-48) ------------------------
def checkpoint_model(*, violating: bool = False):
    """Invariant: committed batches are never duplicated across a restart;
    processed+pending == total."""
    total = 4
    initial = {"committed": [], "pending": list(range(total)),
               "restarted": False}

    def transitions(s):
        out = []
        if s["pending"]:
            batch = s["pending"][0]
            out.append({"committed": s["committed"] + [batch],
                        "pending": s["pending"][1:],
                        "restarted": s["restarted"]})
            if violating and s["committed"]:
                # a buggy restart re-commits an already-committed batch
                out.append({"committed": s["committed"] + [s["committed"][0]],
                            "pending": s["pending"], "restarted": True})
        if not s["restarted"]:
            out.append(dict(s, restarted=True))   # crash+restart, resumes
        return out

    def invariant(s):
        return len(set(s["committed"])) == len(s["committed"]) \
            and len(s["committed"]) + len(s["pending"]) == total

    return initial, transitions, invariant


# --- model 3: dual-write transition (D-0007-45) ------------------------------
def dual_write_model(*, violating: bool = False):
    """Invariant: old and new stores never diverge without a recorded drift
    marker (divergence must be detected, never silent)."""
    initial = {"old": 0, "new": 0, "drift_detected": False}

    def transitions(s):
        out = []
        if s["old"] < 4:   # bounded write horizon keeps the model finite
            out.append({"old": s["old"] + 1, "new": s["new"] + 1,
                        "drift_detected": s["drift_detected"]})
            # a partial write hits only the old store
            partial = {"old": s["old"] + 1, "new": s["new"],
                       "drift_detected": True}
            if violating:
                partial = dict(partial, drift_detected=False)  # silent divergence
            out.append(partial)
        return out

    def invariant(s):
        return s["old"] == s["new"] or s["drift_detected"]

    return initial, transitions, invariant


# --- model 4: deprecation / sunset (§13.5, D-0007-58/59) ---------------------
def sunset_model(*, violating: bool = False):
    """Invariant: RETIRED is reached only when consumers_migrated and the
    support window is satisfied (deprecation is not removal)."""
    initial = {"state": "ANNOUNCED", "consumers_migrated": False,
               "window_satisfied": False}

    def transitions(s):
        out = []
        if not s["consumers_migrated"]:
            out.append(dict(s, consumers_migrated=True))
        if not s["window_satisfied"]:
            out.append(dict(s, window_satisfied=True))
        if s["state"] == "ANNOUNCED":
            can_retire = s["consumers_migrated"] and s["window_satisfied"]
            if can_retire or violating:
                out.append(dict(s, state="RETIRED"))
        return out

    def invariant(s):
        if s["state"] == "RETIRED":
            return s["consumers_migrated"] and s["window_satisfied"]
        return True

    return initial, transitions, invariant


# --- model 5: rollback boundary (D-0007-51/52) --------------------------------
def rollback_boundary_model(*, violating: bool = False):
    """Invariant: no ROLLING_BACK state exists after the last safe rollback
    point has been crossed."""
    initial = {"position": 0, "boundary": 2, "rolling_back": False}

    def transitions(s):
        out = []
        # migration only advances while not rolling back
        if s["position"] < 4 and not s["rolling_back"]:
            out.append(dict(s, position=s["position"] + 1))
        if not s["rolling_back"] \
                and (s["position"] <= s["boundary"] or violating):
            out.append(dict(s, rolling_back=True))
        return out

    def invariant(s):
        if s["rolling_back"]:
            return s["position"] <= s["boundary"]
        return True

    return initial, transitions, invariant


MODELS = {
    "migration_plan_model": migration_plan_model,
    "checkpoint_model": checkpoint_model,
    "dual_write_model": dual_write_model,
    "sunset_model": sunset_model,
    "rollback_boundary_model": rollback_boundary_model,
}


def run_all_models() -> dict:
    out = {}
    for name in sorted(MODELS):
        initial, t, inv = MODELS[name]()
        out[name] = explore(initial, t, inv)
    return out
