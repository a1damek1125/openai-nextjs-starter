"""Conformance & Drift Engine — compare the declared twin with observed reality.

Produces a deterministic set of typed Findings. Hard violations (P0/P1) make the
architecture INVALID; advisory (P2) never blocks on its own (SP0001 D-0001-09,
INV-0001-06). Same tree + same manifest => same findings (INV-0001-12).
"""
from __future__ import annotations

from typing import Any

from .graph import TypedGraph
from .model import (Finding, ObservedSnapshot, P0, P1, P2,
                    FORBIDDEN_DEPENDENCY, CAPABILITY_OWNERSHIP_CONFLICT,
                    UNOWNED_NODE, MIGRATION_MUTATION, EFFECT_GATE_VIOLATION,
                    SPEC_CODE_DRIFT_DETECTED, SCAN_ERROR, UNSUPPORTED_LANGUAGE)
from .observe import EFFECT_MODULES
from .ownership import module_owner, route_owner, table_owner


class ConformanceReport:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.module_owner: dict[str, str] = {}
        self.capability_edges: set[tuple[str, str]] = set()
        self.metrics: dict[str, Any] = {}

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def counts(self) -> dict[str, int]:
        c = {P0: 0, P1: 0, P2: 0}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c

    @property
    def valid(self) -> bool:
        c = self.counts()
        return c[P0] == 0 and c[P1] == 0

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "metrics": self.metrics}


def _caps(twin: dict) -> list[dict]:
    # normalize declared capability dicts into the ownership-spec shape
    out = []
    for c in twin["capabilities"]:
        out.append({
            "id": c["capability_id"],
            "paths": c["canonical_paths"],
            "routes": c["route_namespaces"],
            "tables": c["table_namespaces"],
            "forbidden": c["forbidden_dependencies"],
        })
    return out


