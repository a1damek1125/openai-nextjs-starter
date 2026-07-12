"""Safety Kernel & Assurance CLI (SP0005 §15).

    python -m tools.safety inventory
    python -m tools.safety validate
    python -m tools.safety hazards
    python -m tools.safety regulatory-status
    python -m tools.safety scenarios
    python -m tools.safety assurance
    python -m tools.safety debt
    python -m tools.safety drift
    python -m tools.safety attest --case <id>

Deterministic, --json, no network, no external effect. Exit 1 iff the safety model
is invalid (P0/P1). Never imports product code.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .loader import load_program
from .validate import validate_all
from .hazards import traceability
from .barriers import minimal_cut_sets
from .scenarios import coverage_report
from .debt import assurance_debt, drift_snapshot
from .envelope import safety_case_envelope


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_inventory(a):
    p = load_program()
    _emit({"losses": len(p["losses"]), "hazards": len(p["hazards"]),
           "threats": len(p["threats"]), "controls": len(p["controls"]),
           "action_contracts": len(p["action_contracts"]),
           "trajectory_contracts": len(p["trajectory_contracts"]),
           "claims": len(p["claims"]), "sources": len(p["sources"]),
           "scenarios": len(p["scenarios"]),
           "use_cases": len(p["use_cases"])})
    return 0


def cmd_validate(a):
    rep = validate_all(load_program())
    _emit(rep.to_dict())
    return 0 if rep.valid else 1


def cmd_hazards(a):
    p = load_program()
    _emit({"findings": [f.to_dict() for f in traceability(p)]})
    return 0


def cmd_regulatory(a):
    p = load_program()
    by_status = {}
    for s in p["sources"]:
        by_status.setdefault(s.get("source_status", "?"), []).append(
            s.get("source_id"))
    _emit({"sources_by_status": {k: sorted(v) for k, v in by_status.items()}})
    return 0


def cmd_scenarios(a):
    _emit(coverage_report(load_program()["scenarios"]))
    return 0


def cmd_assurance(a):
    p = load_program()
    rep = validate_all(p)
    _emit(assurance_debt(rep.to_dict(), p))
    return 0


def cmd_debt(a):
    p = load_program()
    rep = validate_all(p)
    _emit(assurance_debt(rep.to_dict(), p))
    return 0 if assurance_debt(rep.to_dict(), p)["safety_gate"] == "PASS" else 1


def cmd_drift(a):
    p = load_program()
    _emit(drift_snapshot(p, validate_all(p).to_dict()))
    return 0


def cmd_attest(a):
    p = load_program()
    case = {"case_id": a.case, "claims": p["claims"], "hazards": p["hazards"],
            "action_contracts": p["action_contracts"],
            "trajectory_contracts": p["trajectory_contracts"],
            "proof_obligations": p["proof_obligations"], "controls": p["controls"],
            "evidence": p["evidence"], "defeaters": p["defeaters"],
            "regulatory_context": p["sources"]}
    env = safety_case_envelope(case)
    rep = validate_all(p)
    env["safety_valid"] = rep.valid
    env["counts"] = rep.counts()
    _emit(env)
    return 0 if rep.valid else 1


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    p = argparse.ArgumentParser(prog="tools.safety", parents=[common],
                                description="Finalis Safety Kernel, Assurance & "
                                            "Regulatory Truth Constitution")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory", parents=[common]).set_defaults(func=cmd_inventory)
    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)
    sub.add_parser("hazards", parents=[common]).set_defaults(func=cmd_hazards)
    sub.add_parser("regulatory-status", parents=[common]).set_defaults(
        func=cmd_regulatory)
    sub.add_parser("scenarios", parents=[common]).set_defaults(func=cmd_scenarios)
    sub.add_parser("assurance", parents=[common]).set_defaults(func=cmd_assurance)
    sub.add_parser("debt", parents=[common]).set_defaults(func=cmd_debt)
    sub.add_parser("drift", parents=[common]).set_defaults(func=cmd_drift)
    at = sub.add_parser("attest", parents=[common])
    at.add_argument("--case", default="SC-1"); at.set_defaults(func=cmd_attest)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
