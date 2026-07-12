"""Proof-Carrying Context Capsule + Context BOM + Risk Envelope + Certificate +
INDEPENDENT Certificate Checker + Context TCB Manifest + SCITT Transparency
Projection + Robustness Frontier + Replay Twin (TOOL-B10 §AL/AM/AN/AO/AP/AQ/AR,
Innovations 15/16/17/18, §11.13..11.16, §12.18..12.24, D-B6-241..320).

A Context Capsule is a POINT-IN-TIME, LEAST-PRIVILEGE, PROOF-CARRYING object: it
carries the snapshot root, the version vector, the entitlement scope, the selected
claims with their four-valued states, the minimal support bases, the risk
envelope, the Context BOM (every input by id+hash+provider account +
independence class), and a CERTIFICATE that binds all of it. The capsule INFORMS
but NEVER AUTHORIZES (INV-01): it contains no authority grant, no provider token,
no secret.

Role separation is structural (D-B6-300..305): the GENERATOR builds the
certificate; a byte-independent CHECKER re-derives every root from the capsule
body ALONE and accepts only if it matches — a generator can never self-certify.
The replay twin recomputes the capsule from the same snapshot and must reproduce
the identical root (determinism). The Context TCB manifest enumerates exactly the
components trusted to produce the guarantee.

Reference kernel only; standard library only; opens no external effect; the
capsule body is asserted secret-free before sealing.
"""
from __future__ import annotations

from .canon import (hash_obj, canonical_json, class_root, global_root,
                    merkle_root)
from .model import (Finding, P0, P1, P2, closes_critical)


# --- Context BOM -------------------------------------------------------------
def bom_entry(*, ref: str, kind: str, content_hash: str, provider_account: str,
              independence_class: str, taint: str, version: str) -> dict:
    """One input line of the Context Bill of Materials."""
    e = {"ref": ref, "kind": kind, "content_hash": content_hash,
         "provider_account": provider_account,
         "independence_class": independence_class, "taint": taint,
         "version": version}
    e["entry_hash"] = hash_obj(e)
    return e


def context_bom(entries: list) -> dict:
    """Complete, ordered bill of materials; its root binds every input."""
    ordered = sorted(entries, key=lambda e: e["entry_hash"])
    return {"entries": ordered,
            "entry_count": len(ordered),
            "bom_root": class_root([e["entry_hash"] for e in ordered])}


# --- risk envelope -----------------------------------------------------------
def risk_envelope(*, taint_max: str, unresolved_conflicts: list,
                  common_mode_atoms: list, guarantee_active: bool,
                  privacy_within_budget: bool, truncation: str) -> dict:
    """A conservative summary of residual risk carried WITH the capsule so a
    downstream consumer sees the worst case explicitly (never hidden)."""
    env = {"taint_max": taint_max,
           "unresolved_conflicts": sorted(unresolved_conflicts),
           "common_mode_atoms": sorted(common_mode_atoms),
           "statistical_guarantee_active": bool(guarantee_active),
           "privacy_within_budget": bool(privacy_within_budget),
           "truncation": truncation}
    env["envelope_hash"] = hash_obj(env)
    return env


# --- Context TCB manifest ----------------------------------------------------
TCB_COMPONENTS = ("canon", "model", "entitlement", "evidence", "requirements",
                  "compile", "capsule", "governance", "boundary", "validate")


def tcb_manifest(*, present: list) -> dict:
    """Enumerate the trusted computing base for the context guarantee. Missing a
    component makes the TCB incomplete (fail-closed, D-B6-310)."""
    have = set(present)
    missing = sorted(c for c in TCB_COMPONENTS if c not in have)
    return {"components": list(TCB_COMPONENTS), "present": sorted(have),
            "missing": missing, "complete": not missing,
            "tcb_root": hash_obj({"c": list(TCB_COMPONENTS),
                                  "p": sorted(have)})}


# --- capsule generation ------------------------------------------------------
_SECRET_MARKERS = ("provider_token", "secret", "api_key", "credential",
                   "authority_grant", "answer_key", "raw_secret", "password",
                   "private_key")
# high-signal substrings that indicate a secret appearing as a VALUE (the capsule
# body is structurally content-only — claim ids, hashes, states — so these markers
# do not collide with legitimate free text)
_SECRET_VALUE_MARKERS = ("sk-live", "sk-test", "sk-", "api_key", "apikey",
                         "api token", "secret", "password", "passwd",
                         "bearer ", "private_key", "-----begin",
                         "access_token", "authorization:")
# the capsule body is a CLOSED shape: any key outside this allowlist is refused,
# so nothing (an authority grant, an extra proof field) can be smuggled in after
# certification (red-team fix — allowlist fails CLOSED, D-B6-300..305)
ALLOWED_BODY_KEYS = frozenset({
    "capsule_kind", "informs_not_authorizes", "tenant_id", "principal_id",
    "purpose", "operation_class", "snapshot_root", "version_vector_hash",
    "entitlement_hash", "claims", "support_bases", "bom_root",
    "risk_envelope_hash", "tcb_root", "compiler_version"})


