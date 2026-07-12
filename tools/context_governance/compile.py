"""Claim-Preserving Compaction + Conflict-Preserving Branch/Merge + Least-Privilege
Views + Privacy Exposure Budget + Noninterference + Proof-of-Non-Use +
Model-Context ABI + Consumption Receipts + Provider Truncation Detection (TOOL-B10
§P/Q/AF/AG/AH/AI/AJ/AK, Innovations 6/7/8/11/12/13, §11.8..11.12, §12.10..12.16,
D-B6-081..100, 191..240).

Compaction is a SEMANTIC contract, not byte reduction: a summary is admissible
only if it PRESERVES every critical claim, its negation/polarity, quantities,
scope, uncertainty, contradictions and provenance (Innovation 6). Branch/merge
keeps conflicting hypotheses SEPARATE and never merges a critical conflict into a
false consensus, and never lets a merge amplify authority. Views are
least-privilege projections per consumer class; noninterference means a
high-sensitivity input never changes a low-view's bytes. The privacy exposure
budget is a NON-COMPENSATORY vector — abundance on one axis cannot pay for
exhaustion on another. Proof-of-non-use certifies that an excluded item did not
influence the output. The model-context ABI renders bytes deterministically and a
consumption receipt binds the exact bytes a provider will see, detecting silent
truncation (fail-closed on UNKNOWN).

Reference kernel only; standard library only; opens no external effect; never
emits provider tokens or secrets into any rendered view or receipt.
"""
from __future__ import annotations

from .canon import hash_obj, canonical_json, sha256_hex
from .model import (Finding, P0, P1, P2, VIEW_CLASSES, CONSUMER_CLASSES,
                    closes_critical)


# --- claim-preserving compaction ---------------------------------------------
_INVARIANTS = ("claims", "polarity", "quantity", "unit", "scope",
               "uncertainty", "contradiction", "provenance")


def _claim_fingerprint(c: dict) -> dict:
    return {"id": c["claim_id"], "polarity": c.get("polarity"),
            "state": c.get("support_state"), "quantity": c.get("quantity"),
            "unit": c.get("unit"), "scope": c.get("scope") or {},
            "taint": sorted(c.get("taint_refs", [])),
            "evidence": sorted(c.get("evidence_refs", []))}


def compaction(*, original_claims: list, retained_claims: list,
               critical_ids: set) -> dict:
    """Verify a compaction preserves the semantic invariants over CRITICAL claims.
    Returns a certificate enumerating any violated invariant (Innovation 6)."""
    orig = {c["claim_id"]: _claim_fingerprint(c) for c in original_claims}
    kept = {c["claim_id"]: _claim_fingerprint(c) for c in retained_claims}
    violations = []
    for cid in sorted(critical_ids):
        if cid not in orig:
            continue
        if cid not in kept:
            violations.append(("COMPRESSION_CLAIM_LOSS", cid))
            continue
        o, k = orig[cid], kept[cid]
        if o["polarity"] != k["polarity"]:
            violations.append(("COMPRESSION_NEGATION_CHANGED", cid))
        if o["state"] != k["state"]:
            violations.append(("COMPRESSION_CONTRADICTION_LOST", cid))
        if o["quantity"] != k["quantity"] or o["unit"] != k["unit"]:
            violations.append(("COMPRESSION_QUANTITY_CHANGED", cid))
        if o["scope"] != k["scope"]:
            violations.append(("COMPRESSION_SCOPE_CHANGED", cid))
        if o["evidence"] != k["evidence"]:
            violations.append(("COMPRESSION_PROVENANCE_LOST", cid))
        if o["taint"] != k["taint"]:
            # compaction must not launder taint off a critical claim
            violations.append(("COMPRESSION_TAINT_STRIPPED", cid))
    cert = {"original_count": len(original_claims),
            "retained_count": len(retained_claims),
            "critical_count": len(critical_ids),
            "violations": [[v[0], v[1]] for v in violations],
            "preserved": not violations}
    cert["compaction_hash"] = hash_obj(cert)
    return cert


