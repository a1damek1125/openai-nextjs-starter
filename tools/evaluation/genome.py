"""Evaluation Genome (Merkle forest of all material roots) + Evaluation Seal
(SP0011 §10.18, §10.19, §11.28, §12.19, D-0011-114/115, AC-0011-293..300).

The genome binds every material evaluation root (configuration, dataset, challenge
escrow, scenario, oracle, metric, statistical-plan, judge, human-review, outcome-
evidence, credit-certificate, qualification-envelope, trusted-kernel, scorecard)
into one deterministic global evaluation root; any root change moves it. The
Evaluation Seal binds the repository commit, the SP0010 Program Seal, the genome
root, the configuration, the scorecard and the envelope. THE SEAL CREATES NO
RUNTIME AUTHORITY (D-0011-115). A material root change invalidates it.
"""
from __future__ import annotations

from .canon import global_root, core_hash

REQUIRED_ROOTS = ("configuration_root", "dataset_root", "challenge_escrow_root",
                  "scenario_root", "oracle_root", "metric_root",
                  "statistical_plan_root", "judge_root", "human_review_root",
                  "outcome_evidence_root", "credit_certificate_root",
                  "qualification_envelope_root", "trusted_kernel_root",
                  "scorecard_root")


def build_genome(roots: dict) -> dict:
    class_roots = {k: roots.get(k, "ABSENT") for k in REQUIRED_ROOTS}
    g = {"genome_version": "1.0.0", **{f"{k}": class_roots[k]
                                       for k in class_roots},
         "class_roots": class_roots}
    g["global_evaluation_root"] = global_root(class_roots)
    return g


def verify_genome(genome: dict) -> bool:
    return genome.get("global_evaluation_root") == global_root(
        genome.get("class_roots", {}))


def build_seal(*, repository_commit: str, program_seal: str,
               evaluation_genome_root: str, configuration_id: str,
               scorecard_id: str, qualification_envelope_id: str,
               total_credits: int, maturity: str, hard_gate_state: str,
               critical_blockers: int, independent_verifier_result: str,
               sealed_at: str, valid_until) -> dict:
    seal = {
        "seal_version": "1.0.0", "repository_commit": repository_commit,
        "program_seal": program_seal,
        "evaluation_genome_root": evaluation_genome_root,
        "configuration_id": configuration_id, "scorecard_id": scorecard_id,
        "qualification_envelope_id": qualification_envelope_id,
        "total_credits": total_credits, "maturity": maturity,
        "hard_gate_state": hard_gate_state, "critical_blockers": critical_blockers,
        "independent_verifier_result": independent_verifier_result,
        "grants_runtime_authority": False,     # never (D-0011-115)
        "sealed_at": sealed_at, "valid_until": valid_until,
        "status": "CANDIDATE",
    }
    seal["seal_hash"] = core_hash(seal)
    return seal


def verify_seal(seal: dict, *, expected_commit: str) -> list:
    problems = []
    if seal.get("repository_commit") != expected_commit:
        problems.append("seal repository_commit does not match snapshot")
    recomputed = core_hash({k: seal[k] for k in seal if k != "seal_hash"})
    if seal.get("seal_hash") != recomputed:
        problems.append("seal hash does not recompute")
    if seal.get("grants_runtime_authority") is not False:
        problems.append("evaluation seal must not grant runtime authority")
    if seal.get("hard_gate_state") not in ("PASS", "FAIL"):
        problems.append("seal hard_gate_state missing")
    return problems
