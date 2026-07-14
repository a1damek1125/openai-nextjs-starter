"""Gate registry, applicability engine, dependency DAG and the non-compensatory
gate lattice (SP0009 §10.3/10.4, §11.4/11.5, D-0009-07/08/09/11).

The lattice is the constitutional core: applicability (REQUIRED /
NOT_APPLICABLE / REVIEW_REQUIRED) is a separate dimension from result (PASS /
FAIL / UNKNOWN / STALE / INVALID / WAIVED). A required HARD gate qualifies only
on a literal PASS — UNKNOWN, STALE, INVALID and missing results all BLOCK
(fail-closed, D-0009-08), a WAIVED result counts only for a waivable gate with a
valid waiver, and no number of passing gates compensates for one hard failure
(D-0009-09). Policy aggregation is most-restrictive-wins (D-0009-11).
"""
from __future__ import annotations

from .canon import core_hash
from .model import (Finding, P0, P1, APPLICABILITY, GATE_RESULTS,
                    GATE_SEVERITIES)

# ---------------------------------------------------------------------------
# The gate registry: real gates for this repository, keyed by trigger classes.
# severity HARD gates are non-compensatory; waivable=False gates are on the
# Non-Waivable Gate Registry (AC-0009-069).
# ---------------------------------------------------------------------------
GATE_REGISTRY = {
    # constitutional hard, non-waivable
    "GATE_TENANT_ISOLATION": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "safety-kernel",
        "meaning": "tenant isolation invariants hold for changed surfaces",
        "triggers": ["AUTHORITY_CHANGE", "SEMANTIC_CHANGE", "CONTRACT_CHANGE"],
        "dependencies": [], "evidence_ttl": None},
    "GATE_RBAC_AUTHORITY": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "safety-kernel",
        "meaning": "no authority widening; RBAC checks intact",
        "triggers": ["AUTHORITY_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_SAFETY": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "safety-kernel",
        "meaning": "SP0005 safety kernel invariants unaffected or re-proven",
        "triggers": ["SAFETY_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_PROOF_INTEGRITY": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "proof envelopes and evidence ledgers verify",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    "GATE_SECRET_EXPOSURE": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "no secret value in diff, artifact or evidence",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    "GATE_ARTIFACT_INTEGRITY": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "verified digest equals promotable digest (build once)",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    # hard, waivable-with-compensating-control
    "GATE_COMPATIBILITY": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "compatibility",
        "meaning": "SP0007 compatibility vector admits the contract delta",
        "triggers": ["CONTRACT_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_CONTRACT_INVENTORY": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "contracts-inventory",
        "meaning": "SP0008 inventory reconciles the changed surfaces",
        "triggers": ["CONTRACT_CHANGE", "SEMANTIC_CHANGE"],
        "dependencies": ["GATE_COMPATIBILITY"], "evidence_ttl": None},
    "GATE_MIGRATION": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "migration is forward-only, numbered, with rollback or "
                   "declared forward-fix",
        "triggers": ["MIGRATION_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_UNIT_TESTS": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "selected unit/integration tests pass for this candidate",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    "GATE_BROWSER_E2E": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "browser E2E suite result recorded honestly incl. flakes",
        "triggers": ["SEMANTIC_CHANGE", "CONTRACT_CHANGE"],
        "dependencies": ["GATE_UNIT_TESTS"], "evidence_ttl": None},
    "GATE_MUTATION_ADEQUACY": {
        "gate_version": "1", "severity": "ADVISORY", "waivable": True,
        "owner": "release",
        "meaning": "non-equivalent mutants killed for changed kernels",
        "triggers": ["GOVERNANCE_TOOLING_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_BUILD_HERMETICITY": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "all build inputs declared; no undeclared network/env/time",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    "GATE_REPRODUCIBILITY": {
        "gate_version": "1", "severity": "ADVISORY", "waivable": True,
        "owner": "release",
        "meaning": "independent rebuild equivalence where declared",
        "triggers": ["*"], "dependencies": ["GATE_BUILD_HERMETICITY"],
        "evidence_ttl": None},
    "GATE_SUPPLY_CHAIN": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "dependency locks pinned; SBOM bound; provenance verifies",
        "triggers": ["DEPENDENCY_CHANGE", "CI_WORKFLOW_CHANGE"],
        "dependencies": [], "evidence_ttl": "P30D"},
    "GATE_CI_WORKFLOW_SECURITY": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "workflow permissions least-privilege; pinning; no "
                   "privileged untrusted checkout; no injection path",
        "triggers": ["CI_WORKFLOW_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_AGENTIC_INJECTION": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "no untrusted-content path into prompts/scripts/authority",
        "triggers": ["CI_WORKFLOW_CHANGE", "AI_CLOSURE_CHANGE"],
        "dependencies": [], "evidence_ttl": None},
    "GATE_AI_CLOSURE": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "ai-release",
        "meaning": "AI release closure complete for AI-affecting changes",
        "triggers": ["AI_CLOSURE_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_DOCUMENTATION": {
        "gate_version": "1", "severity": "ADVISORY", "waivable": True,
        "owner": "release",
        "meaning": "documentation obligations closed",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
    "GATE_ROLLBACK_OR_FORWARD_FIX": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "rollback proven or forward-fix declared for irreversibles",
        "triggers": ["MIGRATION_CHANGE", "CONTRACT_CHANGE"],
        "dependencies": [], "evidence_ttl": None},
    "GATE_FEATURE_FLAGS": {
        "gate_version": "1", "severity": "HARD", "waivable": True,
        "owner": "release",
        "meaning": "flags owned, safe-default, expiring, no authority widening",
        "triggers": ["SEMANTIC_CHANGE"], "dependencies": [],
        "evidence_ttl": None},
    "GATE_UNKNOWN_OUTCOME": {
        "gate_version": "1", "severity": "HARD", "waivable": False,
        "owner": "release",
        "meaning": "hard-scope unknown budget is zero (D-0009-06)",
        "triggers": ["*"], "dependencies": [], "evidence_ttl": None},
}

NON_WAIVABLE = frozenset(g for g, d in GATE_REGISTRY.items()
                         if d["waivable"] is False)


def gate_configuration_fingerprint(gate_id: str) -> str:
    """Fingerprint of the gate's exact configuration (AC-0009-064): a result is
    bound to the configuration that produced it."""
    return core_hash({"gate_id": gate_id, **GATE_REGISTRY[gate_id]})


def registry_findings() -> list[Finding]:
    """Structural checks: owners/meanings/versions present, DAG acyclic."""
    out: list[Finding] = []
    for gid, d in sorted(GATE_REGISTRY.items()):
        for fld in ("owner", "meaning", "gate_version"):
            if not d.get(fld):
                out.append(Finding("GATE_INVALID", P1, gid,
                                   f"gate missing {fld}", {}))
        if d.get("severity") not in GATE_SEVERITIES:
            out.append(Finding("GATE_INVALID", P1, gid,
                               f"bad severity {d.get('severity')!r}", {}))
    out.extend(dag_findings({g: d["dependencies"]
                             for g, d in GATE_REGISTRY.items()}))
    return out


def dag_findings(deps: dict) -> list[Finding]:
    """Reject cycles in the gate dependency DAG (AC-0009-058)."""
    out: list[Finding] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {g: WHITE for g in deps}

    def visit(g, stack):
        color[g] = GRAY
        for d in deps.get(g, ()):
            if d not in deps:
                continue
            if color.get(d) == GRAY:
                out.append(Finding(
                    "GATE_DEPENDENCY_CYCLE", P0, g,
                    f"gate dependency cycle: {' -> '.join(stack + [d])}", {}))
            elif color.get(d) == WHITE:
                visit(d, stack + [d])
        color[g] = BLACK

    for g in sorted(deps):
        if color[g] == WHITE:
            visit(g, [g])
    return out


# --- applicability (§11.4, D-0009-07) --------------------------------------------
def applicability(gate_id: str, change_classes: list) -> str:
    d = GATE_REGISTRY[gate_id]
    trig = d["triggers"]
    if "*" in trig:
        return "REQUIRED"
    hits = set(trig) & set(change_classes)
    if hits:
        return "REQUIRED"
    # a gate whose trigger classes are ADJACENT to the change (same family)
    # falls to REVIEW_REQUIRED rather than silently NOT_APPLICABLE when the
    # change contains unknowns
    if "UNKNOWN_CHANGE" in change_classes:
        return "REVIEW_REQUIRED"
    return "NOT_APPLICABLE"


def plan_gates(change_classes: list) -> dict:
    return {gid: applicability(gid, change_classes)
            for gid in sorted(GATE_REGISTRY)}


# --- the non-compensatory lattice (§11.5, §12.1, D-0009-08/09) --------------------
def _valid_waiver_for(gate_id: str, waivers: dict, *,
                      candidate_genome: str | None, now: str | None) -> bool:
    """A waiver counts ONLY when it is ACTIVE, bound to THIS candidate genome,
    and not expired (red-team #1: a bare status string is insufficient — full
    re-validation, fail-closed). If the caller cannot supply candidate_genome
    or now, a WAIVED result can never pass (fail-closed)."""
    w = (waivers or {}).get(gate_id)
    if not w or w.get("status") != "ACTIVE":
        return False
    if candidate_genome is None or now is None:
        return False               # cannot validate binding => reject
    if w.get("candidate_genome") != candidate_genome:
        return False               # cross-candidate waiver rejected
    exp = w.get("expires_at")
    if not exp or str(exp) <= str(now):
        return False               # missing/expired expiry rejected
    return True


def hard_verdict(plan: dict, results: dict, *, waivers: dict | None = None,
                 candidate_genome: str | None = None,
                 now: str | None = None) -> dict:
    """Aggregate gate results fail-closed.

    A required HARD gate contributes PASS only when its recorded result is the
    literal string PASS (never a truthy value, never a missing entry), or it is
    WAIVED, is waivable, and carries a valid ACTIVE, candidate-bound,
    non-expired waiver (validated with candidate_genome + now). Everything
    else — FAIL, UNKNOWN, STALE, INVALID, absent — BLOCKS. Advisory gates never
    block but are reported. No compensation, no averaging."""
    waivers = waivers or {}
    blocking: list = []
    advisory: list = []
    for gid, appl in sorted(plan.items()):
        if appl not in APPLICABILITY:
            blocking.append((gid, "INVALID_APPLICABILITY"))
            continue
        if appl == "NOT_APPLICABLE":
            continue
        sev = GATE_REGISTRY[gid]["severity"]
        res = results.get(gid)
        if appl == "REVIEW_REQUIRED":
            # review-required is not a pass; it blocks hard gates until a human
            # resolves applicability
            if sev == "HARD":
                blocking.append((gid, "REVIEW_REQUIRED"))
            else:
                advisory.append((gid, "REVIEW_REQUIRED"))
            continue
        if res == "PASS":
            continue
        if res == "WAIVED":
            if gid in NON_WAIVABLE:
                blocking.append((gid, "NON_WAIVABLE_WAIVER_REJECTED"))
            elif _valid_waiver_for(gid, waivers,
                                   candidate_genome=candidate_genome, now=now):
                continue
            else:
                blocking.append((gid, "WAIVER_INVALID"))
            continue
        # FAIL / UNKNOWN / STALE / INVALID / missing → fail closed
        code = res if res in GATE_RESULTS else "MISSING"
        if sev == "HARD":
            blocking.append((gid, code))
        else:
            advisory.append((gid, code))
    return {
        "qualifiable": not blocking,
        "blocking": [{"gate": g, "reason": r} for g, r in blocking],
        "advisory": [{"gate": g, "reason": r} for g, r in advisory],
    }


def most_restrictive(policies: list) -> dict:
    """Most-restrictive-wins aggregation over gate policies (D-0009-11): a gate
    required by ANY policy is required; a gate non-waivable in ANY policy is
    non-waivable; the tightest TTL wins."""
    agg: dict = {}
    for pol in policies:
        for gid, spec in pol.items():
            cur = agg.setdefault(gid, {"required": False, "waivable": True,
                                       "evidence_ttl": None})
            cur["required"] = cur["required"] or bool(spec.get("required"))
            cur["waivable"] = cur["waivable"] and bool(
                spec.get("waivable", True))
            ttl = spec.get("evidence_ttl")
            if ttl is not None and (cur["evidence_ttl"] is None
                                    or str(ttl) < str(cur["evidence_ttl"])):
                cur["evidence_ttl"] = ttl
    return agg
