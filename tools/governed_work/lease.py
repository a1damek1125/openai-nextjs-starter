"""Capability Lease Registry + Attenuation Proof + Revocation (SP0006 §9.5,
D-0006-15..20, INV-0006-07/08/09/16).

A capability lease is contextual, expiring and revocable (D-0006-18); there is no
ambient permanent agent capability. A child lease must be structurally ATTENUATED
relative to its parent (D-0006-16): every operation/target/data/effect set is a
subset, every ceiling is <=, expiry <=, use-count <=. Any non-empty expansion is a
LEASE_ATTENUATION_FAILURE / DELEGATION_AUTHORITY_AMPLIFICATION (P0). Revoking a
parent invalidates all descendants unless an independent root exists (D-0006-19).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, LEASE_ATTENUATION_FAILURE,
                    DELEGATION_AUTHORITY_AMPLIFICATION, LEASE_EXPIRED,
                    LEASE_REVOKED, REVOCATION_PROPAGATION_STALE,
                    INVALID_WORK_SCHEMA, LEASE_SUBSET_DIMS, LEASE_CEILING_DIMS)
from .canon import core_hash

RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4,
              "UNKNOWN": 5}


def _as_set(v) -> set:
    if isinstance(v, (list, set, tuple)):
        return {str(x) for x in v}
    if v is None:
        return set()
    return {str(v)}


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _ceiling_le(child, parent) -> bool:
    """child <= parent for a ceiling dict/number. UNKNOWN child never <= a known
    parent (fail-closed). Missing parent value = no ceiling granted -> child must
    also be empty."""
    if isinstance(parent, dict) or isinstance(child, dict):
        pc = child if isinstance(child, dict) else {}
        pp = parent if isinstance(parent, dict) else {}
        for k in set(pc) | set(pp):
            cv, pv = pc.get(k), pp.get(k)
            if isinstance(cv, str) or isinstance(pv, str):
                if RISK_ORDER.get(str(cv), 5) > RISK_ORDER.get(str(pv), -1):
                    return False
            else:
                cn, pn = _num(cv), _num(pv)
                # a parent that bounds this key but a child that omits it means
                # the child is UNBOUNDED on that key -> not attenuated
                # (SWARM-M E4; fail-closed, INV-0006-08)
                if pn is not None and cn is None:
                    return False
                if cn is None:
                    continue
                if pn is None or cn > pn:
                    return False
        return True
    # scalar
    if isinstance(child, str) or isinstance(parent, str):
        return RISK_ORDER.get(str(child), 5) <= RISK_ORDER.get(str(parent), -1)
    cn, pn = _num(child), _num(parent)
    # child omits a numeric ceiling the parent bounds -> unbounded -> fail
    if cn is None:
        return pn is None
    return pn is not None and cn <= pn


def attenuation_delta(parent: dict, child: dict) -> dict:
    """The rights removed / narrowed going parent -> child (D-0006-17)."""
    delta = {"removed_operations": [], "narrowed_targets": [],
             "narrowed_data": [], "narrowed_effects": [],
             "narrowed_ceilings": [], "narrowed_expiry": None,
             "narrowed_uses": None}
    for dim, key in (("removed_operations", "allowed_operations"),
                     ("narrowed_targets", "targets"),
                     ("narrowed_data", "data_classes"),
                     ("narrowed_effects", "effect_classes")):
        removed = _as_set(parent.get(key)) - _as_set(child.get(key))
        delta[dim] = sorted(removed)
    if parent.get("expires_at") and child.get("expires_at") \
            and child["expires_at"] < parent["expires_at"]:
        delta["narrowed_expiry"] = child["expires_at"]
    pu, cu = parent.get("maximum_uses"), child.get("maximum_uses")
    if isinstance(pu, int) and isinstance(cu, int) and cu < pu:
        delta["narrowed_uses"] = cu
    return delta


def is_attenuation(parent: dict, child: dict) -> tuple[bool, list[str]]:
    """(child <= parent, reasons-for-failure). Subset on set dims, <= on ceilings,
    expiry and use-count."""
    reasons: list[str] = []
    for dim in LEASE_SUBSET_DIMS:
        expanded = _as_set(child.get(dim)) - _as_set(parent.get(dim))
        if expanded:
            reasons.append(f"{dim} expanded: {sorted(expanded)}")
    for dim in LEASE_CEILING_DIMS:
        if not _ceiling_le(child.get(dim), parent.get(dim)):
            reasons.append(f"{dim} exceeds parent")
    # expiry: child must not outlive parent
    pe, ce = parent.get("expires_at"), child.get("expires_at")
    if pe and ce and ce > pe:
        reasons.append("expiry extended beyond parent")
    if pe and not ce:
        reasons.append("child has no expiry but parent does")
    # use count: a parent that bounds uses but a child that omits (or non-ints)
    # its use count means the child is UNBOUNDED -> not attenuated (SWARM-M E4)
    pu = parent.get("maximum_uses")
    cu = child.get("maximum_uses")
    if isinstance(pu, int):
        if not isinstance(cu, int):
            reasons.append("child omits a bounded use count (unbounded)")
        elif cu > pu:
            reasons.append("use count exceeds parent")
    return (not reasons, reasons)


def attenuate(parent: dict, narrow: dict) -> dict:
    """Derive a child lease from a parent by narrowing, then store the proof.
    `narrow` supplies the child-specific subject/purpose/narrowed sets."""
    child = dict(parent)
    child.update(narrow)
    child["parent_lease_id"] = parent.get("lease_id")
    child["current_uses"] = 0
    child["revocation_state"] = "ACTIVE"
    delta = attenuation_delta(parent, child)
    child["attenuation_delta"] = delta
    child["integrity_hash"] = core_hash({k: child.get(k) for k in
                                        ("lease_id", "parent_lease_id",
                                         "subject_identity", "targets",
                                         "allowed_operations", "effect_classes",
                                         "data_classes", "risk_ceiling",
                                         "cost_ceiling", "expires_at",
                                         "maximum_uses", "attenuation_delta")})
    return child


def attenuation_proof(parent: dict, child: dict) -> dict:
    ok, reasons = is_attenuation(parent, child)
    return {"parent_lease_id": parent.get("lease_id"),
            "child_lease_id": child.get("lease_id"),
            "is_attenuated": ok, "reasons": reasons,
            "delta": attenuation_delta(parent, child),
            "proof_hash": core_hash({"p": parent.get("integrity_hash"),
                                     "c": child.get("integrity_hash"),
                                     "ok": ok})}


def validate_child_lease(parent: dict, child: dict) -> list[Finding]:
    out: list[Finding] = []
    ok, reasons = is_attenuation(parent, child)
    if not ok:
        out.append(Finding(LEASE_ATTENUATION_FAILURE, P0,
                           child.get("lease_id", "-"),
                           "child lease is not an attenuation of parent: "
                           + "; ".join(reasons), {"reasons": reasons}))
        out.append(Finding(DELEGATION_AUTHORITY_AMPLIFICATION, P0,
                           child.get("lease_id", "-"),
                           "child authority exceeds parent (INV-0006-08)", {}))
    return out


def validate_lease(lease: dict, *, now: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    lid = lease.get("lease_id", "-")
    for f in ("lease_id", "tenant_id", "work_order_id", "subject_identity",
              "purpose"):
        if not lease.get(f):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, lid,
                               f"lease missing {f} (D-0006-18)", {}))
    if lease.get("revocation_state") == "REVOKED":
        out.append(Finding(LEASE_REVOKED, P0, lid, "lease is revoked", {}))
    if now and lease.get("expires_at") and now > lease["expires_at"]:
        out.append(Finding(LEASE_EXPIRED, P0, lid,
                           f"lease expired at {lease['expires_at']}", {}))
    mu, cu = lease.get("maximum_uses"), lease.get("current_uses", 0)
    if isinstance(mu, int) and isinstance(cu, int) and cu > mu:
        out.append(Finding(LEASE_ATTENUATION_FAILURE, P0, lid,
                           "lease used beyond maximum_uses", {}))
    return out


def revoke_descendants(leases: list[dict], revoked_id: str) -> dict:
    """Propagate revocation to all descendants unless a lease has an independent
    root authority (D-0006-19). Returns invalidated ids + any staleness finding
    surface."""
    by_id = {l.get("lease_id"): l for l in leases}
    children: dict[str, list[str]] = {}
    for l in leases:
        p = l.get("parent_lease_id")
        if p:
            children.setdefault(p, []).append(l.get("lease_id"))
    invalidated: list[str] = []
    stack = list(children.get(revoked_id, []))
    while stack:
        cid = stack.pop()
        lease = by_id.get(cid, {})
        if lease.get("independent_root_authority"):
            continue   # survives via its own root (D-0006-19)
        invalidated.append(cid)
        stack.extend(children.get(cid, []))
    return {"revoked": revoked_id, "invalidated": sorted(set(invalidated))}


def revocation_staleness(revocation: dict) -> list[Finding]:
    """Bounded staleness model (D-0006-20): observed - issued must be within the
    maximum propagation delay, else REVOCATION_PROPAGATION_STALE."""
    issued = revocation.get("issued_seq")
    observed = revocation.get("observed_seq")
    max_delay = revocation.get("max_propagation_delay")
    if isinstance(issued, int) and isinstance(observed, int) \
            and isinstance(max_delay, int) and (observed - issued) > max_delay:
        return [Finding(REVOCATION_PROPAGATION_STALE, P1,
                        revocation.get("revocation_id", "-"),
                        f"revocation propagation delay {observed - issued} "
                        f"exceeds max {max_delay}", {})]
    return []
