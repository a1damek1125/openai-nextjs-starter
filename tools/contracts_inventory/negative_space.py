"""Negative-space verification against a declared universe (SP0008 §negative,
D-0008-30/33).

Completeness cannot be proven in the open world, but it CAN be verified against a
DECLARED universe: for each surface kind we declare an independent lower-bound
count derived from a second, cheap counting method (e.g. a raw regex tally of
route decorators, of CREATE TABLE statements, of EVENT_SCHEMA keys). The negative
space is the gap between what the declaration says should exist and what the
detectors materialized. A shortfall (detectors found FEWER than the declared
floor) is a NEGATIVE_SPACE_UNVERIFIED finding — the inventory is missing surfaces
it should have caught. An overage is fine (detectors found more). This is the
inventory checking itself with a method independent of its own detectors.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import (Finding, P1, P2, NEGATIVE_SPACE_UNVERIFIED,
                    DECLARED_UNIVERSE_INCOMPLETE)


def declared_universe(root: Path) -> dict:
    """Independent lower-bound counts per surface kind, computed by a SECOND
    method (raw text tallies) that does not share the AST detectors' logic."""
    decl: dict[str, int] = {}

    app = root / "finalis" / "portal" / "app.py"
    if app.exists():
        txt = app.read_text(encoding="utf-8", errors="replace")
        decl["HTTP_ROUTE"] = len(re.findall(
            r"@app\.(?:get|post|put|patch|delete)\(", txt))

    db = root / "finalis" / "portal" / "db.py"
    if db.exists():
        txt = db.read_text(encoding="utf-8", errors="replace")
        # distinct table names
        tables = set(re.findall(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)",
            txt, re.IGNORECASE))
        decl["DB_TABLE"] = len(tables)
        decl["DB_MIGRATION"] = len(re.findall(r"^\s*\(\d+,\s*\"\"\"", txt,
                                              re.MULTILINE))

    rl = root / "finalis" / "ai_employee" / "run_ledger.py"
    if rl.exists():
        txt = rl.read_text(encoding="utf-8", errors="replace")
        # EVENT_SCHEMA keys — count "KEY": entries inside the dict block
        m = re.search(r"EVENT_SCHEMA\s*=\s*\{(.*?)\n\}", txt, re.DOTALL)
        if m:
            decl["RUN_LEDGER_EVENT"] = len(re.findall(
                r'"[A-Z][A-Z0-9_]+"\s*:', m.group(1)))
    return decl


def verify_negative_space(root: Path, surfaces) -> tuple:
    """Compare detector materialization against the declared floor. Returns
    (report_dict, findings)."""
    decl = declared_universe(root)
    observed: dict[str, int] = {}
    for s in surfaces:
        observed[s.surface_kind] = observed.get(s.surface_kind, 0) + 1

    rows = []
    findings: list[Finding] = []
    for kind, floor in sorted(decl.items()):
        got = observed.get(kind, 0)
        gap = got - floor
        status = "OK" if got >= floor else "SHORTFALL"
        rows.append({"surface_kind": kind, "declared_floor": floor,
                     "observed": got, "gap": gap, "status": status})
        if got < floor:
            findings.append(Finding(
                NEGATIVE_SPACE_UNVERIFIED, P1, kind,
                f"detectors materialized {got} {kind} surfaces but the declared "
                f"floor (independent count) is {floor}: "
                f"{floor - got} surface(s) unaccounted for",
                {"declared_floor": floor, "observed": got}))
    # kinds with no declaration at all are an incomplete declared universe
    for kind in sorted(observed):
        if kind not in decl and kind not in (
                "STATE_TRANSITION", "AUDIT_EVENT", "PROOF_ARTIFACT",
                "CONFIG_KEY", "STATE_MACHINE"):
            findings.append(Finding(
                DECLARED_UNIVERSE_INCOMPLETE, P2, kind,
                f"surface kind {kind} has observed surfaces but no declared "
                "floor to verify against", {"observed": observed[kind]}))
    report = {"declared": decl, "observed": observed, "rows": rows}
    return report, findings
