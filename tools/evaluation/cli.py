"""FINALIS Evaluation CLI (SP0011 §15): deterministic canonical-JSON answers to
the evaluation questions. No secrets, no external effects, no live provider."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (evaluation as eval_mod, validate as validate_mod, freeze,
               admit, configuration, tcb, claims, genome as genome_mod)
from .canon import canonical_json

_COMPACT = False


def _emit(obj) -> int:
    print(canonical_json(obj) if _COMPACT
          else json.dumps(obj, indent=2, sort_keys=True))
    return 0


def _twin(args) -> dict:
    if getattr(args, "from_file", None):
        return validate_mod.load_evaluation(Path(args.from_file))
    return eval_mod.build_evaluation(Path(args.root))


def cmd_roadmap_identity(a) -> int:
    return _emit({"mission": "SP0011",
                  "canonical_title": "FINALIS Evaluation, Reliability and "
                  "1000/1000 Evidence Qualification Constitution",
                  "predecessor": "SP0010", "successor": "post-constitution",
                  "scope_decision": "PROCEED (equivalent to declared successor)",
                  "boundary": ["no product change", "frontier v27",
                               "no live effect", "no fabricated score"]})


def cmd_admit(a) -> int:
    return _emit(admit.admit_program_seal(Path(a.root)))


def cmd_freeze(a) -> int:
    return _emit(freeze.freeze(Path(a.root)))


def cmd_configuration(a) -> int:
    return _emit(configuration.build_configuration(Path(a.root)))


def cmd_tcb(a) -> int:
    return _emit(tcb.build_manifest(Path(a.root)))


def cmd_claims(a) -> int:
    return _emit({"domain_registry": claims.domain_registry(),
                  "claims": claims.build_claims(Path(a.root))})


def _section(a, key):
    return _emit(_twin(a)[key])


def cmd_credits(a): return _section(a, "credit_awards")
def cmd_coverage(a): return _section(a, "coverage_summary")
def cmd_scenarios(a): return _section(a, "viktor_scenarios")
def cmd_challenge_escrow(a): return _section(a, "challenge_escrow")
def cmd_oracles(a): return _section(a, "oracles")
def cmd_contamination(a): return _section(a, "contamination_ledger")
def cmd_robust(a): return _section(a, "robust")
def cmd_long_horizon(a): return _section(a, "long_horizon")
def cmd_causal(a): return _section(a, "causal")
def cmd_calibration(a): return _section(a, "calibration")
def cmd_judges(a): return _section(a, "judges")
def cmd_invariance(a): return _section(a, "invariance")
def cmd_providers(a): return _section(a, "replaceability")
def cmd_fidelity(a): return _section(a, "fidelity_registry")
def cmd_drift(a): return _section(a, "requalification_cone")
def cmd_hard_gates(a): return _section(a, "hard_gates")
def cmd_envelope(a): return _section(a, "qualification_envelope")
def cmd_genome(a): return _section(a, "evaluation_genome")
def cmd_seal(a): return _section(a, "evaluation_seal")


def cmd_score(a) -> int:
    t = _twin(a)
    return _emit({"scorecard": t["scorecard"], "maturity": t["maturity"],
                  "finalis_1000_state": t["finalis_1000_state"],
                  "counts": t["counts"]})


def cmd_verify_seal(a) -> int:
    t = _twin(a)
    frz = freeze.freeze(Path(a.root))
    problems = genome_mod.verify_seal(t["evaluation_seal"],
                                      expected_commit=frz["starting_head"])
    return _emit({"valid": not problems, "problems": problems})


def cmd_dossier(a) -> int:
    t = _twin(a)
    return _emit({k: t[k] for k in (
        "evaluation_system_state", "product_state", "finalis_1000_state",
        "maturity", "counts", "scorecard", "qualification_envelope",
        "hard_gates", "evaluation_genome", "evaluation_seal")})


def cmd_validate(a) -> int:
    t = _twin(a)
    rep = validate_mod.validate_evaluation(t, Path(a.root))
    _emit(rep.as_dict())
    return 0 if rep.valid else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluation",
                                description="FINALIS Evaluation (SP0011)")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, from_file=True):
        sp = sub.add_parser(name)
        if from_file:
            sp.add_argument("--from", dest="from_file")
        sp.set_defaults(func=fn)

    add("roadmap_identity", cmd_roadmap_identity, False)
    add("admit_program_seal", cmd_admit, False)
    add("freeze", cmd_freeze, False)
    add("configuration", cmd_configuration, False)
    add("tcb", cmd_tcb, False)
    add("claims", cmd_claims, False)
    for name, fn in (("credits", cmd_credits), ("coverage", cmd_coverage),
                     ("scenarios", cmd_scenarios),
                     ("challenge_escrow", cmd_challenge_escrow),
                     ("oracles", cmd_oracles), ("contamination", cmd_contamination),
                     ("robust", cmd_robust), ("long_horizon", cmd_long_horizon),
                     ("causal", cmd_causal), ("calibration", cmd_calibration),
                     ("judges", cmd_judges), ("invariance", cmd_invariance),
                     ("providers", cmd_providers), ("fidelity", cmd_fidelity),
                     ("drift", cmd_drift), ("hard_gates", cmd_hard_gates),
                     ("envelope", cmd_envelope), ("genome", cmd_genome),
                     ("seal", cmd_seal), ("score", cmd_score),
                     ("verify_seal", cmd_verify_seal), ("dossier", cmd_dossier),
                     ("validate", cmd_validate)):
        add(name, fn)
    return p


def main(argv=None) -> int:
    global _COMPACT
    args = build_parser().parse_args(argv)
    _COMPACT = bool(getattr(args, "json", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