def evaluate(twin: dict, observed: ObservedSnapshot,
             active_waivers: set[str] | None = None) -> ConformanceReport:
    active_waivers = active_waivers or set()
    rep = ConformanceReport()
    caps = _caps(twin)
    shared = twin.get("shared_module_owners", {})
    forbidden_by_cap = {c["id"]: c["forbidden"] for c in caps}

    # -- 1. module ownership (unowned P1 / conflict P0) --------------------
    for m in observed.modules:
        owner, conflict = module_owner(m, caps, shared)
        if conflict:
            rep.add(Finding(CAPABILITY_OWNERSHIP_CONFLICT, P0, "|".join(conflict),
                            f"module {m} claimed by multiple capabilities",
                            {"module": m, "candidates": conflict}))
        elif owner is None:
            rep.add(Finding(UNOWNED_NODE, P1, "-",
                            f"module {m} has no canonical owner",
                            {"module": m}))
        else:
            rep.module_owner[m] = owner

    # -- 2. declared-namespace overlap conflicts (P0) ---------------------
    for kind, key in (("route", "route_namespaces"), ("table", "table_namespaces")):
        seen: dict[str, str] = {}
        for c in twin["capabilities"]:
            for ns in c[key]:
                if ns in seen and seen[ns] != c["capability_id"]:
                    rep.add(Finding(
                        CAPABILITY_OWNERSHIP_CONFLICT, P0,
                        f'{seen[ns]}|{c["capability_id"]}',
                        f"{kind} namespace '{ns}' declared by two capabilities",
                        {"namespace": ns, "kind": kind,
                         "capabilities": sorted([seen[ns], c["capability_id"]])}))
                seen[ns] = c["capability_id"]

    # -- 2b. observed route/table ownership (collision P0 / unowned P2) ---
    for r in sorted(set(x[0] for x in observed.route_edges)):
        owner, conflict = route_owner(r, caps)
        if conflict:
            rep.add(Finding(CAPABILITY_OWNERSHIP_CONFLICT, P0, "|".join(conflict),
                            f"observed route {r} owned by multiple capabilities",
                            {"route": r, "candidates": conflict}))
        elif owner is None:
            rep.add(Finding("UNOWNED_ROUTE", P2, "-",
                            f"observed route {r} has no declared owner (advisory)",
                            {"route": r}))
    for t in sorted(set(x[0] for x in observed.data_ownership)):
        owner, conflict = table_owner(t, caps)
        if conflict:
            rep.add(Finding(CAPABILITY_OWNERSHIP_CONFLICT, P0, "|".join(conflict),
                            f"observed table {t} owned by multiple capabilities",
                            {"table": t, "candidates": conflict}))
        elif owner is None:
            rep.add(Finding("UNOWNED_TABLE", P2, "-",
                            f"observed table {t} has no declared owner (advisory)",
                            {"table": t}))

    # -- 3. forbidden dependency edges (P0) -------------------------------
    g = TypedGraph()
    for frm, to in observed.import_edges:
        fo = rep.module_owner.get(frm)
        to_owner, _ = module_owner(to, caps, shared)
        if fo and to_owner and fo != to_owner:
            g.add_edge("DEPENDS_ON", fo, to_owner)
            rep.capability_edges.add((fo, to_owner))
            for pfx in forbidden_by_cap.get(fo, []):
                if to == pfx or to.startswith(pfx.rstrip(".") + ".") or to == pfx:
                    if f"forbidden:{fo}->{to}" in active_waivers:
                        continue
                    rep.add(Finding(FORBIDDEN_DEPENDENCY, P0, fo,
                                    f"{fo} imports forbidden {to} (rule prefix {pfx})",
                                    {"from_module": frm, "to_module": to,
                                     "from_capability": fo, "prefix": pfx}))

    # -- 4. capability dependency graph acyclicity ------------------------
    # Per SP0001 §11.4/§12.3 cycles are NOT globally forbidden — the manifest
    # declares which sub-graphs must be acyclic. The Finalis monolith (one
    # composition-root app.py importing every domain, plus shared models/db)
    # is a KNOWN baseline SCC and refactoring it is a non-goal. So a general
    # cross-capability cycle is ADVISORY (P2); the hard protection is the
    # forbidden product->governance edge above (P0). A capability set listed in
    # the twin's `acyclic_required` MUST stay acyclic (P1 if violated). A NEW
    # cycle not present in the declared baseline surfaces in diff mode.
    sccs = g.strongly_connected_components(["DEPENDS_ON"])
    cyclic = [c for c in sccs if len(c) > 1]
    baseline_cyclic = {frozenset(c) for c in
                       twin.get("dependency_baseline", {}).get("cyclic_sccs", [])}
    # (a) hard rule: each declared acyclic-required group must stay acyclic on
    # its INDUCED subgraph (edges with both endpoints inside the group). This
    # catches a new intra-governance cycle even though the monolith mega-SCC
    # would otherwise absorb it (red-team B6).
    for grp in twin.get("acyclic_required", []):
        gset = set(grp)
        sub = TypedGraph()
        for n in gset:
            sub.add_node(n)
        for _, s, d in g.edges("DEPENDS_ON"):
            if s in gset and d in gset:
                sub.add_edge("DEPENDS_ON", s, d)
        for comp in sub.strongly_connected_components(["DEPENDS_ON"]):
            if len(comp) > 1 and f"cycle:{'|'.join(comp)}" not in active_waivers:
                rep.add(Finding("ARCHITECTURE_DEPENDENCY_CYCLE", P1, "|".join(comp),
                                f"cycle within acyclic-required scope: {comp}",
                                {"cycle": comp, "scope": sorted(gset)}))
    # (b) advisory: any cross-capability cycle not present in the declared baseline
    for comp in cyclic:
        if frozenset(comp) not in baseline_cyclic:
            rep.add(Finding("ARCHITECTURE_DEPENDENCY_CYCLE", P2, "|".join(comp),
                            f"cross-capability cycle (advisory; not in baseline): {comp}",
                            {"cycle": comp}))

    # -- 5. migration integrity (append-only) P0 --------------------------
    declared = {v: h for v, h in twin["migration_integrity"]["baseline_digests"]}
    observed_m = {v: h for v, h in observed.migration_digests}
    for v, h in declared.items():
        if v not in observed_m:
            rep.add(Finding(MIGRATION_MUTATION, P0, "portal_shell",
                            f"historical migration v{v} was removed",
                            {"version": v, "expected": h, "observed": None}))
        elif observed_m[v] != h:
            rep.add(Finding(MIGRATION_MUTATION, P0, "portal_shell",
                            f"historical migration v{v} digest changed (mutation)",
                            {"version": v, "expected": h, "observed": observed_m[v]}))
    # appended new versions are allowed; contiguity advisory
    new_versions = sorted(int(v) for v in observed_m if v not in declared)
    if new_versions:
        expected_next = int(twin["migration_integrity"]["baseline_max_version"]) + 1
        contiguous = new_versions == list(range(expected_next,
                                                 expected_next + len(new_versions)))
        rep.metrics["appended_migrations"] = new_versions
        if not contiguous:
            rep.add(Finding(MIGRATION_MUTATION, P1, "portal_shell",
                            f"appended migrations not contiguous from v{expected_next}",
                            {"new_versions": new_versions}))

    # -- 6. effect gate (P0 network) / advisory (P2 dynamic) --------------
    if not twin["effect_gates"]["real_external_effects_allowed"]:
        baseline = {(o["module"], o["kind"], o["target"])
                    for o in twin["effect_gates"]["baseline_effect_observations"]}
        for o in observed.effect_observations:
            key = (o["module"], o["kind"], o["target"])
            is_network = (o["kind"] in ("import", "from_import")
                          and (o["target"] in EFFECT_MODULES
                               or o["target"].split(".")[0] in EFFECT_MODULES))
            if is_network:
                if f'effect:{o["module"]}:{o["target"]}' in active_waivers:
                    continue
                rep.add(Finding(EFFECT_GATE_VIOLATION, P0,
                                rep.module_owner.get(o["module"], "-"),
                                f"outbound network primitive {o['target']} in {o['module']} "
                                f"(closed effect gate)",
                                {"observation": o}))
            elif key not in baseline:
                rep.add(Finding("DYNAMIC_IMPORT_ADVISORY", P2,
                                rep.module_owner.get(o["module"], "-"),
                                f"new dynamic import in {o['module']} (advisory)",
                                {"observation": o}))

    # -- 7. spec anchors exist (P2) + canonical paths exist (P1) ----------
    import os
    root = _repo_root()
    for c in twin["capabilities"]:
        for anchor in c.get("spec_anchors", []):
            if not os.path.exists(os.path.join(root, anchor)):
                rep.add(Finding(SPEC_CODE_DRIFT_DETECTED, P2, c["capability_id"],
                                f"spec anchor missing: {anchor}",
                                {"anchor": anchor}))

    # -- 8. scan errors are fail-closed (P1) ------------------------------
    for e in observed.scan_errors:
        kind = UNSUPPORTED_LANGUAGE if "UNSUPPORTED_LANGUAGE" in e.get("error", "") \
            else SCAN_ERROR
        rep.add(Finding(kind, P1, "-", e.get("error", "scan error"), e))

    rep.metrics.update({
        "modules": len(observed.modules),
        "capabilities": len(twin["capabilities"]),
        "capability_edges": len(rep.capability_edges),
        "sccs": len(sccs),
        "cyclic_sccs": len(cyclic),
        "routes": len(set(r[0] for r in observed.route_edges)),
        "tables": len(set(t[0] for t in observed.data_ownership)),
        "migrations": len(observed.migration_digests),
        "effect_observations": len(observed.effect_observations),
        "scan_errors": len(observed.scan_errors),
    })
    return rep


def _repo_root() -> str:
    import os
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
