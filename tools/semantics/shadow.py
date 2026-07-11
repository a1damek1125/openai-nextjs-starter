"""Dual-Semantics Shadow Evaluation (SP0002 D-0002-16, §11.8).

Evaluate OLD vs CANDIDATE semantics side-by-side over representative scenarios,
with NO real business-state mutation. Classify each scenario UNCHANGED /
EXPECTED_CHANGED / UNEXPECTED_CHANGED / CANNOT_COMPARE. Unexpected divergence is a
finding (AC-0002-46).
"""
from __future__ import annotations

from typing import Any, Callable

UNCHANGED = "UNCHANGED"
EXPECTED_CHANGED = "EXPECTED_CHANGED"
UNEXPECTED_CHANGED = "UNEXPECTED_CHANGED"
CANNOT_COMPARE = "CANNOT_COMPARE"


def shadow_evaluate(scenarios: list[Any],
                    f_old: Callable[[Any], Any],
                    f_new: Callable[[Any], Any],
                    expected_changed: set | None = None) -> dict[str, Any]:
    expected_changed = expected_changed or set()
    results = []
    counts = {UNCHANGED: 0, EXPECTED_CHANGED: 0, UNEXPECTED_CHANGED: 0,
              CANNOT_COMPARE: 0}
    for i, x in enumerate(scenarios):
        sid = x.get("id", i) if isinstance(x, dict) else i
        try:
            ro = f_old(x)
        except Exception:  # noqa: BLE001 - interpretation-only, no side effects
            ro = _ERR
        try:
            rn = f_new(x)
        except Exception:  # noqa: BLE001
            rn = _ERR
        if ro is _ERR or rn is _ERR:
            cls = CANNOT_COMPARE
        elif ro == rn:
            cls = UNCHANGED
        elif sid in expected_changed:
            cls = EXPECTED_CHANGED
        else:
            cls = UNEXPECTED_CHANGED
        counts[cls] += 1
        results.append({"id": sid, "old": _safe(ro), "new": _safe(rn),
                        "classification": cls})
    return {"results": results, "counts": counts,
            "has_unexpected": counts[UNEXPECTED_CHANGED] > 0,
            "side_effects": False}


class _Err:
    pass


_ERR = _Err()


def _safe(v: Any) -> Any:
    return None if isinstance(v, _Err) else v
