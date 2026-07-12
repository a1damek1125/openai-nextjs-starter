"""Context Entitlement Graph + Point-in-Time Snapshot + Snapshot Lease + TOCTOU
Firewall + Delta Certificate + Cache Coherency (TOOL-B10 §D/G/H/I/J/K/L,
Innovations 1/2/14, §11.1/11.2/11.11, §12.1/12.2/12.17, D-B6-010..021, 061..080).

Entitlement precedes retrieval: every protected access binds tenant + principal +
provider account + purpose + operation class + data classes + jurisdiction +
policy epoch + expiry. A Context Snapshot binds an exact VERSION VECTOR of every
material input and issues a LEASE. Before consumption the TOCTOU firewall
recomputes the current vector, classifies each delta (material/nonmaterial/
unknown), and returns VALID / VALID_WITH_NONMATERIAL_DELTA / RECOMPILE_REQUIRED /
REQUALIFICATION_REQUIRED / BLOCKED / UNKNOWN — an UNKNOWN critical delta blocks
(fail-closed). A cached capsule is reused only on an EXACT scope + version-vector
match (cross-tenant/account/purpose reuse is impossible).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, TOCTOU_VERDICTS, DELTA_CLASSES)

# version-vector components whose change is MATERIAL (critical) by default
CRITICAL_COMPONENTS = frozenset({
    "source_versions", "evidence_versions", "approval_versions",
    "entitlement_version", "policy_epoch", "semantic_epoch"})
# components whose change is nonmaterial when explicitly allowed by the lease
NONMATERIAL_CANDIDATES = frozenset({"memory_versions", "adapter_versions"})


def entitlement(*, tenant_id: str, principal_id: str, provider_account_ids: list,
                purpose: str, operation_class: str, data_classes: list,
                jurisdiction: str, policy_epoch: str, expires_at) -> dict:
    e = {"tenant_id": tenant_id, "principal_id": principal_id,
         "provider_account_ids": sorted(provider_account_ids),
         "purpose": purpose, "operation_class": operation_class,
         "data_classes": sorted(data_classes), "jurisdiction": jurisdiction,
         "policy_epoch": policy_epoch, "expires_at": expires_at}
    e["entitlement_hash"] = hash_obj(e)
    return e


def check_entitlement(ent: dict, *, tenant_id: str, principal_id: str,
                      provider_account_id: str, purpose: str,
                      operation_class: str, now: str) -> list[Finding]:
    """Fail-closed: any mismatch or expiry blocks (D-B6-035..039)."""
    out: list[Finding] = []
    if ent is None:
        return [Finding("ENTITLEMENT_MISSING", P0, "-",
                        "no entitlement for this access (entitlement before "
                        "retrieval)", {})]
    if ent["tenant_id"] != tenant_id:
        out.append(Finding("SOURCE_TENANT_MISMATCH", P0, tenant_id,
                           "cross-tenant context access blocked", {}))
    if ent["principal_id"] != principal_id:
        out.append(Finding("ENTITLEMENT_MISSING", P0, principal_id,
                           "principal not entitled", {}))
    if provider_account_id not in ent["provider_account_ids"]:
        out.append(Finding("SOURCE_ACCOUNT_MISMATCH", P0, provider_account_id,
                           "cross-account context access blocked", {}))
    if ent["purpose"] != purpose:
        out.append(Finding("SOURCE_PURPOSE_MISMATCH", P0, purpose,
                           "cross-purpose context access blocked", {}))
    if ent["operation_class"] != operation_class:
        out.append(Finding("ENTITLEMENT_MISSING", P0, operation_class,
                           "operation class not entitled", {}))
    if ent.get("expires_at") is not None and str(ent["expires_at"]) <= str(now):
        out.append(Finding("ENTITLEMENT_EXPIRED", P0, ent["entitlement_hash"],
                           "entitlement expired", {}))
    return out


def version_vector(*, tenant_id: str, source_versions: dict,
                   evidence_versions: dict, memory_versions: dict,
                   approval_versions: dict, entitlement_version: str,
                   policy_epoch: str, semantic_epoch: str,
                   adapter_versions: dict, compiler_version: str) -> dict:
    v = {"tenant_id": tenant_id, "source_versions": source_versions,
         "evidence_versions": evidence_versions, "memory_versions": memory_versions,
         "approval_versions": approval_versions,
         "entitlement_version": entitlement_version, "policy_epoch": policy_epoch,
         "semantic_epoch": semantic_epoch, "adapter_versions": adapter_versions,
         "compiler_version": compiler_version}
    v["vector_hash"] = hash_obj(v)
    return v


def snapshot(*, tenant_id: str, principal_id: str, provider_account_ids: list,
             work_id: str, purpose: str, operation_class: str,
             version_vector_ref: str, evidence_refs: list, claim_refs: list,
             created_at: str) -> dict:
    s = {"tenant_id": tenant_id, "principal_id": principal_id,
         "provider_account_ids": sorted(provider_account_ids), "work_id": work_id,
         "purpose": purpose, "operation_class": operation_class,
         "version_vector_ref": version_vector_ref,
         "evidence_refs": sorted(evidence_refs), "claim_refs": sorted(claim_refs),
         "created_at": created_at}
    s["snapshot_root"] = hash_obj({k: s[k] for k in s if k != "created_at"})
    s["snapshot_id"] = "SNAP-" + s["snapshot_root"][:16]
    return s


def issue_lease(*, snapshot_root: str, issued_at: str, expires_at: str,
                allowed_delta_classes: list, required_revalidations: list,
                consumption_limit=None) -> dict:
    lease = {"snapshot_root": snapshot_root, "issued_at": issued_at,
             "expires_at": expires_at,
             "allowed_delta_classes": sorted(allowed_delta_classes),
             "required_revalidations": sorted(required_revalidations),
             "consumption_limit": consumption_limit, "consumption_count": 0,
             "state": "ACTIVE"}
    lease["lease_hash"] = hash_obj({k: lease[k] for k in lease
                                    if k != "consumption_count"})
    lease["lease_id"] = "LEASE-" + lease["lease_hash"][:16]
    return lease


def _classify_delta(component: str, allowed: set) -> str:
    if component in CRITICAL_COMPONENTS:
        return "MATERIAL_RECOMPILE"
    if component in NONMATERIAL_CANDIDATES:
        return "NONMATERIAL_ALLOWED" if component in allowed else "MATERIAL_REQUALIFY"
    return "UNKNOWN"                     # unknown component => fail-closed


def revalidate(lease: dict, *, snapshot_vector: dict, current_vector: dict,
               now: str) -> dict:
    """TOCTOU revalidation (Innovation 2). Returns a Delta Certificate + verdict.
    An expired lease, a material delta, or an UNKNOWN critical delta blocks."""
    changed = []
    for comp in sorted(set(snapshot_vector) | set(current_vector)):
        if comp in ("vector_hash",):
            continue
        if snapshot_vector.get(comp) != current_vector.get(comp):
            changed.append(comp)
    allowed = set(lease.get("allowed_delta_classes", []))
    classes = {c: _classify_delta(c, allowed) for c in changed}
    verdict = "VALID"
    if lease.get("expires_at") is not None and str(lease["expires_at"]) <= str(now):
        verdict = "BLOCKED"
    elif any(v == "UNKNOWN" for v in classes.values()):
        verdict = "BLOCKED"             # unknown critical delta fails closed
    elif any(v == "MATERIAL_RECOMPILE" for v in classes.values()):
        verdict = "RECOMPILE_REQUIRED"
    elif any(v == "MATERIAL_REQUALIFY" for v in classes.values()):
        verdict = "REQUALIFICATION_REQUIRED"
    elif changed:
        verdict = "VALID_WITH_NONMATERIAL_DELTA"
    assert verdict in TOCTOU_VERDICTS
    cert = {
        "prior_snapshot_root": lease["snapshot_root"],
        "current_version_vector": current_vector.get("vector_hash"),
        "changed_components": sorted(changed),
        "material_changes": sorted(c for c, v in classes.items()
                                   if v.startswith("MATERIAL")),
        "nonmaterial_changes": sorted(c for c, v in classes.items()
                                      if v == "NONMATERIAL_ALLOWED"),
        "classification": verdict,
        "recompile_required": verdict == "RECOMPILE_REQUIRED",
        "requalification_required": verdict == "REQUALIFICATION_REQUIRED",
        "checker_version": "ctxgov-toctou-1.0",
    }
    cert["certificate_hash"] = hash_obj(cert)
    return {"verdict": verdict, "delta_certificate": cert}


def cache_key(*, tenant_id: str, principal_id: str, provider_account_id: str,
              purpose: str, operation_class: str, vector_hash: str,
              policy_epoch: str, semantic_epoch: str) -> str:
    """Cache reuse requires an EXACT scope + version match (D-B6-020/021,
    §12.17). Cross-tenant/account/purpose reuse is structurally impossible."""
    return hash_obj({"t": tenant_id, "pr": principal_id,
                     "acc": provider_account_id, "purpose": purpose,
                     "op": operation_class, "vec": vector_hash,
                     "pol": policy_epoch, "sem": semantic_epoch})


def cache_reusable(cached_key: str, *, request_key: str, lease: dict,
                   now: str) -> bool:
    if cached_key != request_key:
        return False
    if lease.get("state") != "ACTIVE":
        return False
    if lease.get("expires_at") is not None and str(lease["expires_at"]) <= str(now):
        return False
    return True


def toctou_findings(revalidation: dict) -> list[Finding]:
    out: list[Finding] = []
    v = revalidation["verdict"]
    if v == "BLOCKED":
        out.append(Finding("TOCTOU_REVALIDATION_FAILED", P0, "lease",
                           "snapshot lease invalid at consumption: expired or "
                           "unknown critical delta (fail-closed)",
                           revalidation["delta_certificate"]))
    return out
