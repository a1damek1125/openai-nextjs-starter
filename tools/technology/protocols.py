"""Protocol Version Registry + Deprecation/Sunset Watch + Review Clock + Radar
(SP0004 D-0004-48/49/50/57, §10, INV-0004-15/16/18).

Architecture-critical protocols pin an EXPLICIT supported version — never floating
"latest" (D-0004-49, AC-0004-102). MCP and A2A are interoperability boundaries,
NOT Finalis authority (INV-0004-15/16). The registry detects REVIEW_OVERDUE from
local records; actual current status must be refreshed by research (D-0004-48).
Unsupported versions fail closed (§17.5). The radar (ADOPT/TRIAL/ASSESS/HOLD) is
advisory — the TDR remains authoritative (D-0004-57).
"""
from __future__ import annotations

from .model import (Finding, P1, P2, RADAR_RINGS, FLOATING_VERSION,
                    PROTOCOL_VERSION_STALE, PROTOCOL_DEPRECATION_REVIEW_REQUIRED,
                    INVALID_TDR)

FLOATING_TOKENS = {"latest", "*", "current", "stable", "main", "head"}
# protocols that must never carry Finalis internal authority (INV-0004-15/16)
NON_AUTHORITY_PROTOCOLS = {"MCP", "A2A", "OpenAPI", "AsyncAPI", "CloudEvents"}


def validate_protocols(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    for p in reg.get("protocols", []):
        pid = p.get("protocol_id", "-")
        ver = str(p.get("supported_version", "")).lower()
        if p.get("protected") and ver in FLOATING_TOKENS:
            out.append(Finding(FLOATING_VERSION, P1, pid,
                               f"protected protocol pins floating version "
                               f"{p.get('supported_version')!r} (AC-0004-102)",
                               {}))
        # a non-authority protocol must be classified as an interoperability
        # boundary, not authority (AC-0004-103/104). Normalize family + infer from
        # protocol_id so casing/whitespace/omitted-family cannot evade, and
        # default-deny: ANY protocol with role AUTHORITY is rejected outright
        # (red-team F6, INV-0004-15/16).
        fam = str(p.get("family", "")).strip().upper()
        inferred = fam or str(pid).strip().upper()
        is_non_authority = any(k in inferred for k in
                               (n.upper() for n in NON_AUTHORITY_PROTOCOLS))
        role = p.get("role")
        if role == "AUTHORITY":
            out.append(Finding(INVALID_TDR, P1, pid,
                               f"protocol {pid!r} declares role=AUTHORITY; "
                               "interoperability protocols are never Finalis "
                               "authority (INV-0004-15/16)", {}))
        elif is_non_authority and role != "INTEROP_BOUNDARY":
            out.append(Finding(INVALID_TDR, P1, pid,
                               f"{inferred} must be role=INTEROP_BOUNDARY, not "
                               f"{role!r} (INV-0004-15/16)", {}))
    return out


def deprecation_findings(reg: dict, *, today: str) -> list[Finding]:
    """REVIEW_OVERDUE from local records (D-0004-48). Advisory."""
    out: list[Finding] = []
    for p in reg.get("protocols", []):
        pid = p.get("protocol_id", "-")
        rb = p.get("review_by")
        if rb and str(rb) < str(today):
            out.append(Finding(PROTOCOL_DEPRECATION_REVIEW_REQUIRED, P2, pid,
                               "protocol review overdue from local record "
                               "(refresh via research)", {}))
        sunset = p.get("sunset_date")
        if sunset and str(sunset) < str(today):
            out.append(Finding(PROTOCOL_VERSION_STALE, P1, pid,
                               f"protocol {pid!r} is past its sunset date "
                               f"{sunset}", {}))
    return out


def validate_radar(radar: dict) -> list[Finding]:
    out: list[Finding] = []
    for e in radar.get("entries", []):
        if e.get("ring") not in RADAR_RINGS:
            out.append(Finding(INVALID_TDR, P1, e.get("technology", "-"),
                               f"invalid radar ring {e.get('ring')!r}", {}))
    return out
