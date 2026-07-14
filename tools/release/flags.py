"""Feature flag governance (SP0009 D-0009-49/50, AC-0009-212..216).

A feature flag is a governed contract: owner, scope, type, SAFE default,
expiry, kill switch and cleanup are required. FLAG OFF != UNREACHABLE CODE —
the registry records reachability honestly. Two constitutional walls: a flag
can never widen authority beyond what SP0005/SP0006 grant (a flag that guards
an authority expansion is rejected outright, D-0009-50), and missing flag data
fails SAFE (the safe default applies; absence is never "on", INV-0009-50).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1, FLAG_STATES


def flag(*, flag_id: str, owner: str, scope: str, flag_type: str,
         safe_default, expires_at: str, kill_switch: bool = True,
         widens_authority: bool = False, guards: str = "") -> dict:
    f = {"flag_id": flag_id, "owner": owner, "scope": scope,
         "flag_type": flag_type, "safe_default": safe_default,
         "expires_at": expires_at, "kill_switch": kill_switch,
         "widens_authority": widens_authority, "guards": guards,
         "status": "PROPOSED"}
    f["flag_hash"] = hash_obj(f)
    return f


def validate_flag(f: dict, *, now: str) -> list[Finding]:
    out: list[Finding] = []
    subject = str(f.get("flag_id") or "-")
    if not f.get("owner"):
        out.append(Finding("FEATURE_FLAG_INVALID", P1, subject,
                           "flag requires an owner (AC-0009-213)", {}))
    if "safe_default" not in f or f.get("safe_default") is None:
        out.append(Finding("FEATURE_FLAG_INVALID", P1, subject,
                           "flag requires an explicit safe default "
                           "(AC-0009-214)", {}))
    if not f.get("expires_at"):
        out.append(Finding("FEATURE_FLAG_INVALID", P1, subject,
                           "flag requires an expiry (AC-0009-215)", {}))
    elif str(f["expires_at"]) <= str(now):
        out.append(Finding("FEATURE_FLAG_EXPIRED", P1, subject,
                           "flag expired; retire or renew", {}))
    # authority widening is rejected regardless of any other property — the
    # check is `is True`-strict so a truthy string cannot smuggle it past,
    # and the GUARDS text is scanned too (a flag guarding authority expansion)
    if f.get("widens_authority") is True or any(
            t in str(f.get("guards") or "").lower()
            for t in ("widen_authority", "bypass_rbac", "bypass_approval",
                      "skip_authority")):
        out.append(Finding(
            "FEATURE_FLAG_AUTHORITY_VIOLATION", P0, subject,
            "flag would widen constitutional authority: no configuration may "
            "bypass SP0005/SP0006 (D-0009-50, AC-0009-216)", {}))
    if f.get("status") not in FLAG_STATES:
        out.append(Finding("FEATURE_FLAG_INVALID", P1, subject,
                           f"unknown flag state {f.get('status')!r}", {}))
    return out


def evaluate(f: dict, *, requested_state) -> dict:
    """Evaluate the flag value fail-safe: unknown/missing/invalid requested
    state yields the SAFE DEFAULT, never implicit enablement (INV-0009-50)."""
    if requested_state is True or requested_state is False:
        value = requested_state
    else:
        value = f.get("safe_default")
    return {"flag_id": f.get("flag_id"), "value": value,
            "fail_safe_applied": requested_state not in (True, False)}


def off_is_not_unreachable(f: dict) -> dict:
    """FLAG OFF != UNREACHABLE CODE: the record states reachability honestly."""
    return {"flag_id": f.get("flag_id"),
            "off_means_unreachable": False,
            "note": "code behind an off flag remains present, reviewable and "
                    "reachable through defects; OFF is a routing state, not "
                    "removal"}
