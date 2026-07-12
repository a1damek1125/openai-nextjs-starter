"""Transformers, Loss Vector, Round-Trip (SP0007 §11.8, §12.6/12.8,
D-0007-38/39/40/41, AC-0007-133..141, 166..168).

Every transformer declares a loss vector over the fixed dimensions
(D-0007-38); a missing dimension is UNKNOWN, and UNKNOWN is never NONE
(fail-closed). Critical losses — authority, evidence, provenance — are
NON-COMPENSATORY: no cost or downtime advantage can buy them back (D-0007-39,
INV-0007-33). Observed loss must stay within declared loss (§12.8); anything
beyond is MIGRATION_LOSS_UNDECLARED. A REVERSIBLE declaration is proven only
by an executed round-trip (D-0007-40); tenant identity can never change during
migration (INV-0007-50); a ONE_WAY edge requires an explicit irreversibility
declaration, a last safe rollback point, and a forward-fix plan (D-0007-41).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, LOSS_DIMENSIONS, LOSS_LEVELS,
                    CRITICAL_LOSS_DIMENSIONS, MIGRATION_LOSS_UNDECLARED,
                    ROUND_TRIP_FAILED, CROSS_TENANT_MIGRATION_DETECTED,
                    INVALID_COMPAT_SCHEMA)
from .canon import core_hash

# strict ordering of concrete levels; UNKNOWN handled fail-closed, apart
_LEVEL_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "TOTAL": 4}


def new_loss_vector() -> dict:
    """A fresh loss vector: every dimension explicitly NONE (D-0007-38)."""
    return {d: "NONE" for d in LOSS_DIMENSIONS}


def validate_loss_vector(lv: dict) -> list[Finding]:
    """Unknown dimensions/levels are flagged; a missing dimension is treated
    as UNKNOWN — and UNKNOWN is NOT NONE (fail-closed, D-0007-38)."""
    out: list[Finding] = []
    for d in lv:
        if d not in LOSS_DIMENSIONS:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, d,
                               f"unknown loss dimension {d!r}", {}))
    for d, lvl in lv.items():
        if d in LOSS_DIMENSIONS and lvl not in LOSS_LEVELS:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, d,
                               f"unknown loss level {lvl!r} on {d}", {}))
    for d in LOSS_DIMENSIONS:
        if d not in lv:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P2, d,
                               f"loss dimension {d} undeclared — treated as "
                               "UNKNOWN, not NONE (fail-closed)", {}))
    return out


def critical_loss_findings(lv: dict) -> list[Finding]:
    """Any critical dimension above NONE — or UNKNOWN — is a P0
    non-compensatory finding (D-0007-39, INV-0007-33). No averaging, no
    trade-off against cost or downtime."""
    out: list[Finding] = []
    for d in sorted(CRITICAL_LOSS_DIMENSIONS):
        lvl = lv.get(d, "UNKNOWN")
        if lvl == "NONE":
            continue
        if lvl == "UNKNOWN" or lvl not in _LEVEL_RANK:
            msg = (f"critical loss dimension {d} is UNKNOWN/undeclared — "
                   "fail-closed, treated as loss (D-0007-39)")
        else:
            msg = (f"critical loss dimension {d} at {lvl} is "
                   "non-compensatory — blocks the migration (D-0007-39, "
                   "INV-0007-33)")
        out.append(Finding(MIGRATION_LOSS_UNDECLARED, P0, d, msg,
                           {"dimension": d, "level": lvl,
                            "non_compensatory": True}))
    return out


def _exceeds(observed: str, declared: str) -> bool:
    if observed == "UNKNOWN":
        # UNKNOWN observed exceeds anything except UNKNOWN declared
        return declared != "UNKNOWN"
    if declared == "UNKNOWN" or declared not in _LEVEL_RANK:
        # an UNKNOWN/invalid declaration is no ceiling at all (fail-closed)
        return _LEVEL_RANK.get(observed, 5) > 0
    return _LEVEL_RANK.get(observed, 5) > _LEVEL_RANK[declared]


def observed_loss_findings(declared: dict, observed: dict) -> list[Finding]:
    """§12.8: ObservedLoss must be a subset of DeclaredLoss. Any dimension
    where observation exceeds declaration is MIGRATION_LOSS_UNDECLARED (P0)."""
    out: list[Finding] = []
    dims = list(LOSS_DIMENSIONS) + [d for d in sorted(observed)
                                    if d not in LOSS_DIMENSIONS]
    for d in dims:
        obs = observed.get(d, "NONE")
        dec = declared.get(d, "NONE")
        if _exceeds(obs, dec):
            out.append(Finding(MIGRATION_LOSS_UNDECLARED, P0, d,
                               f"observed loss {obs} on {d} exceeds declared "
                               f"{dec} (§12.8, AC-0007-137)",
                               {"dimension": d, "declared": dec,
                                "observed": obs}))
    return out


def round_trip(x: dict, up, down, *, equivalence=None) -> dict:
    """Execute down(up(x)) and compare (D-0007-40). Equivalence defaults to
    core_hash equality over the canonical, volatile-stripped form."""
    original_hash = core_hash(x)
    try:
        y = down(up(x))
    except Exception as exc:  # a crashing transformer never round-trips
        return {"passed": False, "original_hash": original_hash,
                "roundtrip_hash": None, "error": repr(exc)}
    roundtrip_hash = core_hash(y)
    if equivalence is not None:
        passed = bool(equivalence(x, y))
    else:
        passed = original_hash == roundtrip_hash
    return {"passed": passed, "original_hash": original_hash,
            "roundtrip_hash": roundtrip_hash}


def round_trip_findings(edge: dict, result: dict) -> list[Finding]:
    """A declared-REVERSIBLE edge whose round-trip fails is ROUND_TRIP_FAILED
    (P0) — the reversibility claim is refuted by execution (D-0007-40)."""
    if edge.get("reversibility") == "REVERSIBLE" and not result.get("passed"):
        eid = edge.get("migration_edge_id", "-")
        return [Finding(ROUND_TRIP_FAILED, P0, eid,
                        "round-trip failed for a declared-REVERSIBLE edge "
                        "(D-0007-40, AC-0007-133)",
                        {"original_hash": result.get("original_hash"),
                         "roundtrip_hash": result.get("roundtrip_hash")})]
    return []


def _record_id(r: dict):
    return r.get("id", r.get("record_id"))


def tenant_findings(records_before: list[dict],
                    records_after: list[dict]) -> list[Finding]:
    """Tenant identity can never change during migration (INV-0007-50). A
    record whose tenant_id changed, or an after-record in a tenant unseen
    before, is CROSS_TENANT_MIGRATION_DETECTED (P0)."""
    out: list[Finding] = []
    before_by_id = {_record_id(r): r for r in records_before
                    if _record_id(r) is not None}
    tenants_before = {r.get("tenant_id") for r in records_before}
    for r in records_after:
        rid = _record_id(r)
        tenant = r.get("tenant_id")
        prior = before_by_id.get(rid)
        if prior is not None and prior.get("tenant_id") != tenant:
            out.append(Finding(CROSS_TENANT_MIGRATION_DETECTED, P0,
                               str(rid),
                               f"record {rid!r} changed tenant "
                               f"{prior.get('tenant_id')!r} -> {tenant!r} "
                               "during migration (INV-0007-50)",
                               {"before": prior.get("tenant_id"),
                                "after": tenant}))
        elif prior is None and tenant not in tenants_before:
            out.append(Finding(CROSS_TENANT_MIGRATION_DETECTED, P0,
                               str(rid),
                               f"record {rid!r} appeared in tenant {tenant!r} "
                               "not present before migration (INV-0007-50)",
                               {"after": tenant}))
    return out


def one_way_declaration_findings(edge: dict) -> list[Finding]:
    """A ONE_WAY edge requires an EXPLICIT irreversibility declaration
    (boolean True, fail-closed), a last safe rollback point, and a forward-fix
    plan reference (D-0007-41)."""
    if edge.get("reversibility") != "ONE_WAY":
        return []
    out: list[Finding] = []
    eid = edge.get("migration_edge_id", "-")
    if edge.get("irreversible_declared") is not True:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P0, eid,
                           "ONE_WAY edge without explicit "
                           "irreversible_declared=True — irreversibility must "
                           "be declared, never implied (D-0007-41)", {}))
    if not edge.get("last_safe_rollback_point"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "ONE_WAY edge missing last_safe_rollback_point "
                           "(D-0007-41/51)", {}))
    if not edge.get("forward_fix_plan_ref"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "ONE_WAY edge missing forward_fix_plan_ref "
                           "(D-0007-41/52)", {}))
    return out
