"""Machine-queryable CLI over the Canonical Contract Surface Inventory
(SP0008 §CLI, D-0008-48).

Every subcommand answers one governance question deterministically and prints
canonical JSON (so output is diffable and pipe-friendly). The inventory is built
once from source per invocation, or loaded from a committed artifact with
--from. Nothing here executes anything against the running product.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bootstrap, validate as validate_mod, chains, discover, \
    normalize, detectors as detectors_mod
from .canon import canonical_json


def _emit(obj) -> int:
    print(canonical_json(obj) if _COMPACT else json.dumps(obj, indent=2,
                                                          sort_keys=True))
    return 0


_COMPACT = False


def _inventory(args) -> dict:
    if getattr(args, "from_file", None):
        return validate_mod.load_inventory(Path(args.from_file))
    return bootstrap.build_inventory(Path(args.root))


def _records(inv) -> list:
    return inv["surfaces"]


def _find(inv, sid_or_name):
    for r in _records(inv):
        if r["surface_id"] == sid_or_name or r["canonical_name"] == sid_or_name:
            return r
    return None


# --- commands ---------------------------------------------------------------
def cmd_roadmap_identity(args) -> int:
    return _emit({
        "mission": "SP0008",
        "title": "FINALIS Canonical Contract Surface Inventory, Repository "
                 "Intelligence & Dependency Truth Constitution",
        "populates_registry": "SP0007 FINALIS_CONTRACT_DESCRIPTORS "
                              "(no parallel registry)",
        "boundary": ["zero product-runtime change", "zero product migration "
                     "(frontier stays v27)", "zero external effect",
                     "never imported by product code"],
        "detectors": detectors_mod.detector_names(),
    })


def cmd_detectors(args) -> int:
    return _emit({
        "detectors": detectors_mod.detector_names(),
        "capability": detectors_mod.CAPABILITY,
        "blind_spots": detectors_mod.blind_spots(),
    })


def cmd_discover(args) -> int:
    obs = discover.discover_all(Path(args.root))
    return _emit({"observation_count": len(obs),
                  "observations": [o.as_dict() for o in obs]})


def cmd_inventory(args) -> int:
    inv = _inventory(args)
    if args.summary:
        return _emit({k: inv[k] for k in ("inventory_version", "counts",
                     "genome", "readiness_summary", "model_checks",
                     "inventory_digest")})
    return _emit(inv)


def cmd_surface(args) -> int:
    r = _find(_inventory(args), args.id)
    return _emit(r or {"error": "not found", "id": args.id})


def cmd_why_unknown(args) -> int:
    """Explain why a surface's criticality/reachability/consumers are UNKNOWN."""
    r = _find(_inventory(args), args.id)
    if not r:
        return _emit({"error": "not found", "id": args.id})
    unknown_dims = [d for d, v in r["criticality"]["vector"].items()
                    if v == "UNKNOWN"]
    return _emit({
        "surface_id": r["surface_id"],
        "unknown_criticality_dims": unknown_dims,
        "effect_reachability_exactness": r["effect_reachability"].get(
            "exactness"),
        "consumer_certainty": r["consumers"].get("certainty"),
        "readiness_blockers": r["readiness"].get("hard_blockers"),
        "explanation": "UNKNOWN is a recorded result, not an omission; each "
                       "feeds the probe plan (next_probe).",
    })


def cmd_owners(args) -> int:
    inv = _inventory(args)
    by_owner: dict = {}
    for r in _records(inv):
        o = r["ownership"].get("owner")
        by_owner.setdefault(o, []).append(r["surface_id"])
    return _emit({"owners": {k: len(v) for k, v in sorted(
        by_owner.items(), key=lambda x: (x[0] is None, x[0]))}})


def cmd_consumers(args) -> int:
    r = _find(_inventory(args), args.id)
    return _emit(r["consumers"] if r else {"error": "not found"})


def cmd_contradictions(args) -> int:
    inv = _inventory(args)
    contra = [f for f in inv["findings"]
              if f["kind"] == "CONTRADICTION_PRESERVED"]
    return _emit({"count": len(contra), "contradictions": contra})


def cmd_witnesses(args) -> int:
    r = _find(_inventory(args), args.id)
    return _emit({"surface_id": args.id,
                  "witness_count": r["witness_count"] if r else 0,
                  "witnesses": r["witnesses"] if r else []})


def cmd_boundaries(args) -> int:
    from . import closure
    fs = closure.check_boundary(Path(args.root))
    return _emit({"violations": [f.as_dict() for f in fs],
                  "clean": not fs})


def cmd_trace(args) -> int:
    inv = _inventory(args)
    r = _find(inv, args.id)
    return _emit(r["effect_reachability"] if r else {"error": "not found"})


def cmd_dominators(args) -> int:
    root = Path(args.root)
    obs = discover.discover_all(root)
    descriptors = bootstrap._load_descriptors(root)
    surfaces = normalize.reconcile(obs, descriptors)
    edges, _ = chains.derive_edges(root, surfaces)
    dom = chains.dominators(edges, [args.id], set(edges))
    return _emit({"surface_id": args.id,
                  "dominators": {k: sorted(v) for k, v in dom.items()
                                 if args.id in v and k != args.id}})


