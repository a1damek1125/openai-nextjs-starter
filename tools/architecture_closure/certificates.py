"""Proof-Carrying Closure Certificates + Independent Certificate Checker
(SP0010 V5 FUNCTION W, §0, D-0010-83..90).

The closure reasoner (the "solver": positive-support closure + four-valued
epistemic classification) produces a verdict for each critical claim. That
verdict is NOT trusted on its own. For every critical claim the reasoner must
also emit a PROOF-CARRYING CERTIFICATE — a compact, self-contained witness that
a SMALL INDEPENDENT CHECKER can re-validate without re-running the solver:

  * the claimed epistemic state (must be SUPPORTED_ONLY to close),
  * the activating premise set (the conjunctive hyperedge premises) and the
    assertion that each is itself supported,
  * the minimal support witness (evidence-atom ids) and that each atom exists,
  * the independence class of the support.

The independent checker (`check_certificate`) re-derives the certificate hash and
re-checks each obligation with DIFFERENT code from the solver. THE GATE
(D-0010-84): a solver verdict WITHOUT a VALID certificate is **advisory only** —
it can never close a critical claim. A missing or invalid certificate on a
critical claim is a PROOF_HOLE (P0). This is the CEGAR/proof-carrying discipline
applied to compositional assurance: trust the checker, not the solver.

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, SUPPORTED_ONLY, CERTIFICATE_STATES)


def issue_certificate(*, claim_id: str, epistemic_state: str,
                      premises: list, supported_set: set, refuted_set: set,
                      support_set: list, atoms_by_id: dict,
                      independence_class: str) -> dict:
    """The solver issues a certificate carrying everything the checker needs.
    The solver does not decide validity — that is the checker's job. The
    obligations are computed the SAME way the independent checker re-derives them
    (from the ground-truth supported/refuted sets + atom→claim linkage), so a
    legitimate certificate's self-report agrees with the re-derivation."""
    truly_supported_only = (claim_id in supported_set
                            and claim_id not in refuted_set)
    obligations = {
        "state_is_supported_only": truly_supported_only
        and epistemic_state == SUPPORTED_ONLY,
        "premises_all_supported": all(p in supported_set for p in premises),
        "support_nonempty": bool(support_set),
        "atoms_exist": all(
            a in atoms_by_id
            and claim_id in atoms_by_id[a].get("claim_refs", [])
            for a in support_set),
    }
    cert = {
        "certificate_version": "1.0",
        "claim_id": claim_id,
        "claimed_state": epistemic_state,
        "premises": sorted(premises),
        "support_set": sorted(support_set),
        "independence_class": independence_class,
        "obligations": obligations,
    }
    cert["certificate_hash"] = hash_obj(
        {k: cert[k] for k in cert if k != "certificate_hash"})
    return cert


def check_certificate(cert: dict, *, claim_id: str, supported_set: set,
                      refuted_set: set, atoms_by_id: dict) -> dict:
    """The INDEPENDENT checker. This is the discipline's whole point (D-0010-84),
    so it must NOT trust anything the solver asserts. It re-derives the claim's
    epistemic state from the GROUND TRUTH sets it is given (supported_set /
    refuted_set) rather than trusting cert['claimed_state'] (red-team P1-A): the
    claim genuinely closes only when `claim_id ∈ supported_set` and
    `claim_id ∉ refuted_set`. It further requires every support atom to actually
    reference THIS claim (an atom for an unrelated claim is not evidence for it),
    re-hashes the certificate body, and rejects any certificate whose self-
    reported obligations disagree with the re-derivation. VALID only when every
    independent check holds."""
    problems = []
    if cert is None:
        return {"claim_id": claim_id, "state": "MISSING", "valid": False,
                "problems": ["no certificate issued"]}
    if cert.get("claim_id") != claim_id:
        problems.append("certificate claim_id mismatch")
    recomputed = hash_obj({k: cert[k] for k in cert
                           if k != "certificate_hash"})
    if recomputed != cert.get("certificate_hash"):
        problems.append("certificate hash does not recompute")
    # (1) INDEPENDENT epistemic re-derivation from ground truth — the solver's
    # claimed_state is checked FOR CONSISTENCY, never trusted as the source.
    truly_supported_only = (claim_id in supported_set
                            and claim_id not in refuted_set)
    if not truly_supported_only:
        problems.append("claim is not SUPPORTED_ONLY in the independent ground "
                        "truth (supported/refuted re-derivation)")
    if cert.get("claimed_state") != SUPPORTED_ONLY:
        problems.append("claimed state is not SUPPORTED_ONLY")
    # (2) premises independently supported
    for p in cert.get("premises", []):
        if p not in supported_set:
            problems.append(f"premise not supported: {p}")
    # (3) support atoms must exist AND actually reference this claim
    if not cert.get("support_set"):
        problems.append("empty support set")
    for a in cert.get("support_set", []):
        atom = atoms_by_id.get(a)
        if atom is None:
            problems.append(f"support atom absent from index: {a}")
        elif claim_id not in atom.get("claim_refs", []):
            problems.append(f"support atom {a} does not reference this claim")
    # (4) the certificate's self-reported obligations must AGREE with our
    # independent re-derivation (a certificate that lies about itself is invalid)
    reported = cert.get("obligations", {})
    rederived = {
        "state_is_supported_only": truly_supported_only
        and cert.get("claimed_state") == SUPPORTED_ONLY,
        "premises_all_supported": all(p in supported_set
                                      for p in cert.get("premises", [])),
        "support_nonempty": bool(cert.get("support_set")),
        "atoms_exist": all(
            a in atoms_by_id
            and claim_id in atoms_by_id[a].get("claim_refs", [])
            for a in cert.get("support_set", [])),
    }
    if reported != rederived:
        problems.append("certificate obligations disagree with re-derivation")
    valid = not problems
    state = "VALID" if valid else "INVALID"
    assert state in CERTIFICATE_STATES
    return {"claim_id": claim_id, "state": state, "valid": valid,
            "problems": problems}


