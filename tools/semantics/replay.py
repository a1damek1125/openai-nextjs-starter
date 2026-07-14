"""Historical Semantic Replay (SP0002 D-0002-17, §11.9).

Replay canonical historical fixtures through OLD and CANDIDATE semantics and
compute deltas. Never replays real external effects — interpretation only. Every
UNEXPECTED (undocumented) divergence is a finding (AC-0002-45/46).
"""
from __future__ import annotations

from typing import Any, Callable

from .model import Finding, P1, HISTORICAL_REPLAY_DIVERGENCE


def replay(fixtures: list[dict], f_old: Callable[[dict], Any],
           f_new: Callable[[dict], Any],
           documented_deltas: dict | None = None) -> dict[str, Any]:
    """fixtures: historical records (with an 'id'). documented_deltas: {id: new_val}
    expected/allowed differences. Returns per-fixture delta + findings."""
    documented_deltas = documented_deltas or {}
    rows = []
    findings: list[Finding] = []
    for fx in fixtures:
        fid = fx.get("id")
        ro, rn = f_old(fx), f_new(fx)
        if ro == rn:
            rows.append({"id": fid, "delta": None, "status": "REPRODUCED"})
            continue
        if fid in documented_deltas and documented_deltas[fid] == rn:
            rows.append({"id": fid, "delta": {"old": ro, "new": rn},
                         "status": "DOCUMENTED_DELTA"})
        else:
            rows.append({"id": fid, "delta": {"old": ro, "new": rn},
                         "status": "UNEXPLAINED_DIVERGENCE"})
            findings.append(Finding(HISTORICAL_REPLAY_DIVERGENCE, P1, str(fid),
                                    f"fixture {fid}: {ro} -> {rn} undocumented",
                                    {"id": fid, "old": ro, "new": rn}))
    return {"rows": rows, "findings": [f.to_dict() for f in findings],
            "unexplained": sum(1 for r in rows
                               if r["status"] == "UNEXPLAINED_DIVERGENCE"),
            "findings_objs": findings}
