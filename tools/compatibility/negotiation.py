"""Version pinning, negotiation, downgrade protection, the Compatibility
Firewall, directional version adapters, and bridges (SP0007 §10.4/§10.5,
D-0007-24/25/26/27/28, D-0007-47, AC-0007-111..125).

Protected contract bindings must pin exact versions — floating "latest" is a
silent-upgrade channel (D-0007-24, INV-0007-22). Negotiation is deterministic
and fail-closed: a missing, unsupported, or ambiguous requested version is
rejected, never guessed (D-0007-25/26). A proposal that lowers security
strength is blocked, and an unverified version never passes by default
(INV-0007-23). Provider-version semantics never leak into core; they are
adapted at the firewall (D-0007-27). Adapters are directional, declare their
losses, and can never redefine core semantics (D-0007-28, INV-0007-24).
Bridges (semantic-epoch / protocol-version / proof-envelope) are evidence and
transport, never semantic authority (D-0007-47).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, DIRECTIONS, VERSION_DOWNGRADE_DETECTED,
                    SECURITY_DOWNGRADE_BLOCKED, INVALID_COMPAT_SCHEMA)
from .canon import core_hash

BRIDGE_KINDS = ("SEMANTIC_EPOCH", "PROTOCOL_VERSION", "PROOF_ENVELOPE")

_FLOATING_TOKENS = frozenset({"latest", "*", ""})
_RANGE_CHARS = ("*", "^", "~", "<", ">")


def _is_floating(version) -> bool:
    """A floating/"latest" reference — no exact pin at all (D-0007-24)."""
    if not isinstance(version, str) or not version.strip():
        return True
    v = version.strip()
    return v.lower() in _FLOATING_TOKENS


def _is_exact_pin(version) -> bool:
    if _is_floating(version):
        return False
    v = version.strip()
    if any(ch in v for ch in _RANGE_CHARS):
        return False
    if v.endswith(".x") or ".x." in v:
        return False
    return True


def pinning_findings(binding: dict) -> list[Finding]:
    """Protected contract bindings pin exact versions (D-0007-24, INV-0007-22).

    Fail-closed: a binding without a "protected" key is treated as protected.
    Ranges are tolerated only when the binding explicitly declares
    {"protected": False}.
    """
    out: list[Finding] = []
    subject = str(binding.get("contract_id") or binding.get("binding_id") or "-")
    protected = binding.get("protected", True)  # fail-closed default
    version = binding.get("version")
    if not protected:
        return out
    if _is_floating(version):
        out.append(Finding(
            VERSION_DOWNGRADE_DETECTED, P0, subject,
            f"protected contract binding floats on {version!r} (latest / "
            "unpinned): silent upgrade and downgrade channel — pin an exact "
            "version (D-0007-24, INV-0007-22)",
            {"version": version, "protected": True}))
    elif not _is_exact_pin(version):
        out.append(Finding(
            VERSION_DOWNGRADE_DETECTED, P0, subject,
            f"protected contract binding uses version range {version!r}; "
            "ranges are allowed only for bindings explicitly declared "
            "unprotected (D-0007-24)",
            {"version": version, "protected": True}))
    return out


def negotiate(supported: list[str], requested: str | None, *,
              security_rank: dict | None = None) -> dict:
    """Deterministic fail-closed version negotiation (D-0007-25/26).

    Never guesses: missing, ambiguous, or unsupported requested versions
    FAIL_CLOSED. The evaluated set is recorded for observability.
    """
    evaluated = list(supported)
    if requested is None:
        return {"result": "FAIL_CLOSED", "reason": "missing version",
                "evaluated": evaluated}
    # a floating token ("latest"/"*"/…) is never an acceptable pin even if a
    # malformed `supported` list contains it (SWARM-M E6; D-0007-24)
    if _is_floating(requested):
        return {"result": "FAIL_CLOSED",
                "reason": f"floating/unpinned version {requested!r}",
                "evaluated": evaluated}
    if "*" in requested or "-" in requested:
        return {"result": "FAIL_CLOSED",
                "reason": f"ambiguous version range {requested!r}",
                "evaluated": evaluated}
    if requested not in supported:
        return {"result": "FAIL_CLOSED",
                "reason": f"unsupported version {requested!r}",
                "evaluated": evaluated}
    if security_rank is not None and requested not in security_rank:
        return {"result": "FAIL_CLOSED",
                "reason": f"version {requested!r} has no security rank "
                          "(unverified fallback refused)",
                "evaluated": evaluated}
    return {"result": "ACCEPTED", "version": requested,
            "evaluated": evaluated}


def downgrade_findings(current: str, proposed: str, *,
                       security_rank: dict) -> list[Finding]:
    """Block security downgrades (INV-0007-23). security_rank maps
    version -> int, higher = stronger. Unknown versions fail closed."""
    out: list[Finding] = []
    subject = f"{current}->{proposed}"
    unknown = [v for v in (current, proposed) if v not in security_rank]
    if unknown:
        out.append(Finding(
            SECURITY_DOWNGRADE_BLOCKED, P0, subject,
            f"version(s) {unknown} have no security rank; fail-closed — an "
            "unverified fallback is never accepted (INV-0007-23)",
            {"current": current, "proposed": proposed, "unknown": unknown}))
        return out
    if security_rank[proposed] < security_rank[current]:
        out.append(Finding(
            SECURITY_DOWNGRADE_BLOCKED, P0, subject,
            f"proposed version {proposed!r} (rank "
            f"{security_rank[proposed]}) is weaker than current "
            f"{current!r} (rank {security_rank[current]}); security "
            "downgrade blocked (INV-0007-23)",
            {"current_rank": security_rank[current],
             "proposed_rank": security_rank[proposed]}))
    return out


def firewall_findings(core_module: dict) -> list[Finding]:
    """Compatibility Firewall (D-0007-27): core contracts never branch on
    provider versions; adaptation happens at the firewall boundary."""
    out: list[Finding] = []
    subject = str(core_module.get("contract_id") or
                  core_module.get("module_id") or "-")
    branches = core_module.get("provider_version_branches")
    if branches:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            "provider-version semantics leaked into core; adapt at the "
            "firewall (D-0007-27)",
            {"provider_version_branches": branches}))
    return out


_ADAPTER_REQUIRED = ("source_contract", "source_version", "target_contract",
                     "target_version", "direction", "losses",
                     "failure_semantics", "semantic_epoch_relationship")


def validate_adapter(adapter: dict) -> list[Finding]:
    """Directional version adapter validation (D-0007-28, AC-0007-118..122).

    Adapters declare direction, losses (possibly empty, but always declared),
    failure semantics, and their semantic-epoch relationship. An adapter can
    translate; it can never redefine core semantics (INV-0007-24).
    """
    out: list[Finding] = []
    subject = (f"{adapter.get('source_contract', '-')}@"
               f"{adapter.get('source_version', '-')}->"
               f"{adapter.get('target_contract', '-')}@"
               f"{adapter.get('target_version', '-')}")
    for fld in _ADAPTER_REQUIRED:
        if fld not in adapter or adapter.get(fld) is None:
            out.append(Finding(
                INVALID_COMPAT_SCHEMA, P1, subject,
                f"adapter missing required field {fld!r} (fail-closed, "
                "D-0007-28)", {"missing": fld}))
    direction = adapter.get("direction")
    if direction is not None and direction not in DIRECTIONS:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            f"adapter direction {direction!r} not in {list(DIRECTIONS)}",
            {"direction": direction}))
    if adapter.get("redefines_semantics"):
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P0, subject,
            "adapter cannot redefine core semantics (INV-0007-24)",
            {"redefines_semantics": adapter.get("redefines_semantics")}))
    return out


def bridge(kind: str, old_ref: str, new_ref: str, *,
           rules: dict | None = None) -> dict:
    """Build a bridge record (D-0007-47): Semantic Epoch Bridge, Protocol
    Version Bridge, or Proof Envelope Bridge. Bridges are non-authoritative
    evidence/transport — never semantic authority."""
    record = {"bridge_kind": kind, "old": old_ref, "new": new_ref,
              "rules": rules or {}, "non_authoritative": True}
    record["bridge_hash"] = core_hash(record)
    return record


def validate_bridge(b: dict) -> list[Finding]:
    out: list[Finding] = []
    subject = f"{b.get('old', '-')}->{b.get('new', '-')}"
    kind = b.get("bridge_kind")
    if kind not in BRIDGE_KINDS:
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P1, subject,
            f"unknown bridge kind {kind!r}; expected one of "
            f"{list(BRIDGE_KINDS)}", {"bridge_kind": kind}))
    if b.get("authoritative"):
        out.append(Finding(
            INVALID_COMPAT_SCHEMA, P0, subject,
            "bridge claims semantic authority; bridges are evidence/"
            "transport, never semantic authority (D-0007-47)",
            {"authoritative": b.get("authoritative")}))
    return out
