"""Evidence-carrying Qualification Credits + proof-carrying certificate + the
INDEPENDENT credit checker (SP0011 §2.2, §11.3, §11.25, §12.3, D-0011-008/019/020,
AC-0011-044..052, 166..168).

Each of the 200 qualification claims is worth exactly FIVE indivisible credits.
A claim receives its 5 credits ONLY when a valid proof-carrying Qualification
Credit Certificate is accepted by the independent checker. Every award binds the
exact configuration root and Program Seal; a solver/generator/judge result WITHOUT
a valid certificate cannot award a credit (D-0011-008). The checker re-derives
every obligation from ground truth it is given — it does not trust the issuer's
self-report. Missing / stale / refuted evidence, unmet maturity, a failed hard
gate, an out-of-scope statistical certificate, or a blocking defeater ⇒ ZERO
official credits (diagnostic progress is reported separately, never scored).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, CREDIT_PER_CLAIM, maturity_meets)


def issue_certificate(*, claim_id: str, configuration_root: str,
                      program_seal: str, evidence_refs: list,
                      evidence_domain_refs: list, oracle_certificate_refs: list,
                      statistical_certificate_ref, required_maturity: str,
                      achieved_maturity: str, hard_gate_results: dict,
                      valid_from: str, valid_until, defeater_refs: list,
                      kernel_version: str, evidence_current: bool,
                      evidence_present: bool, evidence_refuted: bool,
                      statistical_required: bool, statistical_pass: bool,
                      oracle_valid: bool) -> dict:
    """The issuer (untrusted) assembles a certificate. It computes obligations the
    SAME way the checker re-derives them, so a legitimate certificate agrees with
    the independent re-derivation; it does NOT itself decide the award."""
    obligations = _derive_obligations(
        evidence_present=evidence_present, evidence_current=evidence_current,
        evidence_refuted=evidence_refuted,
        maturity_ok=maturity_meets(achieved_maturity, required_maturity),
        statistical_required=statistical_required,
        statistical_pass=statistical_pass, oracle_valid=oracle_valid,
        hard_gate_results=hard_gate_results, defeater_refs=defeater_refs)
    cert = {
        "certificate_version": "1.0", "claim_id": claim_id,
        "configuration_root": configuration_root, "program_seal": program_seal,
        "evidence_refs": sorted(evidence_refs),
        "evidence_domain_refs": sorted(evidence_domain_refs),
        "oracle_certificate_refs": sorted(oracle_certificate_refs),
        "statistical_certificate_ref": statistical_certificate_ref,
        "required_maturity": required_maturity,
        "achieved_maturity": achieved_maturity,
        "hard_gate_results": {k: bool(v) for k, v in
                              sorted(hard_gate_results.items())},
        "valid_from": valid_from, "valid_until": valid_until,
        "defeater_refs": sorted(defeater_refs),
        "kernel_version": kernel_version,
        "obligations": obligations,
        "credit_value": CREDIT_PER_CLAIM,
    }
    cert["certificate_hash"] = hash_obj(
        {k: cert[k] for k in cert if k != "certificate_hash"})
    return cert


def _derive_obligations(*, evidence_present, evidence_current, evidence_refuted,
                        maturity_ok, statistical_required, statistical_pass,
                        oracle_valid, hard_gate_results, defeater_refs) -> dict:
    return {
        "evidence_present": evidence_present is True,
        "evidence_current": evidence_current is True,
        "evidence_not_refuted": evidence_refuted is False,
        "maturity_sufficient": maturity_ok is True,
        "statistical_ok": (not statistical_required) or (statistical_pass is True),
        "oracle_valid": oracle_valid is True,
        "hard_gates_pass": all(bool(v) for v in hard_gate_results.values()),
        "no_blocking_defeater": len(defeater_refs) == 0,
    }


def check_certificate(cert: dict, *, expected_configuration_root: str,
                      expected_program_seal: str, ground_truth: dict) -> dict:
    """The INDEPENDENT checker (Trusted Evaluation Kernel). Red-team P0-1: it does
    NOT trust the certificate's self-reported obligations OR self-reported
    maturity/evidence — those are attacker-set. Instead it is handed an
    INDEPENDENT `ground_truth` the KERNEL re-derived (from the trusted claims
    registry + on-disk evidence resolution + the kernel's own hard-gate
    evaluation), and it awards ONLY when:

      * the certificate hash recomputes and binds the exact configuration root +
        Program Seal (integrity),
      * the certificate's claim_id / required_maturity / achieved_maturity EQUAL
        the kernel-derived ground truth (a forged M5/lowered-required cert is
        rejected because the kernel recomputed the real values from disk), and
      * the GROUND TRUTH itself satisfies every obligation (evidence present on
        disk, current, unrefuted; achieved ≥ required; oracle valid; statistical
        ok; hard gates pass; no defeater).

    Public config_root/program_seal equality is integrity binding, not the award
    basis — the award rests on the kernel's independent ground truth."""
    problems = []
    if cert is None or ground_truth is None:
        return {"valid": False, "awarded": False, "credits": 0,
                "claim_id": None, "problems": ["no certificate or ground truth"]}
    if hash_obj({k: cert[k] for k in cert if k != "certificate_hash"}) \
            != cert.get("certificate_hash"):
        problems.append("certificate hash does not recompute")
    if cert.get("configuration_root") != expected_configuration_root:
        problems.append("certificate configuration_root mismatch")
    if cert.get("program_seal") != expected_program_seal:
        problems.append("certificate program_seal mismatch")
    # the certificate's identity + maturity claims MUST equal the kernel's
    # independent ground truth (defeats forged maturity/required inflation)
    if cert.get("claim_id") != ground_truth.get("claim_id"):
        problems.append("certificate claim_id mismatch vs ground truth")
    if cert.get("required_maturity") != ground_truth.get("required_maturity"):
        problems.append("certificate required_maturity != kernel ground truth")
    if cert.get("achieved_maturity") != ground_truth.get("achieved_maturity"):
        problems.append("certificate achieved_maturity != kernel ground truth")
    # the AWARD rests entirely on the KERNEL-DERIVED ground truth
    gt_ok = {
        "evidence_present": ground_truth.get("evidence_present") is True,
        "evidence_current": ground_truth.get("evidence_current") is True,
        "evidence_not_refuted": ground_truth.get("evidence_refuted") is False,
        "maturity_sufficient": maturity_meets(
            ground_truth.get("achieved_maturity", ""),
            ground_truth.get("required_maturity", "")),
        "oracle_valid": ground_truth.get("oracle_valid") is True,
        "statistical_ok": ground_truth.get("statistical_ok") is True,
        "hard_gates_pass": ground_truth.get("hard_gate_pass") is True,
        "no_blocking_defeater": len(ground_truth.get("defeater_refs", [])) == 0,
    }
    for name, ok in sorted(gt_ok.items()):
        if ok is not True:
            problems.append(f"ground-truth obligation not met: {name}")
    valid = not problems
    return {"valid": valid, "awarded": valid,
            "credits": CREDIT_PER_CLAIM if valid else 0,
            "claim_id": cert.get("claim_id"), "problems": problems}


def credit_root(certificates: list) -> str:
    """Merkle-free deterministic root over awarded certificate hashes."""
    return hash_obj(sorted(c["certificate_hash"] for c in certificates
                           if c.get("certificate_hash")))


def credit_findings(checked: list) -> list[Finding]:
    """A certificate that was ISSUED for a critical claim but fails the checker is
    surfaced (the claim simply gets 0 credits; this is diagnostic, not a P0 —
    unmet maturity/evidence is the expected honest state). Only a forged cert
    whose configuration/seal mismatch is a hard finding."""
    out: list[Finding] = []
    for rec in checked:
        for p in rec.get("problems", []):
            if "mismatch" in p or "does not recompute" in p:
                out.append(Finding(
                    "CREDIT_CERTIFICATE_INVALID", P0,
                    str(rec.get("claim_id", "-")),
                    f"credit certificate integrity failure: {p}", {}))
    return out