def compaction_findings(cert: dict) -> list[Finding]:
    out: list[Finding] = []
    for kind, cid in cert.get("violations", []):
        out.append(Finding(kind, P0, cid,
                           f"compaction violated a critical invariant ({kind})",
                           {}))
    return out


# --- conflict-preserving branch / merge --------------------------------------
def branch(*, base_snapshot_root: str, hypothesis: str, claim_refs: list,
           tenant_id: str) -> dict:
    b = {"base_snapshot_root": base_snapshot_root, "hypothesis": hypothesis,
         "tenant_id": tenant_id, "claim_refs": sorted(claim_refs)}
    b["branch_hash"] = hash_obj(b)
    b["branch_id"] = "BR-" + b["branch_hash"][:16]
    return b


def merge_branches(branches: list, claims_by_id: dict, *,
                   critical_ids: set) -> dict:
    """Merge keeps conflicting hypotheses SEPARATE. A critical atom that is
    SUPPORTED_ONLY on one branch and REFUTED/BOTH on another is a preserved
    CONFLICT — never collapsed into a consensus (Innovation 7, D-B6-082/083).
    A merge may never increase authority."""
    atom_states: dict = {}
    for br in branches:
        for cid in br["claim_refs"]:
            c = claims_by_id.get(cid, {})
            for atom in c.get("discharges", []):
                atom_states.setdefault(atom, set()).add(
                    c.get("support_state", "NEITHER"))
    conflicts = []
    for atom in sorted(atom_states):
        states = atom_states[atom]
        supp = "SUPPORTED_ONLY" in states
        refu = bool({"REFUTED_ONLY", "BOTH"} & states)
        if supp and refu:
            conflicts.append(atom)
    critical_conflicts = sorted(a for a in conflicts
                                if a in critical_ids)
    base = {b["base_snapshot_root"] for b in branches}
    result = {"branch_ids": sorted(b["branch_id"] for b in branches),
              "conflicts": sorted(conflicts),
              "critical_conflicts": critical_conflicts,
              "shared_base": len(base) == 1,
              "merged_consensus": False if conflicts else True}
    result["merge_hash"] = hash_obj(result)
    return result


def merge_findings(merge: dict) -> list[Finding]:
    out: list[Finding] = []
    if not merge.get("shared_base"):
        out.append(Finding("BRANCH_BASE_MISMATCH", P1, "merge",
                           "branches do not share a base snapshot", {}))
    for atom in merge.get("critical_conflicts", []):
        out.append(Finding("MERGE_CRITICAL_CONFLICT", P0, atom,
                           "critical atom is both supported and refuted across "
                           "branches: conflict preserved, not merged", {}))
    return out


# --- least-privilege views + noninterference ---------------------------------
# what each consumer view is ALLOWED to carry (least privilege, D-B6-091..095)
_VIEW_GRANTS = {
    "PLANNER_VIEW": {"claims", "requirements", "provenance"},
    "REASONING_MODEL_VIEW": {"claims", "provenance", "uncertainty"},
    "TOOL_GATEWAY_VIEW": {"entitlement_scope", "operation_class"},
    "HUMAN_APPROVER_VIEW": {"claims", "provenance", "uncertainty",
                            "contradictions"},
    "AUDITOR_VIEW": {"claims", "provenance", "uncertainty", "contradictions",
                     "receipts", "certificate"},
    "DOWNSTREAM_AGENT_VIEW": {"claims"},
    "CUSTOMER_RENDER_VIEW": {"claims"},
    "MEMORY_WRITEBACK_REVIEW_VIEW": {"claims", "provenance", "evidence_lineage"},
}
# fields that must NEVER appear in any view (secrets/authority/tokens)
_FORBIDDEN_FIELDS = frozenset({"provider_token", "secret", "api_key",
                               "credential", "authority_grant", "answer_key",
                               "raw_secret"})


