"""Program Constitution CLI (SP0003 §15).

    python -m tools.program_graph validate      [--scenario BASELINE]
    python -m tools.program_graph compile        --scenario TEMPORAL_RUNTIME_OPTION
    python -m tools.program_graph ready          [--scenario ...]
    python -m tools.program_graph criticality    [--scenario ...] [--mc N --seed S]
    python -m tools.program_graph impact         --node ADAPTER-1
    python -m tools.program_graph rework-impact   --node SP0002
    python -m tools.program_graph dominators      --target GENERAL_AVAILABILITY
    python -m tools.program_graph cut-set         --target GENERAL_AVAILABILITY
    python -m tools.program_graph voi             --uncertainty <id>
    python -m tools.program_graph twin
    python -m tools.program_graph drift
    python -m tools.program_graph attest

Deterministic, --json, no network. Exit 1 iff the program plan is invalid (P0/P1).
This tooling never imports product code.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .loader import load_program_bundle
from .validate import validate_program
from .scenario import compile_scenario
from .readiness import ready_nodes, prerequisite_ready_nodes
from .criticality import structural_depth, cpm, display_critical_path
from .forecast import numeric_durations, monte_carlo_criticality
from .impact import dependency_impact_cone, rework_impact_cone
from .resilience import program_dominators, milestone_cut_set
from .voi import evaluate_voi
from .twin import build_twin
from .drift import snapshot_vector
from .envelope import build_envelope


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_validate(a):
    prog = load_program_bundle()
    rep = validate_program(prog, a.scenario)
    d = rep.to_dict()
    _emit(d)
    return 0 if d["valid"] else 1


def cmd_compile(a):
    prog = load_program_bundle()
    active, findings = compile_scenario(prog, a.scenario)
    edges = [e for e in prog.get("hyperedges", []) if active(e)]
    _emit({"scenario": a.scenario, "active_edges": len(edges),
           "findings": [f.to_dict() for f in findings]})
    return 0 if not any(f.severity == "P0" for f in findings) else 1


def cmd_ready(a):
    prog = load_program_bundle()
    active, _ = compile_scenario(prog, a.scenario)
    _emit({"scenario": a.scenario,
           "prerequisite_ready": sorted(prerequisite_ready_nodes(
               prog, active=active)),
           "gate_ready": sorted(ready_nodes(prog, active=active))})
    return 0


def cmd_criticality(a):
    prog = load_program_bundle()
    active, _ = compile_scenario(prog, a.scenario)
    out = {"scenario": a.scenario,
           "structural": structural_depth(prog, active)}
    durs = numeric_durations(prog)
    if durs:
        c = cpm(prog, durs, active)
        out["estimated"] = c
        out["display_critical_path"] = display_critical_path(c, prog, active)
    if a.mc:
        out["monte_carlo"] = monte_carlo_criticality(
            prog, samples=a.mc, seed=a.seed, active=active)
    _emit(out)
    return 0


def cmd_impact(a):
    prog = load_program_bundle()
    _emit(dependency_impact_cone(prog, set(a.node.split(","))))
    return 0


def cmd_rework_impact(a):
    prog = load_program_bundle()
    _emit(rework_impact_cone(prog, set(a.node.split(","))))
    return 0


def cmd_dominators(a):
    prog = load_program_bundle()
    _emit(program_dominators(prog, a.target, a.scenario))
    return 0


def cmd_cut_set(a):
    prog = load_program_bundle()
    _emit(milestone_cut_set(prog, a.target, a.scenario))
    return 0


def cmd_voi(a):
    prog = load_program_bundle()
    for u in prog.get("uncertainties", []):
        if u.get("uncertainty_id") == a.uncertainty:
            _emit(evaluate_voi(u))
            return 0
    _emit({"error": "UNKNOWN_UNCERTAINTY", "uncertainty": a.uncertainty})
    return 1


def cmd_twin(a):
    _emit(build_twin(load_program_bundle(), a.scenario))
    return 0


def cmd_drift(a):
    _emit(snapshot_vector(load_program_bundle(), a.scenario))
    return 0


def cmd_attest(a):
    prog = load_program_bundle()
    rep = validate_program(prog, a.scenario)
    env = build_envelope(prog, base_commit=prog.get("_meta", {}).get(
        "base_commit", ""), scenario_id=a.scenario)
    env["program_valid"] = rep.valid
    env["counts"] = rep.counts()
    _emit(env)
    return 0 if rep.valid else 1


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--scenario", default="BASELINE")
    p = argparse.ArgumentParser(prog="tools.program_graph", parents=[common],
                                description="Finalis Program Dependency & "
                                            "Uncertainty Constitution")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)
    sub.add_parser("compile", parents=[common]).set_defaults(func=cmd_compile)
    sub.add_parser("ready", parents=[common]).set_defaults(func=cmd_ready)
    cr = sub.add_parser("criticality", parents=[common])
    cr.add_argument("--mc", type=int, default=0)
    cr.add_argument("--seed", type=int, default=12345)
    cr.set_defaults(func=cmd_criticality)
    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--node", required=True); im.set_defaults(func=cmd_impact)
    ri = sub.add_parser("rework-impact", parents=[common])
    ri.add_argument("--node", required=True)
    ri.set_defaults(func=cmd_rework_impact)
    do = sub.add_parser("dominators", parents=[common])
    do.add_argument("--target", required=True)
    do.set_defaults(func=cmd_dominators)
    cs = sub.add_parser("cut-set", parents=[common])
    cs.add_argument("--target", required=True)
    cs.set_defaults(func=cmd_cut_set)
    vo = sub.add_parser("voi", parents=[common])
    vo.add_argument("--uncertainty", required=True)
    vo.set_defaults(func=cmd_voi)
    sub.add_parser("twin", parents=[common]).set_defaults(func=cmd_twin)
    sub.add_parser("drift", parents=[common]).set_defaults(func=cmd_drift)
    sub.add_parser("attest", parents=[common]).set_defaults(func=cmd_attest)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
