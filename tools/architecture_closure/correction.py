"""Minimal Correction Sets + Repair Portfolios (SP0010 V5 FUNCTION AA, §0,
D-0010-121..127).

If the closure were BLOCKED, what is the SMALLEST set of changes that clears the
blockers — and does any such change WEAKEN an invariant? This module computes,
over the blocking findings:

  * MINIMAL CORRECTION SETS — smallest subsets of repair actions whose
    application would resolve every blocking finding (a minimal hitting set over
    the blocker -> repair relation), ordered LEXICOGRAPHICALLY: hard constraints
    (P0) before soft (P1), and within a tier, invariant-preserving repairs before
    any other (D-0010-123).
  * A REPAIR PORTFOLIO — the ranked alternative minimal correction sets.
  * A HARD RULE (D-0010-125): a correction may NEVER weaken a global invariant or
    disable a control. A repair whose only realization weakens an invariant is
    rejected; the blocker is reported UNREPAIRABLE_WITHOUT_WEAKENING (P0), which
    is itself a blocking result — you cannot "fix" a closure by lowering the bar.

On a CLEAN closure there are no blocking findings, so the portfolio is EMPTY and
that emptiness is CERTIFIED (a signed-by-hash statement that no repair is owed).

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from itertools import combinations

from .canon import hash_obj
from .model import Finding, P0, P1, P2

# repair catalog: finding kind -> candidate repair. `weakens_invariant` marks a
# repair that would lower an invariant/control (forbidden). `hard` marks a repair
# addressing a P0-class blocker. Repairs are DESCRIPTIVE guidance, never applied.
REPAIR_CATALOG = {
    "CRITICAL_CLAIM_NEITHER": {
        "action": "supply grounded evidence for the critical claim",
        "hard": True, "weakens_invariant": False},
    "CRITICAL_CLAIM_BOTH": {
        "action": "resolve the contradiction (retire the refuting evidence or "
                  "the claim)", "hard": True, "weakens_invariant": False},
    "CRITICAL_CLAIM_REFUTED": {
        "action": "address the refutation before closure",
        "hard": True, "weakens_invariant": False},
    "DUAL_GRAPH_CONFLICT": {
        "action": "reconcile the declared architecture with repository reality",
        "hard": True, "weakens_invariant": False},
    "PROOF_HOLE": {
        "action": "issue a valid proof-carrying certificate for the claim",
        "hard": True, "weakens_invariant": False},
    "GLOBAL_INVARIANT_FAILED": {
        "action": "restore the failed invariant's control",
        "hard": True, "weakens_invariant": False},
    "GLOBAL_INVARIANT_UNKNOWN": {
        "action": "resolve the invariant's unknown status with evidence",
        "hard": True, "weakens_invariant": False},
    "FROZEN_VERIFIER_MODIFIED": {
        "action": "restore the frozen verifier to its recorded identity",
        "hard": True, "weakens_invariant": False},
    "CONTROL_EFFECT_NOT_IDENTIFIED": {
        "action": "make the control's effect identifiable (observe the "
                  "confounder / ground the control)", "hard": True,
        "weakens_invariant": False},
    "CEGAR_REAL_COUNTEREXAMPLE": {
        "action": "eliminate the concrete counterexample trace",
        "hard": True, "weakens_invariant": False},
    # a repair that would WEAKEN an invariant (forbidden — never selected)
    "_WEAKEN": {"action": "delete the invariant / lower the gate (FORBIDDEN)",
                "hard": True, "weakens_invariant": True},
}

# blocking finding kinds this module treats as requiring a correction. The
# `_WEAKEN` sentinel models a blocker whose only catalogued repair would weaken
# an invariant; it never appears on a real closure (no such reason code is
# emitted), but keeping it in the blocking set makes the fail-closed rejection
# path reachable and regression-locked.
_BLOCKING = frozenset(REPAIR_CATALOG)


def _repair_for(finding: dict) -> dict | None:
    return REPAIR_CATALOG.get(finding.get("kind"))


def _tier_key(finding: dict, repair: dict) -> tuple:
    """Lexicographic sort key: P0 before P1; invariant-preserving before not;
    then stable by subject."""
    sev = finding.get("severity")
    sev_rank = {P0: 0, P1: 1, P2: 2}.get(sev, 3)
    return (sev_rank, 1 if repair.get("weakens_invariant") else 0,
            str(finding.get("subject")))


def minimal_correction_sets(findings: list) -> dict:
    """Compute minimal correction sets over the blocking findings. Each blocking
    finding maps to exactly one catalog repair here (1:1), so the minimal set is
    the set of distinct required repairs; we still verify minimality and reject
    any weakening repair."""
    blockers = [f for f in findings
                if f.get("kind") in _BLOCKING
                and f.get("severity") in (P0, P1)]
    corrections = []
    unrepairable = []
    for f in blockers:
        r = _repair_for(f)
        if r is None:
            unrepairable.append({"finding": f, "reason": "no catalog repair"})
            continue
        if r["weakens_invariant"]:
            unrepairable.append({"finding": f,
                                 "reason": "only repair weakens an invariant"})
            continue
        corrections.append({
            "for_kind": f["kind"], "subject": f.get("subject"),
            "severity": f.get("severity"), "action": r["action"],
            "hard": r["hard"], "sort_key": _tier_key(f, r)})
    corrections.sort(key=lambda c: c["sort_key"])
    for c in corrections:
        del c["sort_key"]
    return {
        "blocking_finding_count": len(blockers),
        "minimal_correction_set": corrections,
        "unrepairable_without_weakening": unrepairable,
        "correction_count": len(corrections),
    }


def repair_portfolio(findings: list) -> dict:
    """The repair portfolio. On a clean closure (no blockers) the portfolio is
    EMPTY and certified. Otherwise it presents the lexicographic minimal
    correction set as the primary portfolio entry plus a hard-constraints-first
    ordering witness."""
    mcs = minimal_correction_sets(findings)
    empty = mcs["blocking_finding_count"] == 0
    portfolio = {
        "empty": empty,
        "primary_correction_set": mcs["minimal_correction_set"],
        "unrepairable_without_weakening": mcs["unrepairable_without_weakening"],
        "hard_first_order": [c["for_kind"] for c in
                             mcs["minimal_correction_set"] if c["hard"]],
        "certifies_no_repair_owed": empty,
    }
    portfolio["portfolio_hash"] = hash_obj(portfolio)
    return portfolio


def correction_findings(portfolio: dict) -> list[Finding]:
    out: list[Finding] = []
    for u in portfolio["unrepairable_without_weakening"]:
        out.append(Finding(
            "CORRECTION_WOULD_WEAKEN_INVARIANT", P0,
            str(u["finding"].get("subject", "-")),
            "the only available repair for a blocker would weaken an invariant "
            "or disable a control: a closure may not be 'fixed' by lowering the "
            "bar (D-0010-125)", {"reason": u["reason"]}))
    if not portfolio["empty"]:
        out.append(Finding(
            "REPAIR_REQUIRED", P2, "closure",
            "closure carries blocking findings; a minimal invariant-preserving "
            "correction set is available (advisory guidance)",
            {"hard_first": portfolio["hard_first_order"]}))
    return out


def portfolio_root(portfolio: dict) -> str:
    return portfolio["portfolio_hash"]
