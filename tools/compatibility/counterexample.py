"""Minimal Counterexample Generator (SP0007 §11.4, D-0007-15, AC-0007-073).

An INCOMPATIBLE verdict must ship a concrete witness a human can read, not a
bare boolean (D-0007-15). `minimize` delta-debugs a failing payload down to a
local minimum: keys are probed for removal in DETERMINISTIC sorted order —
shallow dict keys first, then nested dict keys, then list elements — and a
removal is kept only while the failure persists. Probing is bounded
(MAX_PROBES) and the result reports `truncated` honestly rather than
pretending minimality. A probe that raises never justifies a removal
(fail-closed). Governance tooling only; no external effect (INV-0007-47).
"""
from __future__ import annotations

import copy

from .canon import core_hash

# hard bound on predicate evaluations — guarantees termination (AC-0007-073)
MAX_PROBES = 10000


def _removal_paths(obj, prefix: tuple = ()) -> list[tuple]:
    """Every removable path in obj as a tuple of ("key", k) / ("index", i)
    steps, discovered in sorted key order."""
    paths: list[tuple] = []
    if isinstance(obj, dict):
        keys = sorted(obj, key=str)
        for k in keys:
            paths.append(prefix + (("key", k),))
        for k in keys:
            paths.extend(_removal_paths(obj[k], prefix + (("key", k),)))
    elif isinstance(obj, list):
        for i in range(len(obj)):
            paths.append(prefix + (("index", i),))
        for i, v in enumerate(obj):
            paths.extend(_removal_paths(v, prefix + (("index", i),)))
    return paths


def _path_sort_key(path: tuple) -> tuple:
    """Deterministic probe order: shallow before deep; at equal depth dict-key
    removals before list-element removals, then lexicographic."""
    return (len(path), tuple((0, str(v)) if tag == "key" else (1, "%012d" % v)
                             for tag, v in path))


def _remove(root, path: tuple):
    """A deep copy of root with the element at path removed, or None if the
    path no longer resolves."""
    new = copy.deepcopy(root)
    node = new
    for tag, k in path[:-1]:
        if tag == "key":
            if not isinstance(node, dict) or k not in node:
                return None
            node = node[k]
        else:
            if not isinstance(node, list) or k >= len(node):
                return None
            node = node[k]
    tag, k = path[-1]
    if tag == "key":
        if not isinstance(node, dict) or k not in node:
            return None
        del node[k]
    else:
        if not isinstance(node, list) or k >= len(node):
            return None
        del node[k]
    return new


def _format_path(path: tuple) -> str:
    parts: list[str] = []
    for tag, k in path:
        if tag == "key":
            parts.append(("." if parts else "") + str(k))
        else:
            parts.append(f"[{k}]")
    return "".join(parts)


def minimize(failing_payload: dict, still_fails) -> dict:
    """Deterministic delta-debugging (D-0007-15): shrink failing_payload to a
    local minimum under still_fails(payload) -> bool (True while the failure
    persists). Returns {"original", "minimal_witness", "removed_paths",
    "reduction_steps", "truncated"}; reduction_steps counts predicate probes
    (bounded by MAX_PROBES), removed_paths the removals that were kept. The
    predicate receives a deep copy each probe, so a mutating predicate cannot
    corrupt the search; a raising probe counts as NOT-failing (fail-closed)."""
    original = copy.deepcopy(failing_payload)
    probes = 0
    truncated = False

    def fails(candidate) -> bool:
        nonlocal probes
        probes += 1
        try:
            return bool(still_fails(copy.deepcopy(candidate)))
        except Exception:
            return False

    current = copy.deepcopy(original)
    removed: list[str] = []
    if not fails(current):
        # the payload does not actually fail — nothing to minimize
        return {"original": original, "minimal_witness": current,
                "removed_paths": removed, "reduction_steps": probes,
                "truncated": False}

    progress = True
    while progress and not truncated:
        progress = False
        for path in sorted(_removal_paths(current), key=_path_sort_key):
            if probes >= MAX_PROBES:
                truncated = True
                break
            candidate = _remove(current, path)
            if candidate is None:
                continue
            if fails(candidate):
                current = candidate
                removed.append(_format_path(path))
                progress = True
                break  # structure changed: re-enumerate deterministically

    return {"original": original, "minimal_witness": current,
            "removed_paths": removed, "reduction_steps": probes,
            "truncated": truncated}


def witness_record(claim_id: str, dimension: str, reason_kind: str,
                   minimal: dict) -> dict:
    """Package a minimized counterexample as the witness attached to an
    INCOMPATIBLE claim (D-0007-15, AC-0007-073). `minimal` is the dict
    returned by minimize(). The witness_hash binds the record to its content
    (AC-0007-194); None when the payload is not canonically serializable."""
    witness = minimal.get("minimal_witness")
    try:
        witness_hash = core_hash({"claim_id": claim_id,
                                  "failed_dimension": dimension,
                                  "reason_code": reason_kind,
                                  "minimal_witness": witness})
    except (TypeError, ValueError):
        witness_hash = None
    return {"claim_id": claim_id,
            "failed_dimension": dimension,
            "reason_code": reason_kind,
            "original": minimal.get("original"),
            "minimal_witness": witness,
            "reduction_steps": minimal.get("reduction_steps", 0),
            "truncated": minimal.get("truncated", False),
            "witness_hash": witness_hash}
