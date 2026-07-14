"""Compatibility Fitness Functions, the Migration Debt Registry, and the
Compatibility Observatory (SP0007 §19, D-0007-62/63, AC-0007-183..188).

Nine standing fitness functions continuously measure the program: ownership of
protected contracts, sealed released versions, current evidence for active
bindings, replacements for deprecated surfaces, replay safety of workflow
changes, declared reversibility of migration edges, readers for every proof
version, exact provider pins, and rollback points behind destructive edges
(D-0007-63). Migration debt is tracked explicitly, never hidden in an average
(D-0007-62, AC-0007-183). The observatory is ADVISORY — a dashboard is never
a gate (§19).
"""
from __future__ import annotations

from .model import (Finding, P1, IMMUTABLE_STATES, CONTRACT_OWNER_MISSING,
                    COMPATIBILITY_EVIDENCE_STALE,
                    COMPATIBILITY_FITNESS_DEGRADED)
from .vector import hard_gate, overall, freshness
from .contracts import parse_semver

_PROTECTED_CRITICALITY = ("C2", "C3", "C4")
_FLOATING = ("latest", "*", "", None)
_CURRENT_CLAIM_STATES = ("VERIFIED", "PARTIALLY_VERIFIED")


def _deg(subject, message, **details) -> Finding:
    return Finding(COMPATIBILITY_FITNESS_DEGRADED, P1, str(subject), message,
                   details)


def _owned(d: dict) -> bool:
    return bool(d.get("owner") or d.get("owner_capability"))


def fitness_findings(program: dict) -> list[Finding]:
    """The nine standing compatibility fitness functions (D-0007-63,
    AC-0007-184..188) over a loaded program dict."""
    out: list[Finding] = []
    program = program or {}
    descriptors = program.get("descriptors") or []
    versions = program.get("versions") or []
    bindings = program.get("bindings") or []
    claims = program.get("claims") or []

    # 1. every protected contract has an owner
    for d in descriptors:
        protected = d.get("stability") == "STABLE" or \
            d.get("criticality") in _PROTECTED_CRITICALITY
        if protected and not _owned(d):
            out.append(Finding(CONTRACT_OWNER_MISSING, P1,
                               str(d.get("contract_id") or "-"),
                               "protected contract has no owner "
                               "(D-0007-63 F1)", {}))

    # 2. every released version is sealed by a content hash
    for v in versions:
        if v.get("status") in IMMUTABLE_STATES and not v.get("content_hash"):
            out.append(_deg(f"{v.get('contract_id','-')}@"
                            f"{v.get('version','-')}",
                            "released version has no sealed content hash — "
                            "immutability unwitnessed (D-0007-63 F2)"))

    # 3. every active binding carries current compatibility evidence
    for b in bindings:
        if not b.get("active", True):
            continue
        current = [c for c in claims
                   if c.get("contract_id") == b.get("contract_id")
                   and c.get("consumer_id") == b.get("consumer_id")
                   and c.get("status") in _CURRENT_CLAIM_STATES]
        if not current:
            out.append(Finding(COMPATIBILITY_EVIDENCE_STALE, P1,
                               str(b.get("consumer_id") or "-"),
                               "active consumer binding has no current "
                               "verified compatibility claim "
                               "(D-0007-63 F3)",
                               {"contract_id": b.get("contract_id")}))

    # 4. every deprecated surface names a replacement
    for n in program.get("deprecations") or []:
        if not n.get("replacement"):
            out.append(_deg(n.get("deprecation_id") or
                            n.get("contract_id") or "-",
                            "deprecated surface has no replacement "
                            "(D-0007-63 F4)"))

    # 5. every workflow-affecting change proves replay safety
    for w in program.get("workflow_changes") or []:
        if w.get("replay_passed") is not True:
            out.append(_deg(w.get("change_id") or w.get("workflow_id") or "-",
                            "workflow change without a passing replay proof "
                            "(D-0007-63 F5)"))

    # 6. every migration edge declares its reversibility
    for e in program.get("migration_edges") or []:
        if e.get("reversibility", "UNKNOWN") == "UNKNOWN":
            out.append(_deg(e.get("edge_id") or
                            f"{e.get('from_version','-')}->"
                            f"{e.get('to_version','-')}",
                            "migration edge reversibility is UNKNOWN "
                            "(D-0007-63 F6)"))

    # 7. every proof version has a reader
    readable = set()
    for r in program.get("proof_readers") or []:
        if isinstance(r, dict):
            readable.add(r.get("proof_version"))
            readable.update(r.get("supported_versions") or [])
        else:
            readable.add(r)
    for v in versions:
        pc = v.get("proof_contract")
        pv = pc.get("proof_version") if isinstance(pc, dict) else pc
        if pv and pv not in readable:
            out.append(_deg(f"{v.get('contract_id','-')}@"
                            f"{v.get('version','-')}",
                            f"proof version {pv!r} has no registered reader "
                            "(D-0007-63 F7)", proof_version=pv))

    # 8. every provider pin is exact — no floating "latest"
    for p in program.get("provider_pins") or []:
        if p.get("version") in _FLOATING:
            out.append(_deg(p.get("provider_id") or "-",
                            f"provider pin floats on {p.get('version')!r} "
                            "(D-0007-63 F8)"))

    # 9. every destructive edge keeps a last safe rollback point
    for e in program.get("migration_edges") or []:
        losses = e.get("loss_vector") or {}
        destructive = any(level not in ("NONE", None)
                          for level in losses.values())
        if destructive and not e.get("last_safe_rollback_point"):
            out.append(_deg(e.get("edge_id") or
                            f"{e.get('from_version','-')}->"
                            f"{e.get('to_version','-')}",
                            "destructive migration edge has no last safe "
                            "rollback point (D-0007-63 F9)",
                            loss_vector=dict(losses)))
    return out


