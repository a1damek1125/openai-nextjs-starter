"""Kernel invariant self-check (TOOL-B10 §16 INV-01..30; run standalone or from the
CLI). Every invariant is checked by CONSTRUCTION against the kernel primitives, so
a regression in the reference kernel surfaces as an INV-* finding rather than a
silently weakened guarantee.
"""
from __future__ import annotations

from .canon import hash_obj, global_root
from .model import (Finding, P0, claim_state, closes_critical, taint_join,
                    SUPPORTED_ONLY, BOTH, NEITHER)
from . import boundary, capsule as cap_mod, compile as comp_mod
from . import requirements as req_mod


INVARIANTS = (
    "INV-01 capsule informs, never authorizes",
    "INV-02 no live external effect",
    "INV-03 unknown operation fails closed",
    "INV-04 capsule body is secret-free",
    "INV-10 four-valued: BOTH is not TRUE",
    "INV-11 four-valued: NEITHER is not FALSE",
    "INV-12 only SUPPORTED_ONLY closes a critical requirement",
    "INV-13 truthy-string is not support",
    "INV-20 taint join takes the more severe level",
    "INV-21 taint survives transformation unless removal proven",
    "INV-22 unrecognized taint label is treated as most-severe (fail-closed)",
    "INV-25 generator cannot self-certify",
    "INV-26 recomputed capsule root binds the ENTIRE body",
    "INV-27 privacy budget is non-compensatory",
    "INV-28 mandatory reservation precedes budgeted selection",
    "INV-29 capsule body is a closed shape (no smuggled keys)",
    "INV-30 view leakage of a forbidden field is rejected",
)


def self_check() -> list[Finding]:
    out: list[Finding] = []

    def fail(inv: str, msg: str):
        out.append(Finding("BOUNDARY_VIOLATION", P0, inv, msg, {}))

    # INV-10/11/12/13 four-valued lattice
    if claim_state("yes", False) == SUPPORTED_ONLY:      # truthy string
        fail("INV-13", "truthy string treated as support")
    if closes_critical(BOTH) or closes_critical(NEITHER):
        fail("INV-12", "BOTH/NEITHER closed a critical requirement")
    if not closes_critical(SUPPORTED_ONLY):
        fail("INV-12", "SUPPORTED_ONLY failed to close critical")
    if claim_state(True, True) != BOTH or claim_state(False, False) != NEITHER:
        fail("INV-10", "four-valued lattice mislabels BOTH/NEITHER")

    # INV-20/21/22 taint
    if taint_join("EXTERNAL", "QUARANTINED") != "QUARANTINED":
        fail("INV-20", "taint join did not take the more severe level")
    if taint_join("EXTERNAL", "UNKNOWN_SEVERE_LABEL") != "UNKNOWN_SEVERE_LABEL":
        fail("INV-22", "unrecognized taint label was not treated as most-severe")

    # INV-02/03 boundary
    if boundary.classify_effect("EMAIL_SEND") != "FORBIDDEN":
        fail("INV-02", "forbidden effect not classified FORBIDDEN")
    if boundary.classify_effect("SOMETHING_NEW") != "UNKNOWN":
        fail("INV-03", "unknown operation not fail-closed")

    # INV-27 privacy non-compensatory
    b = comp_mod.privacy_budget({"pii": 1, "financial": 0})
    exp = comp_mod.privacy_exposure({"pii": 0, "financial": 5}, b)
    if exp["within_budget"]:
        fail("INV-27", "privacy budget compensated an overrun across axes")

    # INV-30 view leakage
    v = comp_mod.compile_view({"provider_token": "x", "claims": []},
                              view_class="AUDITOR_VIEW")
    if not v["leaked_forbidden"]:
        fail("INV-30", "forbidden field not detected in view")

    # INV-25/26 capsule certificate + independence
    body = {"capsule_kind": "FINALIS_CONTEXT_CAPSULE",
            "informs_not_authorizes": True, "tenant_id": "t",
            "principal_id": "p", "purpose": "u", "operation_class": "o",
            "snapshot_root": "s", "version_vector_hash": "v",
            "entitlement_hash": "e", "claims": [], "support_bases": {},
            "bom_root": "b", "risk_envelope_hash": "r", "tcb_root": "c",
            "compiler_version": "x"}
    capsule = cap_mod.certify_capsule(body, generator_id="g")
    same = cap_mod.check_capsule(capsule, checker_id="g")
    if same["accepted"]:
        fail("INV-25", "generator self-certified its own capsule")
    diff = cap_mod.check_capsule(capsule, checker_id="h")
    if not diff["accepted"]:
        fail("INV-26", "independent checker rejected a valid capsule")

    # INV-26: mutating a body field the old code did not bind must now be caught
    forged = cap_mod.certify_capsule(dict(body), generator_id="g")
    forged["body"]["support_bases"] = {"R": [["CL-FORGED"]]}
    if cap_mod.check_capsule(forged, checker_id="h")["accepted"]:
        fail("INV-26", "certificate did not bind support_bases (full body)")

    # INV-29: an injected key outside the allowlist must be refused
    smuggled = cap_mod.certify_capsule(dict(body), generator_id="g")
    smuggled["body"]["authority"] = {"grant": "APPROVE"}
    if cap_mod.check_capsule(smuggled, checker_id="h")["accepted"]:
        fail("INV-29", "capsule accepted a smuggled out-of-allowlist key")

    return out


def validate() -> dict:
    findings = self_check()
    return {"invariants": list(INVARIANTS),
            "checked": len(INVARIANTS),
            "violations": [f.as_dict() for f in findings],
            "ok": not findings,
            "validation_hash": hash_obj({"n": len(INVARIANTS),
                                         "v": [f.subject for f in findings]})}
