"""Architecture Assurance Closure CLI (SP0010 §15): deterministic canonical-JSON
answers to the closure questions. No secret values, no external effects, no
deployment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (closure as closure_mod, validate as validate_mod, freeze,
               describe, interfaces as iface_mod, crosstwin, noninterference,
               counterfactual, boundary)
from .canon import canonical_json

_COMPACT = False


def _emit(obj) -> int:
    print(canonical_json(obj) if _COMPACT
          else json.dumps(obj, indent=2, sort_keys=True))
    return 0


def _closure(args) -> dict:
    if getattr(args, "from_file", None):
        return validate_mod.load_closure(Path(args.from_file))
    return closure_mod.build_closure(Path(args.root))


def cmd_roadmap_identity(args) -> int:
    return _emit({
        "mission": "SP0010",
        "canonical_title": "FINALIS Architecture Program Final Gate",
        "extended_title": "Architecture Assurance Closure, Constitutional "
                          "Coherence & Program Seal",
        "predecessors": ["SP0000", "SP0001", "SP0002", "SP0003", "SP0004",
                         "SP0005", "SP0006", "SP0007", "SP0008", "SP0009"],
        "successors": ["SP0011"],
        "scope_decision": "Program-registry node labels SP0010 'Global Brand "
                          "Naming Sprint' (stale placeholder, no outputs); the "
                          "SP-AUTHOR-0000 mission + the SP0000-SP0009 "
                          "constitutional arc + SP0011=Evaluation successor "
                          "establish Architecture Program Final Gate as the "
                          "canonical SP0010 scope. Proceeding under a "
                          "documented non-silent reassignment (SP0006 "
                          "precedent); the naming activity is recorded as an "
                          "ACCEPTED_FUTURE_ENHANCEMENT gap, registry unedited.",
        "boundary": ["zero product runtime change", "zero product migration "
                     "(frontier v27)", "zero external effect", "no SP0011 "
                     "score", "verifier not self-certifying"],
    })


def cmd_freeze(args) -> int:
    return _emit(freeze.freeze(Path(args.root)))


def cmd_describe(args) -> int:
    return _emit(describe.build_description(Path(args.root)))


def cmd_interfaces(args) -> int:
    return _emit(iface_mod.build_interfaces(Path(args.root)))


def cmd_hypergraph(args) -> int:
    return _emit(_closure(args)["assurance_hypergraph"])


def cmd_support_closure(args) -> int:
    return _emit(_closure(args)["positive_support"])


def cmd_epistemic_states(args) -> int:
    t = _closure(args)
    return _emit({"summary": t["epistemic_summary"],
                  "states": t["epistemic_states"]})


def cmd_defeaters(args) -> int:
    return _emit(_closure(args)["defeater_resolution"])


def cmd_circularity(args) -> int:
    return _emit(_closure(args)["circularity"])


def cmd_cross_twin(args) -> int:
    return _emit(_closure(args)["cross_twin_matrix"])


def cmd_invariants(args) -> int:
    return _emit(_closure(args)["global_invariants"])


def cmd_noninterference(args) -> int:
    return _emit(_closure(args)["hyperproperties"])


def cmd_counterfactual_control(args) -> int:
    return _emit(_closure(args)["counterfactual_controls"])


def cmd_resilience(args) -> int:
    return _emit(_closure(args)["assurance_resilience"])


def cmd_gaps(args) -> int:
    return _emit(_closure(args)["gap_ledger"])


def cmd_bootstrap_verify(args) -> int:
    return _emit(_closure(args)["bootstrap_ceremony"])


def cmd_genome(args) -> int:
    return _emit(_closure(args)["architecture_genome"])


def cmd_seal(args) -> int:
    return _emit(_closure(args)["program_seal"])


def cmd_verify_seal(args) -> int:
    from . import seal as seal_mod
    t = _closure(args)
    frz = freeze.freeze(Path(args.root))
    problems = seal_mod.verify_seal(t["program_seal"],
                                    expected_commit=frz["head"])
    return _emit({"valid": not problems, "problems": problems,
                  "closure_state": t["program_seal"]["closure_state"]})


def cmd_sp0011_admission(args) -> int:
    return _emit(_closure(args)["sp0011_admission"])


def cmd_assurance(args) -> int:
    t = _closure(args)
    return _emit({"epistemic_summary": t["epistemic_summary"],
                  "minimal_support_sets": t["minimal_support_sets"],
                  "common_mode": t["evidence_common_mode"]})


def cmd_dual_graph(args) -> int:
    return _emit(_closure(args)["dual_graph"])


def cmd_extraction_firewall(args) -> int:
    return _emit(_closure(args)["extraction_firewall"])


def cmd_tcb(args) -> int:
    return _emit(_closure(args)["tcb_manifest"])


def cmd_certificates(args) -> int:
    return _emit(_closure(args)["certification"])


def cmd_causal(args) -> int:
    return _emit(_closure(args)["causal_controls"])


def cmd_cegar(args) -> int:
    return _emit(_closure(args)["cegar"])


def cmd_robustness_frontier(args) -> int:
    return _emit(_closure(args)["robustness_frontier"])


def cmd_federation(args) -> int:
    return _emit(_closure(args)["federation"])


def cmd_repair_portfolio(args) -> int:
    return _emit(_closure(args)["repair_portfolio"])


def cmd_dossier(args) -> int:
    t = _closure(args)
    return _emit({k: t[k] for k in (
        "closure_epoch", "epistemic_summary", "conformance_matrix",
        "global_invariants", "hyperproperties", "counterfactual_controls",
        "gap_ledger", "architecture_genome", "bootstrap_ceremony",
        "program_seal", "sp0011_admission", "counts",
        "dual_graph", "tcb_manifest", "certification", "causal_controls",
        "cegar", "robustness_frontier", "federation", "repair_portfolio")})


def cmd_validate(args) -> int:
    root = Path(args.root)
    t = _closure(args)
    rep = validate_mod.validate_closure(t, root)
    _emit(rep.as_dict())
    return 0 if rep.valid else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="architecture_closure",
        description="FINALIS Architecture Assurance Closure (SP0010)")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *, from_file=True):
        sp = sub.add_parser(name)
        if from_file:
            sp.add_argument("--from", dest="from_file")
        sp.set_defaults(func=fn)

    add("roadmap_identity", cmd_roadmap_identity, from_file=False)
    add("freeze", cmd_freeze, from_file=False)
    add("describe", cmd_describe, from_file=False)
    add("interfaces", cmd_interfaces, from_file=False)
    add("hypergraph", cmd_hypergraph)
    add("support_closure", cmd_support_closure)
    add("epistemic_states", cmd_epistemic_states)
    add("defeaters", cmd_defeaters)
    add("circularity", cmd_circularity)
    add("cross_twin", cmd_cross_twin)
    add("invariants", cmd_invariants)
    add("noninterference", cmd_noninterference)
    add("counterfactual_control", cmd_counterfactual_control)
    add("resilience", cmd_resilience)
    add("gaps", cmd_gaps)
    add("bootstrap_verify", cmd_bootstrap_verify)
    add("genome", cmd_genome)
    add("seal", cmd_seal)
    add("verify_seal", cmd_verify_seal)
    add("sp0011_admission", cmd_sp0011_admission)
    add("assurance", cmd_assurance)
    # V5 subsystems
    add("dual_graph", cmd_dual_graph)
    add("extraction_firewall", cmd_extraction_firewall)
    add("tcb", cmd_tcb)
    add("certificates", cmd_certificates)
    add("causal", cmd_causal)
    add("cegar", cmd_cegar)
    add("robustness_frontier", cmd_robustness_frontier)
    add("federation", cmd_federation)
    add("repair_portfolio", cmd_repair_portfolio)
    add("dossier", cmd_dossier)
    add("validate", cmd_validate)
    return p


def main(argv=None) -> int:
    global _COMPACT
    args = build_parser().parse_args(argv)
    _COMPACT = bool(getattr(args, "json", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
