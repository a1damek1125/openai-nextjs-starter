"""Deprecation Registry, Notices, Support Windows, and the Sunset Gate
(SP0007 §10.11, §11.11, §12.9, D-0007-57..61, AC-0007-171..182).

Deprecation is a governed lifecycle, never a removal (D-0007-58, INV-0007-42):
a notice names the surface, its replacement, its reason, and its support
window (AC-0007-173). Retirement while an active consumer remains is
DEPRECATION_WITH_ACTIVE_CONSUMER (P0). The sunset gate (§12.9) is the AND of
all-known-consumers-migrated, no unknown critical consumers, the support
window satisfied, historical readers preserved, and rollback-or-forward-fix
readiness — fail-closed on every missing input (D-0007-59/60). A support
window extended by waiver must carry a waiver expiry (D-0007-61,
AC-0007-182).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, DEPRECATION_STATES,
                    SUPPORT_WINDOW_STATES, DEPRECATION_WITH_ACTIVE_CONSUMER,
                    SUNSET_NOT_READY, UNKNOWN_CONSUMER,
                    INVALID_COMPAT_SCHEMA)

_NOTICE_REQUIRED = ("deprecation_id", "contract_id", "version", "surface",
                    "reason")


def validate_notice(n: dict) -> list[Finding]:
    """A deprecation notice declares what is deprecated, why, what replaces
    it, since when, and how long it stays supported (D-0007-57,
    AC-0007-171..174)."""
    out: list[Finding] = []
    did = str(n.get("deprecation_id") or "-")
    for fld in _NOTICE_REQUIRED:
        if n.get(fld) in (None, "", []):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, did,
                               f"deprecation notice missing {fld}",
                               {"missing": fld}))
    if n.get("replacement_required", True) and not n.get("replacement"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, did,
                           "deprecated surface has no declared replacement "
                           "(AC-0007-173)", {}))
    if not (n.get("announced_in") or n.get("version")):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, did,
                           "deprecation notice does not name the version it "
                           "was first announced in", {}))
    if not (n.get("support_until") or n.get("support_window_ref")):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, did,
                           "deprecation notice has no support window "
                           "(support_until or support_window_ref) "
                           "(D-0007-60)", {}))
    status = n.get("status", "PROPOSED")
    if status not in DEPRECATION_STATES:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, did,
                           f"unknown deprecation status {status!r}", {}))
    return out


def _active_unmigrated(notice: dict, bindings: list[dict]) -> list[dict]:
    cid = notice.get("contract_id")
    # a consumer counts as migrated ONLY with an explicit boolean True — a
    # truthy string like "false" must not mark it migrated (SWARM-M E2)
    return [b for b in (bindings or [])
            if b.get("contract_id") == cid
            and b.get("active", True) and b.get("migrated") is not True]


def removal_findings(notice: dict, bindings: list[dict]) -> list[Finding]:
    """Deprecation is NOT removal (D-0007-58, INV-0007-42): a RETIRED surface
    with any active, unmigrated consumer binding is a P0 violation."""
    out: list[Finding] = []
    if notice.get("status") != "RETIRED":
        return out
    for b in _active_unmigrated(notice, bindings):
        out.append(Finding(
            DEPRECATION_WITH_ACTIVE_CONSUMER, P0,
            str(b.get("consumer_id") or "-"),
            f"surface {notice.get('contract_id')!r} was retired while "
            f"consumer {b.get('consumer_id')!r} is still active and "
            "unmigrated (D-0007-58, INV-0007-42)",
            {"deprecation_id": notice.get("deprecation_id")}))
    return out


def sunset_gate(notice: dict, *, bindings: list[dict], support_window: dict,
                historical_readers_ok: bool,
                rollback_or_forward_fix_ready: bool,
                unknown_critical_consumers: bool) -> dict:
    """The sunset gate (§12.9, D-0007-59): SunsetReady iff all known consumers
    migrated AND no unknown critical consumers AND the support window is
    satisfied AND historical readers keep working AND rollback or forward-fix
    is ready. Fail-closed: a missing input is a blocker, never a pass."""
    did = str(notice.get("deprecation_id") or notice.get("contract_id") or "-")
    blockers: list[str] = []
    findings: list[Finding] = []

    remaining = _active_unmigrated(notice, bindings)
    if remaining:
        blockers.append("consumers_not_migrated")
    if unknown_critical_consumers:
        blockers.append("unknown_critical_consumers")
        findings.append(Finding(UNKNOWN_CONSUMER, P0, did,
                                "sunset blocked: unknown critical consumers "
                                "may still depend on the surface (§12.9)",
                                {}))
    window = support_window or {}
    if not (window.get("status") == "EXPIRED"
            or window.get("satisfied") is True):
        blockers.append("support_window_not_satisfied")
    if not historical_readers_ok:
        blockers.append("historical_readers_not_preserved")
    if not rollback_or_forward_fix_ready:
        blockers.append("no_rollback_or_forward_fix")

    for blocker in blockers:
        if blocker == "unknown_critical_consumers":
            continue  # already carried as UNKNOWN_CONSUMER P0 above
        findings.append(Finding(
            SUNSET_NOT_READY, P1, did,
            f"sunset gate blocked: {blocker} (§12.9, D-0007-59)",
            {"blocker": blocker,
             "remaining_consumers": [b.get("consumer_id")
                                     for b in remaining]
             if blocker == "consumers_not_migrated" else []}))
    return {"sunset_ready": not blockers, "blockers": blockers,
            "findings": findings}


def validate_support_window(w: dict) -> list[Finding]:
    """Support windows follow the §13.6 alphabet; an EXTENDED_WITH_WAIVER
    window must carry a waiver expiry — waivers never extend forever
    (D-0007-61, AC-0007-182)."""
    out: list[Finding] = []
    wid = str(w.get("window_id") or w.get("contract_id") or "-")
    status = w.get("status")
    if status not in SUPPORT_WINDOW_STATES:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, wid,
                           f"unknown support window status {status!r}", {}))
    if status == "EXTENDED_WITH_WAIVER" and not w.get("waiver_expires_at"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, wid,
                           "support window extended by waiver without a "
                           "waiver expiry (waiver_expires_at) — waivers "
                           "always expire (D-0007-61, AC-0007-182)", {}))
    return out


def acknowledgment_findings(notice: dict, acks: list[dict]) -> list[Finding]:
    """Consumer migration acknowledgments (AC-0007-177): every active consumer
    on the notice should acknowledge the migration; unacknowledged consumers
    are listed as a P2 advisory."""
    acked = {a.get("consumer_id") for a in (acks or [])
             if a.get("acknowledged") is True}
    missing = [c for c in (notice.get("active_consumer_refs") or [])
               if c not in acked]
    if not missing:
        return []
    return [Finding(DEPRECATION_WITH_ACTIVE_CONSUMER, P2,
                    str(notice.get("deprecation_id") or "-"),
                    "active consumers have not acknowledged the deprecation "
                    f"migration: {missing} (AC-0007-177)",
                    {"unacknowledged": missing})]
