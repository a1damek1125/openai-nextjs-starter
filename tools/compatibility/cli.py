"""Repository-local CLI for the Compatibility Constitution (SP0007 §15). Every
subcommand emits JSON (evidence, not authority). No product runtime endpoint.
"""
from __future__ import annotations

import argparse
import json
import sys

from .loader import load_program
from .validate import validate_all
from .modelcheck import run_all_models
from .diff import diff_contracts, breaking_findings
from .fitness import fitness_findings, debt_registry, observatory
from .envelope import compatibility_proof_envelope


def _emit(obj) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_roadmap_identity(a) -> int:
    return _emit({
        "sp_id": "SP0007",
        "canonical_title": "Compatibility, Migration and Versioning Policy",
        "mission": "Backward Compatibility, Migration, Versioning & Contract "
                   "Evolution Constitution",
        "report": "docs/compatibility/SP0007_ROADMAP_IDENTITY_REPORT.md",
        "predecessors": ["SP0000", "SP0001", "SP0002", "SP0003", "SP0004",
                         "SP0005", "SP0006"],
        "evaluation_charter": "reassigned to SP0011 (not implemented here)",
        "change_boundary": {"product_behavior_change": False,
                            "live_migration": False, "db_migration": False,
                            "migration_frontier": 27}})


def cmd_inventory(a) -> int:
    p = load_program()
    return _emit({k: (len(v) if isinstance(v, list) else len(v))
                  for k, v in p.items() if isinstance(v, (list, dict))
                  and k != "_meta"})


def cmd_validate(a) -> int:
    rep = validate_all(load_program())
    _emit(rep.to_dict())
    return 0 if rep.valid else 1


def cmd_modelcheck(a) -> int:
    res = run_all_models()
    out = {k: {kk: vv for kk, vv in v.items() if kk != "counterexample"}
           for k, v in res.items()}
    _emit(out)
    return 0 if all(v.get("verdict") == "HOLDS" for v in res.values()) else 1


def cmd_diff(a) -> int:
    old, new = _load_json(a.old), _load_json(a.new)
    diffs = diff_contracts(old, new)
    findings = breaking_findings(old, new)
    _emit({"diffs": diffs, "findings": [f.to_dict() for f in findings]})
    return 0 if not any(f.severity in ("P0", "P1") for f in findings) else 1


def cmd_fitness(a) -> int:
    p = load_program()
    findings = fitness_findings(p)
    _emit({"findings": [f.to_dict() for f in findings],
           "debt": debt_registry(p)})
    return 0 if not findings else 1


def cmd_observatory(a) -> int:
    return _emit(observatory(load_program()))


def cmd_attest(a) -> int:
    p = load_program()
    rep = validate_all(p)
    d = (p.get("descriptors") or [{}])[0]
    v = (p.get("versions") or [{}])[0]
    b = (p.get("bindings") or [{}])[0]
    env = compatibility_proof_envelope(
        descriptor=d, producer_version=v, consumer_binding=b,
        compatibility_vector=(p.get("claims") or [{}])[0].get(
            "compatibility_vector"),
        historical_corpus=p.get("fixtures"))
    _emit({"valid": rep.valid, "counts": rep.counts(),
           "compatibility_proof_envelope": env})
    return 0 if rep.valid else 1


def cmd_impact(a) -> int:
    from .consumers import build_graph, blast_radius
    p = load_program()
    graph = build_graph(p.get("descriptors", []), p.get("bindings", []))
    return _emit({"contract_id": a.change,
                  "blast_radius": blast_radius(graph, a.change,
                                               bindings=p.get("bindings", [])),
                  "classification": "ADVISORY"})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.compatibility")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")

    for name, fn in (("roadmap-identity", cmd_roadmap_identity),
                     ("inventory", cmd_inventory), ("validate", cmd_validate),
                     ("modelcheck", cmd_modelcheck), ("fitness", cmd_fitness),
                     ("observatory", cmd_observatory), ("attest", cmd_attest)):
        sub.add_parser(name, parents=[common]).set_defaults(func=fn)

    d = sub.add_parser("diff", parents=[common])
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    d.set_defaults(func=cmd_diff)

    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--change", required=True)
    im.set_defaults(func=cmd_impact)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
