"""Provider-Neutral Authorization Projection + Anti-Corruption Layer
(SP0006 §5.4/§5.6, D-0006-63, INV-0006-45).

External authorization standards are PROJECTIONS, not internal authority. SP0006
owns the one canonical internal capability lease; GNAP, OAuth-RAR, OAuth Token
Exchange, zcap-LD, UCAN and Macaroons may only PROJECT or TRANSPORT a lease as
evidence — they can never redefine its semantics or grant Finalis authority
(D-0006-63, INV-0006-45). Inbound external tokens are quarantined as UNTRUSTED
candidate requests and must pass internal admission before any live lease exists.

No real cryptography or signing is implemented here — a projection is a structural
descriptor only. Governance tooling only; product runtime must never import it
(INV-0006-46). It opens NO external effect (INV-0006-47).
"""
from __future__ import annotations

from .model import Finding, P0, P1, INVALID_WORK_SCHEMA, LEASE_SUBSET_DIMS
from .canon import core_hash

PROJECTION_FORMATS = ("GNAP", "OAUTH_RAR", "OAUTH_TOKEN_EXCHANGE", "ZCAP",
                      "UCAN", "MACAROON")

# formats whose native model is contextual attenuation-as-caveats.
_CAVEAT_NATIVE_FORMATS = ("MACAROON", "UCAN")


def _as_set(v) -> set:
    if isinstance(v, (list, set, tuple)):
        return {str(x) for x in v}
    if v is None:
        return set()
    return {str(v)}


def _lease_caveats(lease: dict, fmt: str) -> list[dict]:
    """Express the lease's attenuation as a deterministic list of caveats. For
    Macaroon/UCAN-native formats the attenuation delta is also carried as
    contextual caveats."""
    caveats: list[dict] = []
    for dim in LEASE_SUBSET_DIMS:            # operations/targets/data/effects
        vals = _as_set(lease.get(dim))
        if vals:
            caveats.append({"dimension": dim, "restrict_to": sorted(vals)})
    for dim in ("risk_ceiling", "cost_ceiling"):
        if lease.get(dim) is not None:
            caveats.append({"dimension": dim, "max": lease.get(dim)})
    if lease.get("expires_at"):
        caveats.append({"dimension": "expires_at",
                        "not_after": lease.get("expires_at")})
    if isinstance(lease.get("maximum_uses"), int):
        caveats.append({"dimension": "maximum_uses",
                        "max": lease.get("maximum_uses")})
    if fmt in _CAVEAT_NATIVE_FORMATS and lease.get("attenuation_delta"):
        caveats.append({"dimension": "attenuation_delta",
                        "contextual": lease.get("attenuation_delta")})
    return caveats


def project_lease(lease: dict, fmt: str) -> dict:
    """Produce a provider-neutral projection descriptor for a canonical internal
    lease. The descriptor is transport/evidence only and is explicitly non-
    authoritative (INV-0006-45)."""
    caveats = _lease_caveats(lease, fmt)
    descriptor = {
        "format": fmt,
        "projected_from_lease": lease.get("lease_id"),
        "caveats": caveats,
        "non_authoritative": True,
        "note": "projection is transport/evidence, not Finalis authority",
    }
    descriptor["projection_hash"] = core_hash({
        "format": fmt,
        "projected_from_lease": lease.get("lease_id"),
        "caveats": caveats,
    })
    return descriptor


def validate_projection(projection: dict) -> list[Finding]:
    """A projection that claims to GRANT authority or to be AUTHORITATIVE is
    rejected (P0); an unknown projection format is a P1 defect (AC-0006 external-
    projection criteria)."""
    out: list[Finding] = []
    subject = projection.get("projected_from_lease",
                             projection.get("format", "-"))
    if projection.get("grants_authority") is True \
            or projection.get("authoritative") is True:
        out.append(Finding(INVALID_WORK_SCHEMA, P0, subject,
                           "external authorization is a projection, not internal "
                           "authority (INV-0006-45)",
                           {"format": projection.get("format")}))
    fmt = projection.get("format")
    if fmt not in PROJECTION_FORMATS:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, subject,
                           f"unknown projection format {fmt!r} "
                           "(D-0006-63)", {"format": fmt}))
    return out


def anti_corruption_import(external_token: dict, fmt: str) -> dict:
    """Translate an inbound external token into an UNTRUSTED candidate capability
    request — never a live lease (D-0006-63, INV-0006-45). The proposed
    attenuation is a candidate ceiling only; a live lease exists solely after
    internal admission."""
    proposed = {
        "allowed_operations": sorted(_as_set(external_token.get("scope")
                                     or external_token.get("actions")
                                     or external_token.get("operations"))),
        "targets": sorted(_as_set(external_token.get("resources")
                          or external_token.get("targets"))),
        "caveats": external_token.get("caveats", []),
        "expires_at": external_token.get("exp") or external_token.get("expires_at"),
    }
    return {
        "status": "UNTRUSTED_PROJECTION",
        "format": fmt,
        "proposed_attenuation": proposed,
        "requires_internal_admission": True,
        "non_authoritative": True,
        "note": "external token is a projection; a live lease exists only after "
                "internal admission (D-0006-63, INV-0006-45)",
        "source_fingerprint": core_hash(external_token),
    }
