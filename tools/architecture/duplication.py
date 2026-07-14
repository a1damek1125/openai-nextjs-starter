"""Semantic Duplication Candidate Detector (SP0001 D-0001-11, §11.7).

Deterministic advisory scoring only. A high score means REVIEW CANDIDATE, never
DUPLICATION PROVEN (INV-0001-07: an LLM/score is never sole hard-gate evidence).
At current capability scale exact set comparison (Jaccard) is preferred over
approximate MinHash/LSH (§11.7).
"""
from __future__ import annotations

from typing import Any

# weights must sum to 1.0 (SP0001 §11.7)
WEIGHTS = {"routes": 0.25, "tables": 0.25, "perms": 0.15,
           "deps": 0.20, "lexical": 0.15}
DEFAULT_THRESHOLD = 0.55


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tokens(text: str) -> set[str]:
    import re
    return set(t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2)


def _neighbors(cap_id: str, edges: list[list[str]]) -> set[str]:
    out: set[str] = set()
    for frm, to in edges:
        if frm == cap_id:
            out.add(to)
        if to == cap_id:
            out.add(frm)
    return out


def similarity(a: dict, b: dict, edges: list[list[str]]) -> dict[str, Any]:
    ra, rb = set(a["route_namespaces"]), set(b["route_namespaces"])
    ta, tb = set(a["table_namespaces"]), set(b["table_namespaces"])
    pa, pb = set(a["permission_namespaces"]), set(b["permission_namespaces"])
    da = _neighbors(a["capability_id"], edges)
    db = _neighbors(b["capability_id"], edges)
    la = _tokens(a["display_name"] + " " + a["purpose"])
    lb = _tokens(b["display_name"] + " " + b["purpose"])
    parts = {
        "routes": _jaccard(ra, rb),
        "tables": _jaccard(ta, tb),
        "perms": _jaccard(pa, pb),
        "deps": _jaccard(da, db),
        "lexical": _jaccard(la, lb),
    }
    score = round(sum(WEIGHTS[k] * parts[k] for k in WEIGHTS), 6)
    return {"a": a["capability_id"], "b": b["capability_id"],
            "score": score, "components": parts}


def candidates(twin: dict, edges: list[list[str]] | None = None,
               threshold: float = DEFAULT_THRESHOLD) -> list[dict[str, Any]]:
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "weights must sum to 1"
    caps = twin["capabilities"]
    edges = edges or [list(e) for e in
                      twin.get("dependency_baseline", {}).get("edges", [])]
    out: list[dict[str, Any]] = []
    for i in range(len(caps)):
        for j in range(i + 1, len(caps)):
            s = similarity(caps[i], caps[j], edges)
            if s["score"] >= threshold:
                s["verdict"] = "DUPLICATION_CANDIDATE"   # NOT proven
                out.append(s)
    return sorted(out, key=lambda s: (-s["score"], s["a"], s["b"]))
