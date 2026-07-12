"""Release assurance CLI (SP0009 §15): deterministic canonical-JSON answers to
the release questions. No secret values, no external effects, no deployment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bootstrap, validate as validate_mod, archaeology, gates, \
    classify, modelcheck, boundary
from .canon import canonical_json

_COMPACT = False


def _emit(obj) -> int:
    print(canonical_json(obj) if _COMPACT
          else json.dumps(obj, indent=2, sort_keys=True))
    return 0


def _twin(args) -> dict:
    if getattr(args, "from_file", None):
        return validate_mod.load_twin(Path(args.from_file))
    return bootstrap.build_twin(Path(args.root))


def cmd_roadmap_identity(args) -> int:
    return _emit({
        "mission": "SP0009",
        "canonical_title": "Release Train, Quality Gates and Definition of "
                           "Done",
        "extended_title": "FINALIS Release Assurance, Quality Gates, "
                          "Definition of Done & Proof-Carrying Promotion "
                          "Constitution",
        "predecessors": ["SP0007", "SP0008"],
        "successors": ["SP0010", "SP0011"],
        "boundary": ["zero live deployment", "zero product migration "
                     "(frontier v27)", "zero production credentials",
                     "zero external effect", "no SP0011 evidence"],
    })


def cmd_archaeology(args) -> int:
    return _emit(archaeology.release_archaeology(Path(args.root)))


def cmd_classify(args) -> int:
    paths = args.paths or []
    c = classify.classify_paths(paths)
    return _emit({"classification": c, "risk_vector": classify.risk_vector(c)})


def cmd_create_candidate(args) -> int:
    t = _twin(args)
    return _emit(t["candidate"])


def cmd_impact(args) -> int:
    return _emit(_twin(args)["impact_cone"])


def cmd_slice(args) -> int:
    return _emit(_twin(args)["release_slice"])


def cmd_plan_gates(args) -> int:
    t = _twin(args)
    return _emit({"plan": t["gate_plan"], "results": t["gate_results"],
                  "verdict": t["gate_verdict"]})


def cmd_select_tests(args) -> int:
    return _emit(_twin(args)["test_selection"])


def cmd_flakes(args) -> int:
    t = _twin(args)
    return _emit({"classification": t["flake_classification"],
                  "posterior": t["flake_posterior"]})


def cmd_flake_clusters(args) -> int:
    return _emit(_twin(args)["flake_clusters"])


def cmd_rerun_ledger(args) -> int:
    t = _twin(args)
    return _emit({"attempts": t["execution_ledger"],
                  "accounting": t["rerun_accounting"]})


def cmd_build_manifest(args) -> int:
    return _emit(_twin(args)["build_manifest"])


def cmd_reproduce(args) -> int:
    return _emit(_twin(args)["reproducibility"])


def cmd_builder_quorum(args) -> int:
    return _emit(_twin(args)["attestation_quorum"])


def cmd_artifact_closure(args) -> int:
    return _emit(_twin(args)["artifact_closure"])


def cmd_verify_attestations(args) -> int:
    return _emit(_twin(args)["attestations"])


def cmd_verify_trust(args) -> int:
    return _emit(_twin(args)["trust_roots"])


def cmd_verify_transparency(args) -> int:
    return _emit(_twin(args)["transparency_receipts"])


def cmd_sbom(args) -> int:
    return _emit(_twin(args)["sbom"])


def cmd_ai_bom(args) -> int:
    return _emit(_twin(args)["ai_ml_bom"])


def cmd_ci_taint(args) -> int:
    return _emit(_twin(args)["ci_security_posture"])


def cmd_ai_closure(args) -> int:
    t = _twin(args)
    return _emit({"closure": t["ai_release_closure"],
                  "sp0011": t["sp0011_qualification"]})


def cmd_dod(args) -> int:
    t = _twin(args)
    return _emit({"obligations": t["obligations"],
                  "closure": t["dod_closure"]})


def cmd_defeaters(args) -> int:
    return _emit({"open_defeaters": [],
                  "note": "no defeater is currently open for RC-SP0009"})


def cmd_qualify(args) -> int:
    t = _twin(args)
    return _emit({"qualification": t["qualification"],
                  "candidate_status": t["candidate"]["status"],
                  "unknown_budget": t["unknown_budget"]})


def cmd_attest(args) -> int:
    t = _twin(args)
    return _emit({"release_envelope": t["release_envelope"],
                  "twin_digest": t["twin_digest"]})


def cmd_validate(args) -> int:
    root = Path(args.root)
    t = _twin(args)
    rep = validate_mod.validate_twin(t, root)
    _emit(rep.as_dict())
    return 0 if rep.valid else 1


def cmd_dossier(args) -> int:
    t = _twin(args)
    return _emit({k: t[k] for k in (
        "candidate", "classification", "risk_vector", "impact_cone",
        "gate_verdict", "dod_closure", "rerun_accounting",
        "flake_classification", "reproducibility", "artifact",
        "artifact_closure", "attestation_quorum", "sbom", "ai_ml_bom",
        "progressive_delivery", "qualification", "release_envelope")})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="release", description="FINALIS Release Assurance (SP0009)")
    p.add_argument("--root", default=".")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *, from_file=True, extra=None):
        sp = sub.add_parser(name)
        if from_file:
            sp.add_argument("--from", dest="from_file")
        if extra:
            extra(sp)
        sp.set_defaults(func=fn)

    add("roadmap_identity", cmd_roadmap_identity, from_file=False)
    add("archaeology", cmd_archaeology, from_file=False)
    add("classify", cmd_classify, from_file=False,
        extra=lambda sp: sp.add_argument("paths", nargs="*"))
    add("create_candidate", cmd_create_candidate)
    add("impact", cmd_impact)
    add("slice", cmd_slice)
    add("plan_gates", cmd_plan_gates)
    add("select_tests", cmd_select_tests)
    add("flakes", cmd_flakes)
    add("flake_clusters", cmd_flake_clusters)
    add("rerun_ledger", cmd_rerun_ledger)
    add("build_manifest", cmd_build_manifest)
    add("reproduce", cmd_reproduce)
    add("builder_quorum", cmd_builder_quorum)
    add("artifact_closure", cmd_artifact_closure)
    add("verify_attestations", cmd_verify_attestations)
    add("verify_trust", cmd_verify_trust)
    add("verify_transparency", cmd_verify_transparency)
    add("sbom", cmd_sbom)
    add("ai_bom", cmd_ai_bom)
    add("ci_taint", cmd_ci_taint)
    add("ai_closure", cmd_ai_closure)
    add("dod", cmd_dod)
    add("defeaters", cmd_defeaters)
    add("qualify", cmd_qualify)
    add("attest", cmd_attest)
    add("validate", cmd_validate)
    add("dossier", cmd_dossier)
    return p


def main(argv=None) -> int:
    global _COMPACT
    args = build_parser().parse_args(argv)
    _COMPACT = bool(getattr(args, "json", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
