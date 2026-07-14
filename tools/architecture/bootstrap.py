"""Offline seeding: render the DECLARED Architecture Digital Twin JSON.

This runs OUTSIDE the gate path (SP0001 §5.2 / ArchAgent caveat: LLM/offline
recovery may seed the twin, but the gate itself stays deterministic). It freezes
the current migration digests and the closed effect-gate baseline into the
declared twin so future mutation is detectable against declared intent.

Usage: python -m tools.architecture.bootstrap [--write]
"""
from __future__ import annotations

import json
import os
import sys

from . import TWIN_SCHEMA_VERSION
from .capabilities import CAPABILITIES, SHARED_MODULES, _BASE
from .graph import TypedGraph
from .observe import build_observed
from .ownership import module_owner

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TWIN_PATH = os.path.join(REPO_ROOT, "docs", "architecture",
                         "FINALIS_1000_ARCHITECTURE_TWIN.json")


def _capability_node(spec: dict) -> dict:
    return {
        "capability_id": spec["id"],
        "display_name": spec["id"].replace("_", " ").title(),
        "canonical_owner": spec["owner"],
        "classification": spec["classification"],
        "purpose": spec["purpose"],
        "canonical_paths": sorted(spec["paths"]),
        "extension_points": spec.get("extension_points", []),
        "route_namespaces": sorted(spec.get("routes", [])),
        "table_namespaces": sorted(spec.get("tables", [])),
        "permission_namespaces": sorted(spec.get("perms", [])),
        "spec_anchors": spec.get("spec_anchors", [
            "docs/audit/AUDIT_TRACE_1_MASTER.md",
            "docs/architecture/FINALIS_1000_MASTER_ARCHITECTURE_LOCK.md",
        ]),
        "test_anchors": spec.get("test_anchors", []),
        "allowed_dependencies": sorted(set(_BASE) | set(spec.get("allowed", []))),
        "forbidden_dependencies": sorted(spec.get("forbidden", [])),
        "replacement_policy": "DO_NOT_REBUILD",
    }


def _baseline_capability_graph(observed) -> dict:
    """Observed capability-level DEPENDS_ON edges + cyclic SCCs at bootstrap."""
    caps = [{"id": c["id"], "paths": c["paths"]} for c in CAPABILITIES]
    g = TypedGraph()
    edges: set[tuple[str, str]] = set()
    for frm, to in observed.import_edges:
        fo, _ = module_owner(frm, caps, SHARED_MODULES)
        to_o, _ = module_owner(to, caps, SHARED_MODULES)
        if fo and to_o and fo != to_o:
            g.add_edge("DEPENDS_ON", fo, to_o)
            edges.add((fo, to_o))
    sccs = g.strongly_connected_components(["DEPENDS_ON"])
    cyclic = [c for c in sccs if len(c) > 1]
    return {
        "edges": sorted([list(e) for e in edges]),
        "cyclic_sccs": [sorted(c) for c in cyclic],
        "note": ("Baseline monolith: app.py composition-root imports every domain "
                 "and shared models/db are imported widely. This SCC is DECLARED "
                 "baseline reality (refactor is a non-goal). New cross-capability "
                 "cycles surface in diff mode."),
    }


def build_declared_twin() -> dict:
    observed = build_observed(REPO_ROOT)
    capabilities = [_capability_node(c) for c in CAPABILITIES]

    dependency_rules = []
    for c in CAPABILITIES:
        for fb in c.get("forbidden", []):
            dependency_rules.append({
                "rule": "FORBIDDEN", "capability": c["id"],
                "forbidden_import_prefix": fb,
                "note": "Product engine must not depend on the governance kernel.",
            })
    # Layered acyclic guarantee: the capability dependency graph must be acyclic.
    dependency_rules.append({
        "rule": "ACYCLIC_LAYER", "graph": "capability_depends_on",
        "note": "Cross-capability dependency graph must remain acyclic.",
    })

    twin = {
        "schema_version": TWIN_SCHEMA_VERSION,
        "program": "FINALIS_1000",
        "sp": "SP0001",
        "twin_kind": "DECLARED",
        "baseline_head": observed.commit,
        "capabilities": sorted(capabilities, key=lambda c: c["capability_id"]),
        "dependency_rules": dependency_rules,
        "protected_contracts": [
            {"contract": "authority_ladder",
             "note": "Model/external content/LGGT/frontend are never authority (SP0000 INV-0000-02..05)."},
            {"contract": "one_capability_one_owner", "note": "INV-0001-01."},
            {"contract": "append_only_migrations", "note": "INV-0001-05 / D-0001-18."},
            {"contract": "closed_effect_gate", "note": "INV-0001-10 / D-0001-19."},
        ],
        "spec_nodes": [
            {"spec_id": "AUDIT_TRACE_1", "path": "docs/audit/AUDIT_TRACE_1_MASTER.md"},
            {"spec_id": "SP0000_MASTER", "path": "docs/architecture/FINALIS_1000_MASTER_ARCHITECTURE_LOCK.md"},
            {"spec_id": "SP0000_AUTHORITY", "path": "docs/architecture/FINALIS_1000_AUTHORITY_BOUNDARIES.md"},
            {"spec_id": "SP0000_DO_NOT_REBUILD", "path": "docs/architecture/FINALIS_1000_DO_NOT_REBUILD.md"},
        ],
        "effect_gates": {
            "real_external_effects_allowed": False,
            "baseline_effect_observations": observed.effect_observations,
            "note": ("Current closed effect gate. Dynamic imports are advisory (P2); "
                     "any network primitive (requests/httpx/smtplib/socket/urllib.request/"
                     "http.client/...) in non-test product code is EFFECT_GATE_VIOLATION."),
        },
        "migration_integrity": {
            "policy": "APPEND_ONLY",
            "baseline_max_version": max(int(d[0]) for d in observed.migration_digests),
            "baseline_digests": observed.migration_digests,
        },
        "acyclic_required": [
            [c["id"] for c in CAPABILITIES
             if c["classification"].startswith("governance")]
        ],
        "dependency_baseline": _baseline_capability_graph(observed),
        "route_baseline": sorted(set(r[0] for r in observed.route_edges)),
        "table_baseline": sorted(set(t[0] for t in observed.data_ownership)),
        "waiver_policy": {
            "waivers_file": "docs/architecture/FINALIS_1000_ARCHITECTURE_WAIVERS.json",
            "max_lifetime_days": 90,
            "note": "No permanent anonymous waiver (SP0001 §13.2).",
        },
        "scanner_adapters": [
            {"language": "python", "adapter": "ast", "status": "ACTIVE"},
            {"language": "typescript", "adapter": "tree-sitter", "status": "FUTURE_BOUNDARY"},
            {"language": "any", "adapter": "codeql", "status": "FUTURE_BOUNDARY"},
        ],
        "shared_module_owners": SHARED_MODULES,
    }
    return twin


def main(argv: list[str]) -> int:
    twin = build_declared_twin()
    text = json.dumps(twin, indent=2, ensure_ascii=False, sort_keys=True)
    if "--write" in argv:
        os.makedirs(os.path.dirname(TWIN_PATH), exist_ok=True)
        with open(TWIN_PATH, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {os.path.relpath(TWIN_PATH, REPO_ROOT)} "
              f"({len(twin['capabilities'])} capabilities)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