def compile_view(capsule_fields: dict, *, view_class: str) -> dict:
    """Project a capsule to a least-privilege view. Fields outside the view's
    grant are dropped; forbidden fields are never rendered."""
    assert view_class in VIEW_CLASSES, view_class
    grant = _VIEW_GRANTS.get(view_class, set())
    projected = {k: v for k, v in capsule_fields.items()
                 if k in grant and k not in _FORBIDDEN_FIELDS}
    leaked = sorted(k for k in capsule_fields
                    if k in _FORBIDDEN_FIELDS)
    view = {"view_class": view_class, "fields": sorted(projected),
            "leaked_forbidden": leaked,
            "view_bytes_hash": hash_obj(projected)}
    return view


def noninterference(*, low_view_high: dict, low_view_low: dict) -> dict:
    """A high-sensitivity input must not change the bytes of a low view. Given the
    same low view compiled under two high-input worlds, their byte hashes must be
    equal (Innovation 12, D-B6-096/097)."""
    ok = low_view_high.get("view_bytes_hash") == low_view_low.get(
        "view_bytes_hash")
    return {"noninterference_ok": bool(ok),
            "a": low_view_high.get("view_bytes_hash"),
            "b": low_view_low.get("view_bytes_hash")}


def view_findings(views: list, noninterf: dict = None) -> list[Finding]:
    out: list[Finding] = []
    for v in views:
        if v.get("leaked_forbidden"):
            out.append(Finding("VIEW_LEAKAGE", P0, v["view_class"],
                               "forbidden field(s) present in view: "
                               f"{v['leaked_forbidden']}", {}))
    if noninterf is not None and not noninterf.get("noninterference_ok"):
        out.append(Finding("NONINTERFERENCE_FAILED", P0, "view",
                           "a high-sensitivity input changed a low view's bytes",
                           {}))
    return out


# --- privacy exposure budget (non-compensatory) ------------------------------
_PRIVACY_AXES = ("pii", "financial", "health", "biometric", "location",
                 "cross_tenant")


def privacy_budget(limits: dict) -> dict:
    return {"limits": {a: int(limits.get(a, 0)) for a in _PRIVACY_AXES},
            "budget_hash": hash_obj({a: int(limits.get(a, 0))
                                     for a in _PRIVACY_AXES})}


def privacy_exposure(exposures: dict, budget: dict) -> dict:
    """Non-compensatory vector check (Innovation 11, D-B6-088): each axis is
    compared independently; slack on one axis can NEVER offset an overrun on
    another. Any single overrun fails."""
    over = []
    for a in _PRIVACY_AXES:
        used = int(exposures.get(a, 0))
        if used > budget["limits"][a]:
            over.append({"axis": a, "used": used,
                         "limit": budget["limits"][a]})
    # an exposure on an UNKNOWN axis has no budget: it fails closed rather than
    # being silently ignored (red-team fix)
    for a in sorted(exposures):
        if a not in _PRIVACY_AXES and int(exposures.get(a, 0)) > 0:
            over.append({"axis": a, "used": int(exposures[a]), "limit": 0})
    return {"within_budget": not over, "overruns": over,
            "exposure_hash": hash_obj({"o": over})}


def privacy_findings(exposure: dict) -> list[Finding]:
    out: list[Finding] = []
    for o in exposure.get("overruns", []):
        out.append(Finding("PRIVACY_EXPOSURE_EXCEEDED", P0, o["axis"],
                           f"privacy exposure on {o['axis']} exceeds budget "
                           f"({o['used']} > {o['limit']}); non-compensatory", {}))
    return out


# --- proof of non-use --------------------------------------------------------
def proof_of_non_use(*, excluded_ref: str, output_hash: str,
                     output_without_excluded_hash: str) -> dict:
    """Certify an excluded item did NOT influence the output: the output computed
    WITH the item withheld is byte-identical to the delivered output (Innovation
    8, D-B6-085). If they differ the item influenced the result — non-use fails."""
    unused = output_hash == output_without_excluded_hash
    cert = {"excluded_ref": excluded_ref, "output_hash": output_hash,
            "counterfactual_hash": output_without_excluded_hash,
            "non_use_proven": bool(unused)}
    cert["non_use_hash"] = hash_obj(cert)
    return cert


