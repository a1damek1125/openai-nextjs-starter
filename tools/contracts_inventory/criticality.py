"""Contract criticality as a VECTOR, not a scalar (SP0008 §12.6, D-0008-24/25).

Criticality is eight independent dimensions. Hard dimensions (authority, tenant,
externality, irreversibility, proof, historical_obligation) are CONJUNCTIVE and
non-compensatory: a single hard flag makes the surface CRITICAL regardless of the
others, and dimensions are NEVER averaged into a score (INV-0008-25). A dimension
that cannot be established is UNKNOWN, and UNKNOWN on a hard dimension is itself a
finding — it is never silently read as "safe" (fail-closed, D-0008-24).
"""
from __future__ import annotations

from .model import (CRITICALITY_DIMS, HARD_CRITICALITY_DIMS, Finding, P1, P2,
                    CRITICALITY_UNKNOWN, HARD_FLAG_UNVERIFIED)

# Deterministic, source-grounded heuristics per surface kind. Each returns a
# vector value in {"YES","NO","UNKNOWN"}. UNKNOWN is a first-class result.
YES, NO, UNK = "YES", "NO", "UNKNOWN"


def _http_vector(surface, shape) -> dict:
    method = (shape.get("method") or "").upper()
    path = shape.get("path") or ""
    writes = method in ("POST", "PUT", "PATCH", "DELETE")
    # authority: touches auth/rbac/roles/permissions/approval
    authority = YES if any(t in path for t in
                           ("/auth", "role", "permission", "approval",
                            "rbac")) else UNK
    tenant = YES if "tenant" in path else UNK
    return {
        "authority": authority,
        "tenant": tenant,
        "data": YES if writes else UNK,
        "externality": UNK,               # provider reachability resolved in chains
        "irreversibility": YES if method == "DELETE" else UNK,
        "centrality": UNK,                # graph-derived downstream
        "proof": NO,
        "historical_obligation": UNK,
    }


def _event_vector(surface, shape) -> dict:
    return {d: (YES if d in ("data", "historical_obligation", "proof") else UNK)
            for d in CRITICALITY_DIMS}


def _db_vector(surface, shape) -> dict:
    v = {d: UNK for d in CRITICALITY_DIMS}
    v["data"] = YES
    v["historical_obligation"] = YES
    if surface.surface_kind == "DB_MIGRATION":
        v["irreversibility"] = YES        # forward-only migrations (no down)
    if "tenant" in surface.canonical_name:
        v["tenant"] = YES
    return v


def _proof_vector(surface, shape) -> dict:
    v = {d: UNK for d in CRITICALITY_DIMS}
    v["proof"] = YES
    v["historical_obligation"] = YES
    return v


def _state_vector(surface, shape) -> dict:
    v = {d: UNK for d in CRITICALITY_DIMS}
    v["historical_obligation"] = YES
    return v


def _default_vector(surface, shape) -> dict:
    return {d: UNK for d in CRITICALITY_DIMS}


_KIND_VECTOR = {
    "HTTP_ROUTE": _http_vector,
    "AUDIT_EVENT": _event_vector,
    "RUN_LEDGER_EVENT": _event_vector,
    "DB_TABLE": _db_vector,
    "DB_MIGRATION": _db_vector,
    "PROOF_ARTIFACT": _proof_vector,
    "STATE_MACHINE": _state_vector,
    "STATE_TRANSITION": _state_vector,
}


def criticality_vector(surface, *, shape: dict | None = None) -> dict:
    """The eight-dimension criticality vector for a surface. `shape` supplies the
    detector shape (method/path/…) when the caller has it."""
    shape = shape or {}
    fn = _KIND_VECTOR.get(surface.surface_kind, _default_vector)
    vec = fn(surface, shape)
    # never average; expose the raw vector (conjunctive verdict computed apart)
    return {d: vec.get(d, UNK) for d in CRITICALITY_DIMS}


def verdict(vec: dict) -> str:
    """Conjunctive verdict: any hard flag YES => CRITICAL; any hard flag UNKNOWN
    => ELEVATED (must be resolved, never assumed safe); else STANDARD."""
    if any(vec.get(d) == YES for d in HARD_CRITICALITY_DIMS):
        return "CRITICAL"
    if any(vec.get(d) == UNK for d in HARD_CRITICALITY_DIMS):
        return "ELEVATED"
    return "STANDARD"


def criticality_findings(surface, vec: dict) -> list[Finding]:
    """Emit findings for unresolved hard dimensions (fail-closed, D-0008-24)."""
    out: list[Finding] = []
    unresolved = [d for d in HARD_CRITICALITY_DIMS if vec.get(d) == UNK]
    if unresolved:
        # advisory (P2), NOT an inventory-integrity failure: an UNKNOWN hard
        # flag is a legitimate, expected result that feeds the probe plan — it
        # is never read as "safe", but it also does not invalidate the
        # inventory (the mission treats UNKNOWN as a first-class result).
        out.append(Finding(
            HARD_FLAG_UNVERIFIED, P2, surface.surface_id,
            f"hard criticality dimension(s) {sorted(unresolved)} unresolved "
            "for this surface; UNKNOWN on a hard flag is never read as safe",
            {"unresolved": sorted(unresolved), "verdict": verdict(vec)}))
    if all(vec.get(d) == UNK for d in CRITICALITY_DIMS):
        out.append(Finding(
            CRITICALITY_UNKNOWN, P2, surface.surface_id,
            "criticality vector is entirely UNKNOWN for this surface",
            {"surface_kind": surface.surface_kind}))
    return out
