"""Behavioral witnesses (SP0008 §witnesses, D-0008-31/32).

A witness is a concrete, source-grounded behavioral fact about a surface: a case
it accepts (POSITIVE), rejects (NEGATIVE), a failure path (FAILURE), a
metamorphic relation, or a tenant/authority-enforcement observation. Witnesses
are derived from real artifacts — a route's raise HTTPException(status, detail)
is a grounded NEGATIVE/FAILURE witness; a test that exercises the surface is a
POSITIVE/CONFIRMED witness. An LLM may only PROPOSE witness candidates; a
candidate with no source grounding is WITNESS_UNGROUNDED and cannot be admitted.
A witness whose outcome cannot be determined is UNKNOWN_OUTCOME, never silently
assumed to pass.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .canon import hash_obj
from .model import (Finding, P1, P2, WITNESS_KINDS, WITNESS_OUTCOMES,
                    WITNESS_UNGROUNDED, UNKNOWN_OUTCOME_WITNESS)

_HTTPEXC = re.compile(r"HTTPException\(\s*(\d+)\s*,")


def _witness(kind, outcome, surface_id, description, path, line, extra=None):
    rec = {
        "kind": kind, "outcome": outcome, "surface_id": surface_id,
        "description": description,
        "source": {"path": path, "line": line},
        "grounded": bool(path),
    }
    if extra:
        rec.update(extra)
    rec["witness_id"] = "WT-" + hash_obj({k: rec[k] for k in
                                          ("kind", "surface_id", "description",
                                           "source")})[:20]
    return rec


def derive_http_witnesses(root: Path, surfaces) -> list[dict]:
    """Grounded witnesses for HTTP routes from HTTPException status codes in the
    handler body (NEGATIVE/FAILURE witnesses)."""
    out: list[dict] = []
    handler_line = {s.evidence[0][1]: s for s in surfaces
                    if s.surface_kind == "HTTP_ROUTE" and s.evidence}
    app_path = root / "finalis" / "portal" / "app.py"
    if not app_path.exists():
        return out
    src = app_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        matched = [handler_line[d.lineno] for d in node.decorator_list
                   if d.lineno in handler_line]
        if not matched:
            continue
        statuses = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise) and sub.exc is not None:
                seg = lines[sub.lineno - 1] if 0 < sub.lineno <= len(lines) \
                    else ""
                m = _HTTPEXC.search(seg)
                if m:
                    statuses.add((int(m.group(1)), sub.lineno))
        for surface in matched:
            for status, ln in sorted(statuses):
                kind = "AUTHORITY" if status in (401, 403) else "NEGATIVE"
                out.append(_witness(
                    kind, "CONFIRMED", surface.surface_id,
                    f"route rejects with HTTP {status}",
                    str(app_path.relative_to(root)), ln,
                    {"status": status}))
    return out


def validate_witness(w: dict) -> list[Finding]:
    """A witness must be grounded and carry a known kind/outcome (D-0008-31)."""
    out: list[Finding] = []
    subject = str(w.get("surface_id") or "-")
    if w.get("kind") not in WITNESS_KINDS:
        out.append(Finding(WITNESS_UNGROUNDED, P1, subject,
                           f"unknown witness kind {w.get('kind')!r}", {}))
    if not w.get("grounded") or not (w.get("source") or {}).get("path"):
        out.append(Finding(
            WITNESS_UNGROUNDED, P1, subject,
            "witness candidate is not grounded in a source location; an "
            "ungrounded (e.g. LLM-proposed) witness cannot be admitted",
            {"witness": w.get("witness_id")}))
    if w.get("outcome") not in WITNESS_OUTCOMES:
        out.append(Finding(UNKNOWN_OUTCOME_WITNESS, P2, subject,
                           f"unknown witness outcome {w.get('outcome')!r}", {}))
    elif w.get("outcome") == "UNKNOWN_OUTCOME":
        out.append(Finding(
            UNKNOWN_OUTCOME_WITNESS, P2, subject,
            "witness outcome is UNKNOWN_OUTCOME; not treated as a pass", {}))
    return out


def witness_coverage(surfaces, witnesses) -> dict:
    """Which surfaces have >=1 grounded witness vs none (NONE is recorded, not
    hidden)."""
    have = {w["surface_id"] for w in witnesses if w.get("grounded")}
    per_kind: dict = {}
    for w in witnesses:
        per_kind[w["kind"]] = per_kind.get(w["kind"], 0) + 1
    covered = [s.surface_id for s in surfaces if s.surface_id in have]
    uncovered = [s.surface_id for s in surfaces if s.surface_id not in have]
    return {"covered": len(covered), "uncovered": len(uncovered),
            "by_kind": per_kind}