def _scan_secret_free(body: dict) -> list:
    """Return the offending paths if any secret marker appears as a KEY or as a
    string VALUE (the capsule body must be secret-free before sealing,
    INV-04..06). Value scanning closes the red-team gap where a secret hid under
    an innocuous key."""
    hits = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(m in str(k).lower() for m in _SECRET_MARKERS):
                    hits.append(path + "/" + str(k))
                walk(v, path + "/" + str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}/{i}")
        elif isinstance(obj, str):
            low = obj.lower()
            if any(m in low for m in _SECRET_VALUE_MARKERS):
                hits.append(path + "=<secret-value>")

    walk(body, "")
    return hits


def _disallowed_body_keys(body: dict) -> list:
    """Keys present in the body that are outside the closed allowlist."""
    return sorted(k for k in body if k not in ALLOWED_BODY_KEYS)


def build_capsule(*, snapshot: dict, version_vector: dict, entitlement: dict,
                  selected_claims: list, support_bases: dict,
                  bom: dict, risk: dict, tcb: dict,
                  compiler_version: str = "ctxgov-compiler-1.0") -> dict:
    """Assemble the capsule BODY (no certificate yet). The body is content it is
    safe to render; the certificate (below) binds it. INFORMS, never authorizes:
    the body carries no authority grant and no secret."""
    claim_view = [{"claim_id": c["claim_id"],
                   "support_state": c.get("support_state"),
                   "polarity": c.get("polarity"),
                   "evidence_refs": sorted(c.get("evidence_refs", [])),
                   "taint_refs": sorted(c.get("taint_refs", [])),
                   "discharges": sorted(c.get("discharges", []))}
                  for c in sorted(selected_claims,
                                  key=lambda x: x["claim_id"])]
    body = {
        "capsule_kind": "FINALIS_CONTEXT_CAPSULE",
        "informs_not_authorizes": True,
        "tenant_id": snapshot["tenant_id"],
        "principal_id": snapshot["principal_id"],
        "purpose": snapshot["purpose"],
        "operation_class": snapshot["operation_class"],
        "snapshot_root": snapshot["snapshot_root"],
        "version_vector_hash": version_vector["vector_hash"],
        "entitlement_hash": entitlement["entitlement_hash"],
        "claims": claim_view,
        "support_bases": {k: [sorted(b) for b in v]
                          for k, v in sorted(support_bases.items())},
        "bom_root": bom["bom_root"],
        "risk_envelope_hash": risk["envelope_hash"],
        "tcb_root": tcb["tcb_root"],
        "compiler_version": compiler_version,
    }
    return body


def _capsule_roots(body: dict) -> dict:
    """Deterministically derive the capsule's class roots from the body alone.

    The BODY root is a hash over the ENTIRE canonical body, so every field —
    including ``support_bases`` (the minimal-support proof), ``compiler_version``
    and any other key — is bound; the structural class roots (CLAIMS/SCOPE/BOM/
    RISK/TCB) remain for transparency. Changing any body field moves BODY and
    therefore the capsule root (red-team fix)."""
    claim_root = class_root([hash_obj(c) for c in body["claims"]]) \
        if body["claims"] else merkle_root([])
    scope_root = hash_obj({
        "tenant": body["tenant_id"], "principal": body["principal_id"],
        "purpose": body["purpose"], "operation": body["operation_class"],
        "snapshot": body["snapshot_root"],
        "vector": body["version_vector_hash"],
        "entitlement": body["entitlement_hash"]})
    return {"CLAIMS": claim_root, "SCOPE": scope_root,
            "BOM": body["bom_root"], "RISK": body["risk_envelope_hash"],
            "TCB": body["tcb_root"], "BODY": hash_obj(body)}


def certify_capsule(body: dict, *, generator_id: str) -> dict:
    """GENERATOR produces the certificate: the global root over the capsule's
    class roots, plus a secret-free assertion. The generator id is recorded so
    the checker can enforce role separation."""
    secret_hits = _scan_secret_free(body)
    disallowed = _disallowed_body_keys(body)
    roots = _capsule_roots(body)
    cert = {
        "capsule_root": global_root(roots),
        "class_roots": roots,
        "body_hash": roots["BODY"],
        "secret_free": not secret_hits,
        "secret_hits": secret_hits,
        "well_formed": not disallowed,
        "disallowed_keys": disallowed,
        "generator_id": generator_id,
        "checker_version": "ctxgov-capsule-cert-1.0",
    }
    cert["certificate_hash"] = hash_obj(cert)
    return {"body": body, "certificate": cert,
            "capsule_id": "CAP-" + cert["capsule_root"][:16]}