def non_use_findings(certs: list) -> list[Finding]:
    out: list[Finding] = []
    for c in certs:
        if not c.get("non_use_proven"):
            out.append(Finding("PROOF_OF_NON_USE_FAILED", P1, c["excluded_ref"],
                               "excluded item influenced the output "
                               "(non-use not proven)", {}))
    return out


# --- model-context ABI + consumption receipt + truncation --------------------
ABI_VERSION = "ctxgov-abi-1.0"
SUPPORTED_ABI = frozenset({ABI_VERSION})


def render_abi(view: dict, *, abi_version: str = ABI_VERSION) -> dict:
    """Deterministic byte rendering for a provider/model. The rendered bytes are
    canonical JSON of the view fields; the byte hash is the ABI commitment."""
    if abi_version not in SUPPORTED_ABI:
        return {"abi_version": abi_version, "supported": False,
                "rendered_bytes": "", "byte_len": 0, "byte_hash": None}
    body = canonical_json({"view_class": view["view_class"],
                           "fields": view["fields"],
                           "view_bytes_hash": view["view_bytes_hash"]})
    return {"abi_version": abi_version, "supported": True,
            "rendered_bytes": body, "byte_len": len(body.encode("utf-8")),
            "byte_hash": sha256_hex(body)}


def consumption_receipt(*, render: dict, lease_revalidation: dict,
                        provider_reported_len=None) -> dict:
    """Bind the EXACT bytes a provider will consume and detect silent truncation.
    If the provider-reported length is missing => UNKNOWN (fail-closed); if it
    differs from the rendered length => truncation DETECTED (Innovation 13)."""
    if not render.get("supported"):
        trunc = "UNKNOWN"
    elif provider_reported_len is None:
        trunc = "UNKNOWN"
    elif int(provider_reported_len) != render["byte_len"]:
        trunc = "DETECTED"
    else:
        trunc = "NONE"
    lease_ok = lease_revalidation.get("verdict") in (
        "VALID", "VALID_WITH_NONMATERIAL_DELTA")
    receipt = {"abi_version": render.get("abi_version"),
               "rendered_byte_hash": render.get("byte_hash"),
               "rendered_len": render.get("byte_len"),
               "provider_reported_len": provider_reported_len,
               "truncation": trunc, "lease_valid": bool(lease_ok),
               "state": "CONSUMED" if (trunc == "NONE" and lease_ok)
               else "REJECTED"}
    receipt["receipt_hash"] = hash_obj(receipt)
    return receipt


def receipt_findings(receipt: dict) -> list[Finding]:
    out: list[Finding] = []
    if not SUPPORTED_ABI or receipt.get("abi_version") not in SUPPORTED_ABI:
        out.append(Finding("ABI_VERSION_UNSUPPORTED", P0, "abi",
                           f"unsupported ABI version {receipt.get('abi_version')}",
                           {}))
    if receipt.get("truncation") == "DETECTED":
        out.append(Finding("PROVIDER_TRUNCATION_DETECTED", P0, "receipt",
                           "provider truncated the rendered context "
                           f"(reported {receipt.get('provider_reported_len')} vs "
                           f"{receipt.get('rendered_len')})", {}))
    elif receipt.get("truncation") == "UNKNOWN":
        out.append(Finding("PROVIDER_TRUNCATION_UNKNOWN", P1, "receipt",
                           "provider consumed length unknown: cannot prove no "
                           "truncation (fail-closed)", {}))
    if not receipt.get("lease_valid"):
        out.append(Finding("CONSUMPTION_RECEIPT_INVALID", P0, "receipt",
                           "lease invalid at consumption time", {}))
    return out
