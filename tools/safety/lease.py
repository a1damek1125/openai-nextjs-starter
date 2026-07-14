"""Context-Bound Safety Admission Lease + TOCTOU revalidation (SP0005 D-0005-13
..17, §11.2/§11.5/§12.4, INV-0005-04..08).

A safety approval is NOT an eternal Boolean. A lease binds an action fingerprint,
tenant, actor, target, authority snapshot, safety context and trajectory state,
with an expiry. Immediately before a future effect, the material context is
recomputed and compared to the lease; ANY material mismatch or expiry means the
lease cannot authorize the effect (SAFETY_TOCTOU_MISMATCH). A lease for one
action/target/tenant/context can never be replayed for another (INV-0005-04..08,
§17.1/17.2/17.3). A lease is EVIDENCE, not authority by itself (D-0005-84).
"""
from __future__ import annotations

from .canon import action_fingerprint, target_fingerprint, core_hash
from .model import (Finding, P0, MATERIAL_CONTEXT_FIELDS,
                    SAFETY_ADMISSION_LEASE_INVALID,
                    SAFETY_ADMISSION_LEASE_EXPIRED, SAFETY_TOCTOU_MISMATCH,
                    MATERIAL_CONTEXT_CHANGED)


def authority_hash(authority: dict) -> str:
    return core_hash(authority or {})


def safety_context_hash(context: dict) -> str:
    return core_hash({k: (context or {}).get(k) for k in MATERIAL_CONTEXT_FIELDS})


def issue_lease(*, action: dict, tenant: str, actor: str, authority: dict,
                context: dict, trajectory_state: dict, policy_version: str,
                semantic_epoch: str, issued_at: str, expires_at: str,
                revalidation_triggers=None, lease_id: str = "lease") -> dict:
    return {
        "lease_id": lease_id,
        "action_fingerprint": action_fingerprint(action),
        "target_fingerprint": target_fingerprint(action),
        "tenant_id": tenant, "actor_id": actor,
        "authority_snapshot_hash": authority_hash(authority),
        "safety_context_hash": safety_context_hash(context),
        "trajectory_state_hash": core_hash(trajectory_state or {}),
        "policy_version": policy_version, "semantic_epoch": semantic_epoch,
        "issued_at": issued_at, "expires_at": expires_at,
        "revalidation_triggers": sorted(revalidation_triggers or []),
        "status": "ACTIVE",
    }


def material_context_change(context_0: dict, context_1: dict) -> list[str]:
    """Fields in MATERIAL_CONTEXT_FIELDS that changed between two contexts."""
    return sorted(m for m in MATERIAL_CONTEXT_FIELDS
                  if (context_0 or {}).get(m) != (context_1 or {}).get(m))


def revalidate(lease: dict, *, action: dict, tenant: str, actor: str,
               authority: dict, context: dict, trajectory_state: dict,
               now: str) -> tuple[bool, list[Finding]]:
    """Immediate pre-effect revalidation (§11.2). Returns (may_execute, findings).
    Any material mismatch, expiry, or wrong binding => no effect."""
    out: list[Finding] = []
    lid = lease.get("lease_id", "-")
    if lease.get("status") not in ("ACTIVE",):
        out.append(Finding(SAFETY_ADMISSION_LEASE_INVALID, P0, lid,
                           f"lease status {lease.get('status')!r} is not ACTIVE",
                           {}))
    # expiry (string ISO compare; `now` supplied for determinism)
    if lease.get("expires_at") is not None and str(now) >= str(lease["expires_at"]):
        out.append(Finding(SAFETY_ADMISSION_LEASE_EXPIRED, P0, lid,
                           f"lease expired at {lease['expires_at']} (now {now})",
                           {}))
    # binding: replay prevention (INV-0005-04..08, §17.1/17.2/17.3)
    if lease.get("action_fingerprint") != action_fingerprint(action):
        out.append(Finding(SAFETY_TOCTOU_MISMATCH, P0, lid,
                           "action fingerprint changed — lease cannot authorize a "
                           "different action (INV-0005-04/06)", {}))
    if lease.get("target_fingerprint") != target_fingerprint(action):
        out.append(Finding(SAFETY_TOCTOU_MISMATCH, P0, lid,
                           "target changed — revalidation required (INV-0005-07)",
                           {}))
    if lease.get("tenant_id") != tenant:
        out.append(Finding(SAFETY_ADMISSION_LEASE_INVALID, P0, lid,
                           "tenant mismatch — lease is non-transferable "
                           "(INV-0005-04)", {}))
    if lease.get("actor_id") != actor:
        out.append(Finding(SAFETY_ADMISSION_LEASE_INVALID, P0, lid,
                           "actor mismatch — lease is non-transferable", {}))
    if lease.get("authority_snapshot_hash") != authority_hash(authority):
        out.append(Finding(SAFETY_TOCTOU_MISMATCH, P0, lid,
                           "authority changed since admission (INV-0005-08)", {}))
    if lease.get("safety_context_hash") != safety_context_hash(context):
        out.append(Finding(SAFETY_TOCTOU_MISMATCH, P0, lid,
                           "material safety context changed since admission "
                           "(INV-0005-04)", {}))
    if lease.get("trajectory_state_hash") != core_hash(trajectory_state or {}):
        out.append(Finding(SAFETY_TOCTOU_MISMATCH, P0, lid,
                           "trajectory state changed since admission", {}))
    return (len(out) == 0), out