# --- INDEPENDENT certificate checker (role-separated) ------------------------
def check_capsule(capsule: dict, *, checker_id: str) -> dict:
    """A byte-INDEPENDENT checker. It re-derives every root from the capsule body
    ALONE and accepts only if the recomputed global root equals the certified
    root, the body is secret-free, informs-not-authorizes holds, and the checker
    is NOT the generator (a generator can never self-certify, D-B6-300..305)."""
    body = capsule["body"]
    cert = capsule["certificate"]
    recomputed_roots = _capsule_roots(body)
    recomputed_global = global_root(recomputed_roots)
    # BODY binds the ENTIRE body, so root_ok already covers every field
    root_ok = recomputed_global == cert["capsule_root"]
    class_ok = recomputed_roots == cert["class_roots"]
    body_hash_ok = recomputed_roots["BODY"] == cert.get("body_hash")
    secret_free = not _scan_secret_free(body)
    disallowed = _disallowed_body_keys(body)
    well_formed = not disallowed              # closed shape: no smuggled keys
    # authority is refused structurally: the body must carry the informs flag and
    # NO key hinting at authority/grant/approval (allowlist already blocks these,
    # this is defence in depth)
    authority_keys = [k for k in body
                      if any(t in str(k).lower()
                             for t in ("authority", "grant", "approval",
                                       "permission", "entitle_action"))]
    informs_only = (body.get("informs_not_authorizes") is True
                    and not authority_keys)
    independent = checker_id != cert.get("generator_id")
    accepted = bool(root_ok and class_ok and body_hash_ok and secret_free
                    and well_formed and informs_only and independent)
    return {"accepted": accepted, "root_ok": root_ok, "class_ok": class_ok,
            "body_hash_ok": body_hash_ok, "secret_free": secret_free,
            "well_formed": well_formed, "disallowed_keys": disallowed,
            "informs_only": informs_only, "independent": independent,
            "checker_id": checker_id, "recomputed_root": recomputed_global,
            "certified_root": cert["capsule_root"]}


def capsule_findings(check: dict) -> list[Finding]:
    out: list[Finding] = []
    if not check.get("independent"):
        out.append(Finding("GENERATOR_SELF_CERTIFICATION", P0, "capsule",
                           "checker id equals generator id: self-certification "
                           "forbidden", {}))
    if not (check.get("root_ok") and check.get("class_ok")
            and check.get("body_hash_ok", True)):
        out.append(Finding("CAPSULE_CERTIFICATE_INVALID", P0, "capsule",
                           "recomputed capsule root/body hash does not match "
                           "certificate",
                           {"recomputed": check.get("recomputed_root"),
                            "certified": check.get("certified_root")}))
    if not check.get("well_formed", True):
        out.append(Finding("CAPSULE_CERTIFICATE_INVALID", P0, "capsule",
                           "capsule body carries keys outside the closed "
                           f"allowlist: {check.get('disallowed_keys')}", {}))
    if not check.get("secret_free"):
        out.append(Finding("PROVIDER_TOKEN_IN_CAPSULE", P0, "capsule",
                           "capsule body is not secret-free", {}))
    if not check.get("informs_only"):
        out.append(Finding("AUTHORITY_INFERENCE_REJECTED", P0, "capsule",
                           "capsule asserts authority: capsules inform, never "
                           "authorize (INV-01)", {}))
    return out


# --- SCITT transparency projection -------------------------------------------
def transparency_receipt(capsule: dict, *, log_position: int) -> dict:
    """An append-only transparency projection (SCITT-style): a signed-shaped
    statement binding the capsule root at a log position. No signature material is
    emitted — only the content commitment (D-B6-260)."""
    stmt = {"capsule_root": capsule["certificate"]["capsule_root"],
            "capsule_id": capsule["capsule_id"], "log_position": log_position}
    stmt["receipt_hash"] = hash_obj(stmt)
    return stmt


# --- robustness frontier -----------------------------------------------------
def robustness_frontier(*, scenarios: list) -> dict:
    """Enumerate, per adversarial/degradation scenario, whether the capsule would
    still certify. The frontier is the set of scenarios under which the guarantee
    holds vs breaks (Innovation 17)."""
    holds, breaks = [], []
    for s in scenarios:
        (holds if s.get("certifies") else breaks).append(s.get("name"))
    return {"holds_under": sorted(holds), "breaks_under": sorted(breaks),
            "frontier_hash": hash_obj({"h": sorted(holds),
                                       "b": sorted(breaks)})}


# --- replay twin -------------------------------------------------------------
def replay_twin(original: dict, replayed_body: dict, *,
                generator_id: str) -> dict:
    """Recompute the capsule from the same snapshot; determinism requires the
    replayed root to equal the original (Innovation 18, D-B6-290..295)."""
    twin = certify_capsule(replayed_body, generator_id=generator_id)
    diverged = twin["certificate"]["capsule_root"] != \
        original["certificate"]["capsule_root"]
    return {"diverged": bool(diverged),
            "original_root": original["certificate"]["capsule_root"],
            "replay_root": twin["certificate"]["capsule_root"]}


def replay_findings(replay: dict) -> list[Finding]:
    if replay.get("diverged"):
        return [Finding("CAPSULE_REPLAY_DIVERGED", P0, "replay",
                        "replay produced a different capsule root: "
                        "nondeterministic build", {})]
    return []
