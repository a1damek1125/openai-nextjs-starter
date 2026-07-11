"""Shared (non-collected) helpers for Architecture Immune System tests.

Builds small synthetic declared twins + observed snapshots so mutation/conformance
tests are deterministic and never mutate the real repository tree.
"""
from __future__ import annotations

import copy

from tools.architecture.model import ObservedSnapshot


def cap(cid, *, owner=None, paths=None, routes=None, tables=None, perms=None,
        forbidden=None, classification="product_engine", purpose="",
        allowed=None, tests=None, specs=None,
        replacement="DO_NOT_REBUILD"):
    return {
        "capability_id": cid,
        "display_name": cid.replace("_", " ").title(),
        "canonical_owner": owner or f"finalis/{cid}",
        "classification": classification,
        "purpose": purpose or f"{cid} capability",
        "canonical_paths": paths or [f"finalis/{cid}/"],
        "extension_points": [],
        "route_namespaces": routes or [],
        "table_namespaces": tables or [],
        "permission_namespaces": perms or [],
        "spec_anchors": specs if specs is not None else [],
        "test_anchors": tests or [],
        "allowed_dependencies": allowed or [],
        "forbidden_dependencies": forbidden or [],
        "replacement_policy": replacement,
    }


def mini_twin(capabilities, *, migrations=None, effects_allowed=False,
              baseline_effects=None, edges=None, cyclic=None,
              route_baseline=None, table_baseline=None,
              acyclic_required=None):
    migrations = migrations or [["1", "hash_v1"], ["2", "hash_v2"]]
    return {
        "schema_version": "2.0.0",
        "program": "FINALIS_1000",
        "sp": "SP0001",
        "twin_kind": "DECLARED",
        "baseline_head": "testhead",
        "capabilities": copy.deepcopy(capabilities),
        "dependency_rules": [],
        "protected_contracts": [],
        "spec_nodes": [],
        "acyclic_required": acyclic_required or [],
        "dependency_baseline": {"edges": edges or [],
                                "cyclic_sccs": cyclic or []},
        "route_baseline": route_baseline if route_baseline is not None else [],
        "table_baseline": table_baseline if table_baseline is not None else [],
        "effect_gates": {"real_external_effects_allowed": effects_allowed,
                         "baseline_effect_observations": baseline_effects or []},
        "migration_integrity": {"policy": "APPEND_ONLY",
                                "baseline_max_version": max(int(v) for v, _ in migrations),
                                "baseline_digests": migrations},
        "waiver_policy": {"waivers_file": "x.json", "max_lifetime_days": 90},
        "scanner_adapters": [{"language": "python", "adapter": "ast",
                              "status": "ACTIVE"}],
        "shared_module_owners": {},
    }


def mini_observed(*, modules=None, import_edges=None, routes=None, tables=None,
                  migrations=None, effects=None, scan_errors=None,
                  commit="obs1"):
    return ObservedSnapshot(
        commit=commit,
        modules=modules or [],
        capabilities=[],
        import_edges=import_edges or [],
        route_edges=[[r, "finalis.portal.app"] for r in (routes or [])],
        data_ownership=[[t, "1"] for t in (tables or [])],
        migration_digests=migrations or [["1", "hash_v1"], ["2", "hash_v2"]],
        effect_observations=effects or [],
        metrics={},
        scan_errors=scan_errors or [],
    )


def net_effect(module, target="requests", line=1):
    return {"module": module, "path": f"{module.replace('.', '/')}.py",
            "kind": "import", "target": target, "line": line}


def dyn_effect(module, line=1):
    return {"module": module, "path": f"{module.replace('.', '/')}.py",
            "kind": "dynamic_import", "target": "__import__", "line": line}
