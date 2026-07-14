"""Architecture waiver lifecycle (SP0001 §13.2, D-0001-09).

PROPOSED -> ACTIVE -> EXPIRED (or REJECTED / REVOKED). No permanent anonymous
waiver: every waiver needs an owner, reason, and expiry. `now` is passed in
explicitly (never wall-clock) so results stay deterministic (INV-0001-12).
An expired-but-still-relied-on waiver is a WAIVER_EXPIRED finding (P1).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .model import Finding, P1, P2, WAIVER_EXPIRED

STATES = {"PROPOSED", "ACTIVE", "EXPIRED", "REJECTED", "REVOKED"}


def _parse(d: str) -> date:
    y, m, day = (int(x) for x in d.split("-"))
    return date(y, m, day)


def validate_waiver(w: dict) -> list[str]:
    errors: list[str] = []
    for f in ("waiver_id", "scope", "reason", "owner", "created_at", "expires_at",
              "status"):
        if not w.get(f):
            errors.append(f"waiver missing field: {f}")
    if w.get("status") and w["status"] not in STATES:
        errors.append(f"invalid waiver status: {w['status']}")
    if not w.get("owner"):
        errors.append("no permanent anonymous waiver: owner required")
    return errors


def _within_lifetime(w: dict, max_days: int) -> bool:
    try:
        created = _parse(w["created_at"])
        expires = _parse(w["expires_at"])
    except (KeyError, ValueError):
        return False
    return expires >= created and (expires - created).days <= max_days


def is_valid_active(w: dict, now: str, max_days: int) -> bool:
    """A waiver may suppress a finding ONLY if it is well-formed, owned, ACTIVE,
    unexpired, and within the max lifetime (SP0001 §13.2 — no permanent anonymous
    waiver). Enforced at GATE time (red-team GAP-1), not just in unit tests."""
    if validate_waiver(w):
        return False
    if w.get("status") != "ACTIVE":
        return False
    if not _within_lifetime(w, max_days):
        return False
    try:
        return _parse(w["expires_at"]) >= _parse(now)
    except (KeyError, ValueError):
        return False


def active_scopes(waivers: list[dict], now: str, max_days: int = 90) -> set[str]:
    """Scopes covered by a VALID, currently-active, unexpired waiver."""
    return {w["scope"] for w in waivers if is_valid_active(w, now, max_days)}


def invalid_waiver_findings(waivers: list[dict], now: str,
                            max_days: int = 90) -> list[Finding]:
    """Active waivers that are anonymous, malformed, or over-lifetime — they do
    NOT suppress anything and are surfaced (P1) so tampering is visible."""
    out: list[Finding] = []
    for w in waivers:
        if w.get("status") != "ACTIVE":
            continue
        reasons = validate_waiver(w)
        if not _within_lifetime(w, max_days):
            reasons = reasons + [f"lifetime exceeds {max_days} days or inverted dates"]
        if reasons:
            out.append(Finding("INVALID_WAIVER", P1, w.get("scope", "-"),
                               f"waiver {w.get('waiver_id', '?')} is invalid and "
                               f"suppresses nothing: {reasons}",
                               {"waiver": w, "reasons": reasons}))
    return out


def expired_findings(waivers: list[dict], now: str) -> list[Finding]:
    today = _parse(now)
    out: list[Finding] = []
    for w in waivers:
        if w.get("status") != "ACTIVE":
            continue
        try:
            exp = _parse(w["expires_at"])
        except (KeyError, ValueError):
            continue
        if exp < today:
            out.append(Finding(WAIVER_EXPIRED, P1, w.get("scope", "-"),
                               f"waiver {w.get('waiver_id')} expired {w['expires_at']}",
                               {"waiver": w, "as_of": now}))
    return out


def status_report(waivers: list[dict], now: str) -> dict[str, Any]:
    return {
        "total": len(waivers),
        "active": len(active_scopes(waivers, now)),
        "expired": len(expired_findings(waivers, now)),
        "as_of": now,
    }