def certify_closure(*, critical_claims: set, states: dict,
                    hyperedges: list, supported_set: set, refuted_set: set,
                    support_sets_by_claim: dict, atoms_by_id: dict,
                    independence_by_claim: dict) -> dict:
    """Issue + independently check a certificate for every critical claim, then
    compute the ADMISSIBLE closing set: a critical claim is admitted as CLOSED
    only if it is SUPPORTED_ONLY in the independent ground truth AND its
    certificate checks VALID. Claims lacking a valid certificate are PROOF_HOLES
    (advisory-only). The admission is driven by the independent VERDICT, not by
    the solver's self-reported state (red-team P1-A)."""
    premises_by_conclusion = {}
    for e in hyperedges:
        premises_by_conclusion.setdefault(
            e["conclusion_claim_ref"], []).extend(e["premise_claim_refs"])
    certs = {}
    verdicts = {}
    for cid in sorted(critical_claims):
        st = states.get(cid, {}).get("state", "NEITHER")
        premises = sorted(set(premises_by_conclusion.get(cid, [])))
        support = (support_sets_by_claim.get(cid, [[]]) or [[]])[0]
        cert = issue_certificate(
            claim_id=cid, epistemic_state=st, premises=premises,
            supported_set=supported_set, refuted_set=refuted_set,
            support_set=support, atoms_by_id=atoms_by_id,
            independence_class=independence_by_claim.get(cid, "UNKNOWN"))
        certs[cid] = cert
        verdicts[cid] = check_certificate(
            cert, claim_id=cid, supported_set=supported_set,
            refuted_set=refuted_set, atoms_by_id=atoms_by_id)
    # a claim CLOSES iff its independent verdict is VALID (which itself requires
    # SUPPORTED_ONLY in the ground truth) — the solver's claimed state alone
    # never closes a claim.
    admitted_closed = sorted(cid for cid in critical_claims
                             if verdicts[cid]["valid"])
    proof_holes = sorted(
        cid for cid in critical_claims
        if states.get(cid, {}).get("state") == SUPPORTED_ONLY
        and not verdicts[cid]["valid"])
    return {
        "certificates": certs,
        "verdicts": verdicts,
        "admitted_closed": admitted_closed,
        "proof_holes": proof_holes,
        "all_certified": not proof_holes,
        "certificate_root": hash_obj(
            {cid: certs[cid]["certificate_hash"] for cid in sorted(certs)}),
    }


def certificate_findings(certification: dict, critical_claims: set,
                         states: dict) -> list[Finding]:
    out: list[Finding] = []
    for cid in sorted(certification["proof_holes"]):
        out.append(Finding(
            "PROOF_HOLE", P0, cid,
            "critical claim's solver verdict is SUPPORTED_ONLY but carries no "
            "VALID proof-carrying certificate: advisory only, cannot close "
            "(D-0010-84)",
            {"verdict": certification["verdicts"][cid]["problems"]}))
    return out
