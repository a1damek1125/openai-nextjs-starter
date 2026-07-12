"""Impact cone and dependency-closed release slice (SP0009 FUNCTION A/§11.2/
11.3, §12.2, D-0009-04, AC-0009-043..050).

The impact cone traverses REAL SP0008 truth: changed source paths are matched
against the Contract Inventory's evidence locations to find directly impacted
surfaces; parent contracts, criticality verdicts and effect reachability come
from the same records. A surface whose effect reachability is UNKNOWN is an
UNKNOWN impact — represented, never dropped, and CRITICAL unknowns block the
slice (fail-closed). The release slice is dependency-closed (§12.2): every
required dependency of a slice member must be inside the slice or the verified
baseline; anything else is RELEASE_SLICE_NOT_CLOSED.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0, P1

INVENTORY_PATH = "docs/contracts_inventory/FINALIS_CONTRACT_INVENTORY.json"


def load_inventory(root: Path) -> dict:
    p = root / INVENTORY_PATH
    if not p.exists():
        return {}
    return json.load(open(p, encoding="utf-8"))


def impact_cone(root: Path, changed_paths: list,
                inventory: dict | None = None) -> dict:
    """Traverse CHANGED SOURCE -> SURFACE -> PARENT CONTRACT -> CRITICALITY /
    EFFECT over the real SP0008 inventory."""
    inv = inventory if inventory is not None else load_inventory(root)
    surfaces = inv.get("surfaces") or []
    changed = set(changed_paths)
    direct, unknown = [], []
    for s in surfaces:
        ev_paths = {e.get("path") for e in s.get("evidence") or []}
        if ev_paths & changed:
            rec = {
                "surface_id": s["surface_id"],
                "canonical_name": s.get("canonical_name"),
                "parent_contract_id": s.get("parent_contract_id"),
                "criticality_verdict": (s.get("criticality") or {}).get(
                    "verdict", "UNKNOWN"),
                "effect_exactness": (s.get("effect_reachability") or {}).get(
                    "exactness", "UNKNOWN"),
            }
            direct.append(rec)
            if rec["effect_exactness"] == "UNKNOWN":
                unknown.append(rec["surface_id"])
    contracts = sorted({d["parent_contract_id"] for d in direct
                        if d["parent_contract_id"]})
    cone = {
        "changed_paths": sorted(changed),
        "direct_impacts": sorted(direct, key=lambda d: d["surface_id"]),
        "impacted_contracts": contracts,
        "unknown_impacts": sorted(unknown),
        "critical_impacts": sorted(d["surface_id"] for d in direct
                                   if d["criticality_verdict"] == "CRITICAL"),
    }
    cone["impact_cone_hash"] = hash_obj(cone)
    return cone


def cone_findings(cone: dict) -> list[Finding]:
    out: list[Finding] = []
    critical_unknown = set(cone.get("unknown_impacts", [])) & set(
        cone.get("critical_impacts", []))
    for sid in sorted(critical_unknown):
        out.append(Finding(
            "IMPACT_CONE_INCOMPLETE", P0, sid,
            "CRITICAL surface with UNKNOWN effect reachability inside the "
            "impact cone: unknown critical branches block (§11.2)", {}))
    return out


# --- dependency-closed release slice (§11.3, §12.2, D-0009-04) ------------------------
def release_slice(*, slice_id: str, members: list, dependencies: dict,
                  verified_baseline: set) -> dict:
    """members: change ids in the slice; dependencies: {member: [required]};
    verified_baseline: ids already verified. Closure check per §12.2."""
    member_set = set(members)
    missing = {}
    for m in sorted(member_set):
        for dep in sorted(dependencies.get(m, ())):
            if dep not in member_set and dep not in verified_baseline:
                missing.setdefault(m, []).append(dep)
    s = {"slice_id": slice_id, "members": sorted(member_set),
         "dependencies": {k: sorted(v) for k, v in
                          sorted(dependencies.items())},
         "missing_dependencies": {k: sorted(v) for k, v in
                                  sorted(missing.items())},
         "closed": not missing}
    s["release_slice_ref"] = "RS-" + hash_obj(s)[:20]
    return s


def slice_findings(s: dict) -> list[Finding]:
    out: list[Finding] = []
    for member, deps in sorted((s.get("missing_dependencies") or {}).items()):
        out.append(Finding(
            "RELEASE_SLICE_NOT_CLOSED", P0, member,
            f"slice member requires {deps} which are neither in the slice "
            "nor in the verified baseline: the release slice must be "
            "dependency-closed (D-0009-04)", {"missing": deps}))
    return out