def cmd_cut_sets(args) -> int:
    root = Path(args.root)
    obs = discover.discover_all(root)
    descriptors = bootstrap._load_descriptors(root)
    surfaces = normalize.reconcile(obs, descriptors)
    edges, _ = chains.derive_edges(root, surfaces)
    sinks = chains.effect_sinks(surfaces)
    res = chains.minimal_cut_sets(edges, [args.id], sinks)
    return _emit(res)


def cmd_negative_space(args) -> int:
    return _emit(_inventory(args)["negative_space"])


def cmd_residual(args) -> int:
    return _emit(_inventory(args)["residual_estimate"])


def cmd_next_probe(args) -> int:
    plan = _inventory(args)["probe_plan"]
    return _emit({"top": plan[:args.n], "total": len(plan)})


def cmd_agent_readiness(args) -> int:
    inv = _inventory(args)
    if args.id:
        r = _find(inv, args.id)
        return _emit(r["readiness"] if r else {"error": "not found"})
    return _emit(inv["readiness_summary"])


def cmd_closure(args) -> int:
    return cmd_boundaries(args)


def cmd_genome(args) -> int:
    return _emit(_inventory(args)["genome"])


def cmd_diff(args) -> int:
    a = validate_mod.load_inventory(Path(args.old))
    b = validate_mod.load_inventory(Path(args.new))
    return _emit(_diff_inventories(a, b))


def _diff_inventories(a, b) -> dict:
    ga, gb = a["genome"]["global_root"], b["genome"]["global_root"]
    ids_a = {r["surface_id"] for r in a["surfaces"]}
    ids_b = {r["surface_id"] for r in b["surfaces"]}
    leaves_a = {r["surface_id"]: r["material_leaf"] for r in a["surfaces"]}
    leaves_b = {r["surface_id"]: r["material_leaf"] for r in b["surfaces"]}
    changed = sorted(sid for sid in (ids_a & ids_b)
                     if leaves_a[sid] != leaves_b[sid])
    return {
        "genome_changed": ga != gb,
        "added": sorted(ids_b - ids_a),
        "removed": sorted(ids_a - ids_b),
        "materially_changed": changed,
    }


def cmd_impact(args) -> int:
    """What effect sinks and downstream surfaces a given surface can reach."""
    inv = _inventory(args)
    r = _find(inv, args.id)
    if not r:
        return _emit({"error": "not found"})
    return _emit({"surface_id": r["surface_id"],
                  "reaches_effect": r["effect_reachability"].get(
                      "reaches_effect"),
                  "effect_sinks": r["effect_reachability"].get("effect_sinks"),
                  "criticality_verdict": r["criticality"]["verdict"]})


def cmd_validate(args) -> int:
    root = Path(args.root)
    inv = _inventory(args)
    rep = validate_mod.validate_inventory(inv, root)
    _emit(rep.as_dict())
    return 0 if rep.valid else 1


def cmd_attest(args) -> int:
    inv = _inventory(args)
    return _emit({"envelope": inv["envelope"],
                  "inventory_digest": inv["inventory_digest"]})


# --- parser -----------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contracts_inventory",
        description="Canonical Contract Surface Inventory (SP0008)")
    p.add_argument("--root", default=".", help="repository root")
    p.add_argument("--json", action="store_true",
                   help="compact canonical JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *, needs_id=False, needs_from=True, extra=None):
        sp = sub.add_parser(name)
        if needs_from:
            sp.add_argument("--from", dest="from_file",
                            help="load a committed inventory JSON")
        if needs_id:
            sp.add_argument("id", help="surface id or canonical name")
        if extra:
            extra(sp)
        sp.set_defaults(func=fn)
        return sp

    add("roadmap_identity", cmd_roadmap_identity, needs_from=False)
    add("detectors", cmd_detectors, needs_from=False)
    add("discover", cmd_discover, needs_from=False)
    add("inventory", cmd_inventory,
        extra=lambda sp: sp.add_argument("--summary", action="store_true"))
    add("surface", cmd_surface, needs_id=True)
    add("why_unknown", cmd_why_unknown, needs_id=True)
    add("owners", cmd_owners)
    add("consumers", cmd_consumers, needs_id=True)
    add("contradictions", cmd_contradictions)
    add("witnesses", cmd_witnesses, needs_id=True)
    add("boundaries", cmd_boundaries, needs_from=False)
    add("trace", cmd_trace, needs_id=True)
    add("dominators", cmd_dominators, needs_id=True, needs_from=False)
    add("cut_sets", cmd_cut_sets, needs_id=True, needs_from=False)
    add("negative_space", cmd_negative_space)
    add("residual", cmd_residual)
    add("next_probe", cmd_next_probe,
        extra=lambda sp: sp.add_argument("-n", type=int, default=10))
    add("agent_readiness", cmd_agent_readiness,
        extra=lambda sp: sp.add_argument("id", nargs="?", default=None))
    add("closure", cmd_closure, needs_from=False)
    add("genome", cmd_genome)
    add("diff", cmd_diff, needs_from=False,
        extra=lambda sp: (sp.add_argument("--old", required=True),
                          sp.add_argument("--new", required=True)))
    add("impact", cmd_impact, needs_id=True)
    add("validate", cmd_validate)
    add("attest", cmd_attest)
    return p


def main(argv=None) -> int:
    global _COMPACT
    parser = build_parser()
    args = parser.parse_args(argv)
    _COMPACT = bool(getattr(args, "json", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
