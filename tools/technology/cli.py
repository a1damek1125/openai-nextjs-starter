"""Continuous Technology Sovereignty CLI (SP0004 §15).

    python -m tools.technology inventory
    python -m tools.technology validate
    python -m tools.technology decision      --id TDR-0001
    python -m tools.technology compare        --technology-class model_provider
    python -m tools.technology fitness
    python -m tools.technology common-mode
    python -m tools.technology exit-readiness  --technology <id>
    python -m tools.technology impact          --decision <id>
    python -m tools.technology freshness
    python -m tools.technology attest          --decision <id>

Deterministic, --json, no network. Exit 1 iff the technology model is invalid
(P0/P1). Never imports product code.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .loader import load_program
from .validate import validate_all
from .inventory import inventory_stats
from .decisions import tdr_index, freshness_findings
from .fitness import evaluate_fitness, fitness_summary
from .depgraph import detect_common_mode
from .exit_readiness import evaluate_exit, exit_readiness_index, profile_for
from .survivability import impact_cone
from .envelope import decision_envelope
from .observatory import snapshot

TODAY = "2026-07-11"


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_inventory(a):
    _emit(inventory_stats(load_program().get("inventory", {})))
    return 0


def cmd_validate(a):
    rep = validate_all(load_program(), today=TODAY)
    _emit(rep.to_dict())
    return 0 if rep.valid else 1


def cmd_decision(a):
    d = tdr_index(load_program().get("decision_registry", {})).get(a.id)
    _emit(d or {"error": "UNKNOWN_DECISION", "id": a.id})
    return 0 if d else 1


def cmd_compare(a):
    prog = load_program()
    techs = [t for t in prog.get("inventory", {}).get("technologies", [])
             if t.get("technology_class") == a.technology_class]
    _emit({"technology_class": a.technology_class,
           "technologies": [t["technology_id"] for t in techs]})
    return 0


def cmd_fitness(a):
    prog = load_program()
    findings = evaluate_fitness(prog, today=TODAY)
    _emit({**fitness_summary(findings),
           "findings": [f.to_dict() for f in findings]})
    return 0 if fitness_summary(findings)["hard_failures"] == 0 else 1


def cmd_common_mode(a):
    prog = load_program()
    findings = detect_common_mode(prog.get("dependency_graph", {}),
                                  prog.get("provider_groups", []))
    _emit({"findings": [f.to_dict() for f in findings]})
    return 0


def cmd_exit(a):
    prog = load_program()
    prof = profile_for(prog.get("exit_profiles", []), a.technology)
    if prof is None:
        _emit({"error": "NO_EXIT_PROFILE", "technology": a.technology})
        return 1
    _emit({"technology": a.technology, "profile": prof,
           "index": exit_readiness_index(prof)})
    return 0


def cmd_impact(a):
    prog = load_program()
    d = tdr_index(prog.get("decision_registry", {})).get(a.decision, {})
    _emit(impact_cone(prog.get("dependency_graph", {}), d))
    return 0


def cmd_freshness(a):
    prog = load_program()
    fs = freshness_findings(prog.get("decision_registry", {}), today=TODAY)
    _emit({"findings": [f.to_dict() for f in fs]})
    return 0


def cmd_attest(a):
    prog = load_program()
    d = tdr_index(prog.get("decision_registry", {})).get(a.decision)
    if d is None:
        _emit({"error": "UNKNOWN_DECISION", "id": a.decision})
        return 1
    # bind the decision's ACTUAL Pareto + sensitivity + regret analyses into the
    # envelope so they are attested, not left inert (SWARM-M item 2).
    from .pareto import pareto_frontier
    from .sensitivity import sensitivity, minimax_regret
    analyses = {
        "pareto": pareto_frontier(d.get("candidates", []), d.get("criteria", [])),
        "sensitivity": sensitivity(d),
        "scenario": minimax_regret(d),
    }
    _emit(decision_envelope(d, analyses=analyses))
    return 0


def cmd_observatory(a):
    _emit(snapshot(load_program(), today=TODAY))
    return 0


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    p = argparse.ArgumentParser(prog="tools.technology", parents=[common],
                                description="Finalis Continuous Technology "
                                            "Sovereignty Constitution")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory", parents=[common]).set_defaults(func=cmd_inventory)
    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)
    d = sub.add_parser("decision", parents=[common])
    d.add_argument("--id", required=True); d.set_defaults(func=cmd_decision)
    c = sub.add_parser("compare", parents=[common])
    c.add_argument("--technology-class", required=True)
    c.set_defaults(func=cmd_compare)
    sub.add_parser("fitness", parents=[common]).set_defaults(func=cmd_fitness)
    sub.add_parser("common-mode", parents=[common]).set_defaults(
        func=cmd_common_mode)
    e = sub.add_parser("exit-readiness", parents=[common])
    e.add_argument("--technology", required=True); e.set_defaults(func=cmd_exit)
    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--decision", required=True); im.set_defaults(func=cmd_impact)
    sub.add_parser("freshness", parents=[common]).set_defaults(func=cmd_freshness)
    at = sub.add_parser("attest", parents=[common])
    at.add_argument("--decision", required=True); at.set_defaults(func=cmd_attest)
    sub.add_parser("observatory", parents=[common]).set_defaults(
        func=cmd_observatory)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