def _semver_key(v: dict):
    parsed = parse_semver(v.get("version", ""))
    return (parsed is not None, parsed or (0, 0, 0), str(v.get("version")))


def debt_registry(program: dict) -> dict:
    """Explicit migration-debt counts (D-0007-62, AC-0007-183) — debt is
    named and counted, never averaged away."""
    program = program or {}
    versions = program.get("versions") or []
    bindings = program.get("bindings") or []
    claims = program.get("claims") or []
    edges = program.get("migration_edges") or []
    validator = program.get("validator_version")

    # supported old versions: non-retired, non-draft versions of a contract
    # that are not its newest supported version
    by_contract: dict = {}
    for v in versions:
        if v.get("status") in ("DRAFT", "REVIEWED", "RETIRED"):
            continue
        by_contract.setdefault(v.get("contract_id"), []).append(v)
    supported_old = 0
    for group in by_contract.values():
        if len(group) > 1:
            supported_old += len(group) - 1
            _ = max(group, key=_semver_key)  # newest is the current version

    stale = 0
    for c in claims:
        if c.get("status") == "STALE" or (
                validator and freshness(
                    c, validator_version=validator) == "STALE"):
            stale += 1

    return {
        "supported_old_versions": supported_old,
        "retained_adapters": len(program.get("adapters") or []),
        "dual_write_active": sum(
            1 for e in edges if e.get("dual_write_active")) + len(
            program.get("dual_writes") or []),
        "unmigrated_consumers": sum(
            1 for b in bindings
            if b.get("active", True) and not b.get("migrated")),
        "stale_claims": stale,
        "one_way_edges": sum(
            1 for e in edges if e.get("reversibility") == "ONE_WAY"),
        "replay_gaps": sum(
            1 for w in program.get("workflow_changes") or []
            if w.get("replay_passed") is not True),
        "unowned_contracts": sum(
            1 for d in program.get("descriptors") or [] if not _owned(d)),
    }


def observatory(program: dict) -> dict:
    """The §19 Compatibility Observatory summary. ADVISORY only — the
    dashboard never gates; gates are the fitness findings and the Report."""
    program = program or {}
    claims = program.get("claims") or []
    claims_by_status: dict = {}
    claims_by_verdict: dict = {}
    hard_gate_failures = 0
    for c in claims:
        claims_by_status[c.get("status", "PROPOSED")] = \
            claims_by_status.get(c.get("status", "PROPOSED"), 0) + 1
        vec = c.get("compatibility_vector") or {}
        verdict = overall(vec)
        claims_by_verdict[verdict] = claims_by_verdict.get(verdict, 0) + 1
        if hard_gate(vec) == "INCOMPATIBLE":
            hard_gate_failures += 1
    versions_by_status: dict = {}
    for v in program.get("versions") or []:
        versions_by_status[v.get("status", "DRAFT")] = \
            versions_by_status.get(v.get("status", "DRAFT"), 0) + 1
    deprecations_by_status: dict = {}
    for n in program.get("deprecations") or []:
        deprecations_by_status[n.get("status", "PROPOSED")] = \
            deprecations_by_status.get(n.get("status", "PROPOSED"), 0) + 1
    fixtures_by_class: dict = {}
    for fx in program.get("fixtures") or []:
        fixtures_by_class[fx.get("corpus_class", "COMMON")] = \
            fixtures_by_class.get(fx.get("corpus_class", "COMMON"), 0) + 1
    return {
        "classification": "ADVISORY_NOT_A_GATE",
        "contracts": len(program.get("descriptors") or []),
        "versions": len(program.get("versions") or []),
        "versions_by_status": versions_by_status,
        "bindings": len(program.get("bindings") or []),
        "claims": len(claims),
        "claims_by_status": claims_by_status,
        "claims_by_verdict": claims_by_verdict,
        "hard_gate_failures": hard_gate_failures,
        "migration_edges": len(program.get("migration_edges") or []),
        "deprecations": len(program.get("deprecations") or []),
        "deprecations_by_status": deprecations_by_status,
        "fixtures_by_class": fixtures_by_class,
        "debt": debt_registry(program),
    }
