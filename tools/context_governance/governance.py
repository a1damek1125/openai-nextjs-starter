"""End-to-end Context Governance orchestrator (TOOL-B10 §7, §8, §12; the
build_capsule pipeline binds every subsystem into one proof-carrying result).

Pipeline (fail-closed at every stage):
  boundary  -> entitlement -> snapshot/version-vector -> lease
  -> evidence-before-belief -> four-valued claims -> taint / air-gap
  -> requirement hypergraph + minimal bases -> mandatory reservation
  -> robust submodular selection under budget + VOI
  -> claim-preserving compaction -> conflict-preserving merge
  -> least-privilege views + noninterference + privacy budget
  -> ABI render + consumption receipt (truncation) -> proof of non-use
  -> capsule body + certificate (GENERATOR)
  -> INDEPENDENT checker + replay twin + TCB + transparency

The orchestrator NEVER authorizes work: it emits a Context Capsule that INFORMS.
Any P0/P1 finding makes the resulting Report invalid and the capsule is withheld
(state INCOMPLETE / *_BLOCKED). Reference kernel only; no external effect.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1, report
from . import boundary, entitlement as ent_mod, evidence as ev_mod
from . import requirements as req_mod, compile as comp_mod, capsule as cap_mod


def _token_of(claim: dict) -> int:
    return int(claim.get("tokens", 1))


def build_capsule(request: dict, *, generator_id: str = "ctxgov-generator",
                  checker_id: str = "ctxgov-checker") -> dict:
    """Run the full governance pipeline over a self-contained ``request`` dict.

    The request carries only in-memory reference objects (no live handles). The
    return value is {"report", "capsule", "findings", "state", ...}. The capsule
    is present only when the report is valid (zero P0/P1)."""
    findings: list[Finding] = []

    # 0. boundary — the kernel performs only pure computation
    findings += boundary.boundary_findings(
        request.get("requested_operations", ["PURE_COMPUTE"]))

    # 1. entitlement before retrieval (fail-closed)
    ent = request.get("entitlement")
    acc = request.get("provider_account_id", "")
    findings += ent_mod.check_entitlement(
        ent, tenant_id=request["tenant_id"],
        principal_id=request["principal_id"], provider_account_id=acc,
        purpose=request["purpose"], operation_class=request["operation_class"],
        now=request.get("now", ""))

    # 2. snapshot + version vector + lease + TOCTOU revalidation
    reval = request.get("revalidation")
    if reval is not None:
        findings += ent_mod.toctou_findings(reval)

    # 3. evidence-before-belief, claims, taint, authority air-gap
    claims = request.get("claims", [])
    critical_ids = set(request.get("critical_claim_ids", []))
    evidence = request.get("evidence", [])
    findings += ev_mod.claim_findings(claims, critical_ids=critical_ids)
    findings += ev_mod.taint_findings(claims, critical_ids=critical_ids)
    findings += ev_mod.authority_air_gap(evidence)
    findings += ev_mod.memory_findings(request.get("memory_candidates", []))

    # 4. requirement hypergraph + minimal bases
    evidence_by_id = {e["evidence_id"]: e for e in evidence
                      if "evidence_id" in e}
    reqs = request.get("requirements", [])
    evaluations = [req_mod.evaluate_requirement(r, claims,
                                                evidence_by_id=evidence_by_id)
                   for r in reqs]
    findings += req_mod.requirement_findings(evaluations)

    # 5. mandatory reservation + robust selection under budget + VOI
    claims_by_id = {c["claim_id"]: c for c in claims}
    reserved = req_mod.reserve_mandatory(evaluations, claims_by_id,
                                         token_of=_token_of)
    selection = req_mod.robust_select(
        [c["claim_id"] for c in claims], claims_by_id,
        budget=request.get("token_budget", 10 ** 9), token_of=_token_of,
        reserved=set(reserved["reserved_claim_ids"]),
        scenarios=request.get("robustness_scenarios", []))
    findings += req_mod.selection_findings(selection, reserved)
    if request.get("voi") is not None:
        findings += req_mod.voi_findings(request["voi"])
    if request.get("conformal") is not None:
        findings += req_mod.statistics_findings(request["conformal"])

    selected_ids = set(selection["selected_ids"])
    selected_claims = [claims_by_id[c] for c in sorted(selected_ids)
                       if c in claims_by_id]

    # 6. claim-preserving compaction
    if request.get("compaction") is not None:
        cc = request["compaction"]
        cert = comp_mod.compaction(original_claims=cc["original"],
                                   retained_claims=cc["retained"],
                                   critical_ids=critical_ids)
        findings += comp_mod.compaction_findings(cert)

    # 7. conflict-preserving merge
    if request.get("branches"):
        merge = comp_mod.merge_branches(request["branches"], claims_by_id,
                                        critical_ids=critical_ids)
        findings += comp_mod.merge_findings(merge)

    # 8. views + noninterference + privacy budget
    cap_fields = request.get("capsule_fields", {})
    views = [comp_mod.compile_view(cap_fields, view_class=v)
             for v in request.get("view_classes", [])]
    findings += comp_mod.view_findings(views, request.get("noninterference"))
    if request.get("privacy") is not None:
        pv = request["privacy"]
        exposure = comp_mod.privacy_exposure(pv["exposures"],
                                             comp_mod.privacy_budget(pv["limits"]))
        findings += comp_mod.privacy_findings(exposure)

    # 9. ABI render + consumption receipt (truncation)
    if views and reval is not None:
        rendered = comp_mod.render_abi(views[0])
        receipt = comp_mod.consumption_receipt(
            render=rendered, lease_revalidation=reval,
            provider_reported_len=request.get("provider_reported_len"))
        findings += comp_mod.receipt_findings(receipt)

    # 10. proof of non-use
    findings += comp_mod.non_use_findings(request.get("non_use_certs", []))

    rep = report(findings)

    # 11. capsule — built only if valid; independently checked; replay twin
    capsule = None
    check = None
    state = "SEALED"
    if rep.valid and request.get("snapshot") and request.get("version_vector"):
        bom = cap_mod.context_bom(request.get("bom_entries", []))
        risk = cap_mod.risk_envelope(
            taint_max=request.get("taint_max", "UNTAINTED"),
            unresolved_conflicts=request.get("unresolved_conflicts", []),
            common_mode_atoms=request.get("common_mode_atoms", []),
            guarantee_active=request.get("guarantee_active", True),
            privacy_within_budget=request.get("privacy_within_budget", True),
            truncation=request.get("truncation", "NONE"))
        tcb = cap_mod.tcb_manifest(present=request.get(
            "tcb_present", list(cap_mod.TCB_COMPONENTS)))
        support_bases = {e["req_id"]: e["minimal_support_bases"]
                         for e in evaluations}
        body = cap_mod.build_capsule(
            snapshot=request["snapshot"],
            version_vector=request["version_vector"], entitlement=ent,
            selected_claims=selected_claims, support_bases=support_bases,
            bom=bom, risk=risk, tcb=tcb)
        capsule = cap_mod.certify_capsule(body, generator_id=generator_id)
        check = cap_mod.check_capsule(capsule, checker_id=checker_id)
        check_findings = cap_mod.capsule_findings(check)
        if check_findings:
            findings += check_findings
            rep = report(findings)
            capsule = None
            state = "CERTIFICATE_INVALID"
    else:
        state = "INCOMPLETE"

    result = {"report": rep.as_dict(), "valid": rep.valid,
              "state": "SEALED" if (capsule and rep.valid) else state,
              "capsule": capsule, "check": check,
              "reservation": reserved, "selection": selection,
              "evaluations": [e["evaluation_hash"] for e in evaluations]}
    result["result_hash"] = hash_obj({"v": rep.valid, "s": result["state"],
                                       "c": capsule["certificate"]["capsule_root"]
                                       if capsule else None})
    return result
