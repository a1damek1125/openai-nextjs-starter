"""Requirement Hypergraph + Minimal Support/Refutation/Missing-Evidence Bases +
Mandatory Context Reservation + Robust Submodular Selection + Value-of-Information
Retrieval + Anytime-Valid & Conformal-with-Shift-Guard diagnostics (TOOL-B10
§U/V/W/AC/AD/AE, Innovations 3/4/5/9/10, §11.4..11.7, §12.4..12.9,
D-B6-048..060, 121..140, 161..190).

A work requirement is a HYPEREDGE over claims: it is satisfied only by a set of
claims that JOINTLY discharge it, and a critical requirement is satisfied only by
SUPPORTED_ONLY claims (BOTH/NEITHER never satisfy, model.closes_critical). We
compute the MINIMAL SUPPORT BASES (subset-minimal claim sets that satisfy the
requirement — an antichain), the MINIMAL REFUTATION BASES (subset-minimal sets
that refute), and the MISSING-EVIDENCE BASES (subset-minimal sets of absent
evidence that would close the gap — hitting sets over the unmet atoms). MANDATORY
requirements must be reserved BEFORE any optional/budget-driven selection so a
token budget can never evict a safety-critical claim. Selection is robust
(worst-case over the plausibility set) and submodular-greedy under a budget; VOI
retrieval stops when marginal value is non-positive but never stops while a
mandatory atom is unmet. Anytime-valid monitoring (e-process) and conformal
prediction with an explicit distribution-shift guard produce diagnostics that
FAIL CLOSED — a disabled guarantee is surfaced, never silently assumed.

Reference kernel only; standard library only; opens no external effect.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations

from .canon import hash_obj
from .model import (Finding, P0, P1, P2, closes_critical)


# --- requirement hypergraph --------------------------------------------------
def requirement(*, req_id: str, description: str, atoms: list, critical: bool,
                mandatory: bool = False, min_independent: int = 1) -> dict:
    """A requirement is a hyperedge over ATOMS. Each atom is a predicate that some
    claim must discharge. ``min_independent`` demands corroboration from that many
    INDEPENDENT (non common-mode) sources before the atom counts as supported."""
    r = {"req_id": req_id, "description": description,
         "atoms": sorted(atoms), "critical": bool(critical),
         "mandatory": bool(mandatory),
         "min_independent": max(1, int(min_independent))}
    r["requirement_hash"] = hash_obj({k: r[k] for k in r
                                      if k != "description"})
    return r


def _atom_support(atom: str, claims: list) -> list:
    """Claims that SUPPORTED_ONLY-discharge ``atom`` (critical satisfaction)."""
    return [c for c in claims
            if atom in c.get("discharges", [])
            and closes_critical(c.get("support_state", "NEITHER"))]


def _atom_refute(atom: str, claims: list) -> list:
    return [c for c in claims
            if atom in c.get("discharges", [])
            and c.get("support_state") in ("REFUTED_ONLY", "BOTH")]


def _independent_producers(claims: list, evidence_by_id: dict) -> set:
    """Distinct producing origins behind a set of claims (common-mode collapses
    to one). Mirrors evidence.independence_class quotient."""
    producers = set()
    for c in claims:
        for eid in c.get("evidence_refs", []):
            ev = evidence_by_id.get(eid, {})
            producers.add(ev.get("provider") or ev.get("origin")
                          or ev.get("source_id") or eid)
    return producers


def _min_bases(candidates_per_atom: dict, atoms: list) -> list:
    """Subset-minimal claim-id sets that cover every atom (an antichain of
    transversals). Deterministic; bounded by the reference-kernel atom count."""
    if any(not candidates_per_atom.get(a) for a in atoms):
        return []                                   # some atom uncoverable
    # transversal search over small atom sets (reference kernel scale)
    options = [sorted({c["claim_id"] for c in candidates_per_atom[a]})
               for a in atoms]
    covers: set = set()
    frontier = [frozenset()]
    for opt in options:
        nxt = []
        for partial in frontier:
            for cid in opt:
                nxt.append(partial | {cid})
        frontier = nxt
    for combo in frontier:
        covers.add(frozenset(combo))
    minimal = []
    for cov in sorted(covers, key=lambda s: (len(s), sorted(s))):
        if not any(m < cov for m in minimal):
            minimal.append(cov)
    return [sorted(m) for m in minimal]


def evaluate_requirement(req: dict, claims: list, *,
                         evidence_by_id: dict = None) -> dict:
    """Compute support/refutation/missing bases and the satisfaction verdict.

    A requirement is SATISFIED iff every atom has a support basis meeting the
    independence floor and no atom is left in a purely-refuted or contradicted
    state. Missing-evidence bases are the atoms that remain unmet."""
    evidence_by_id = evidence_by_id or {}
    atoms = req["atoms"]
    support_c = {a: _atom_support(a, claims) for a in atoms}
    refute_c = {a: _atom_refute(a, claims) for a in atoms}

    unmet = []
    common_mode_short = []
    for a in atoms:
        prods = _independent_producers(support_c[a], evidence_by_id)
        if not support_c[a]:
            unmet.append(a)
        elif len(prods) < req["min_independent"]:
            common_mode_short.append(a)

    refuted_atoms = sorted(a for a in atoms if refute_c[a])
    support_bases = _min_bases(support_c, atoms) if not unmet else []
    refutation_bases = _min_bases(
        {a: refute_c[a] for a in atoms if refute_c[a]},
        sorted(a for a in atoms if refute_c[a])) if refuted_atoms else []
    missing_bases = [sorted(unmet)] if unmet else []

    satisfied = (not unmet and not common_mode_short
                 and not refuted_atoms)
    result = {
        "req_id": req["req_id"], "critical": req["critical"],
        "mandatory": req["mandatory"], "satisfied": bool(satisfied),
        "unmet_atoms": sorted(unmet),
        "common_mode_short_atoms": sorted(common_mode_short),
        "refuted_atoms": refuted_atoms,
        "minimal_support_bases": support_bases,
        "minimal_refutation_bases": refutation_bases,
        "missing_evidence_bases": missing_bases,
    }
    result["evaluation_hash"] = hash_obj(result)
    return result


def requirement_findings(evaluations: list) -> list[Finding]:
    out: list[Finding] = []
    for ev in evaluations:
        sev = P0 if ev["critical"] else P1
        if ev["mandatory"] and not ev["satisfied"]:
            out.append(Finding("MANDATORY_REQUIREMENT_MISSING", P0, ev["req_id"],
                               "mandatory requirement not satisfied "
                               f"(unmet atoms: {ev['unmet_atoms']})",
                               {"missing": ev["missing_evidence_bases"]}))
            continue
        if ev["unmet_atoms"] and ev["critical"]:
            out.append(Finding("MINIMAL_SUPPORT_MISSING", sev, ev["req_id"],
                               "no minimal support basis for critical "
                               f"requirement (unmet: {ev['unmet_atoms']})",
                               {"missing": ev["missing_evidence_bases"]}))
        if ev["common_mode_short_atoms"]:
            out.append(Finding("COMMON_MODE_SUPPORT_INSUFFICIENT", sev,
                               ev["req_id"],
                               "support fails independence floor (common-mode "
                               f"sources): {ev['common_mode_short_atoms']}", {}))
    return out


# --- mandatory reservation ---------------------------------------------------
def reserve_mandatory(evaluations: list, claims_by_id: dict, *,
                      token_of) -> dict:
    """Reserve every claim in a mandatory requirement's minimal support basis
    BEFORE budgeted selection (Innovation 4). A mandatory atom can never be
    evicted by a token budget; if it cannot be reserved the build fails closed."""
    reserved: set = set()
    unreservable = []
    for ev in evaluations:
        if not ev["mandatory"]:
            continue
        if not ev["minimal_support_bases"]:
            unreservable.append(ev["req_id"])
            continue
        basis = min(ev["minimal_support_bases"],
                    key=lambda b: (sum(token_of(claims_by_id[c]) for c in b),
                                   sorted(b)))
        reserved |= set(basis)
    cost = sum(token_of(claims_by_id[c]) for c in reserved
               if c in claims_by_id)
    return {"reserved_claim_ids": sorted(reserved),
            "reserved_tokens": cost,
            "unreservable_requirements": sorted(unreservable),
            "reservation_hash": hash_obj({"r": sorted(reserved),
                                          "u": sorted(unreservable)})}


# --- robust submodular selection under budget --------------------------------
def _coverage_value(selected_ids: set, claims_by_id: dict) -> Fraction:
    """Submodular coverage: value = number of DISTINCT atoms discharged
    SUPPORTED_ONLY (diminishing returns — a duplicate atom adds nothing)."""
    atoms: set = set()
    for cid in selected_ids:
        c = claims_by_id.get(cid, {})
        if closes_critical(c.get("support_state", "NEITHER")):
            atoms |= set(c.get("discharges", []))
    return Fraction(len(atoms))


def _robust_value(selected_ids: set, claims_by_id: dict,
                  scenarios: list) -> Fraction:
    """Worst-case (robust) coverage over a plausibility set of scenarios; each
    scenario may drop some claims (source could be stale/revoked)."""
    if not scenarios:
        return _coverage_value(selected_ids, claims_by_id)
    worst = None
    for drop in scenarios:
        surviving = selected_ids - set(drop)
        v = _coverage_value(surviving, claims_by_id)
        worst = v if worst is None else min(worst, v)
    return worst


def robust_select(candidate_ids: list, claims_by_id: dict, *, budget: int,
                  token_of, reserved: set = None,
                  scenarios: list = None) -> dict:
    """Greedy robust-submodular selection under a hard token budget. Reserved
    (mandatory) claims are pre-committed and never dropped. Greedy maximizes the
    robust marginal value per token; ties broken deterministically by id."""
    reserved = set(reserved or [])
    scenarios = scenarios or []
    selected = set(reserved)
    spent = sum(token_of(claims_by_id[c]) for c in selected
                if c in claims_by_id)
    if spent > budget:
        return {"selected_ids": sorted(selected), "spent_tokens": spent,
                "budget": budget, "budget_ok": False,
                "value": str(_robust_value(selected, claims_by_id, scenarios)),
                "selection_hash": hash_obj({"s": sorted(selected),
                                            "ok": False})}
    pool = [c for c in candidate_ids if c not in selected]
    while True:
        best = None
        base_v = _robust_value(selected, claims_by_id, scenarios)
        for cid in sorted(pool):
            cost = token_of(claims_by_id.get(cid, {"tokens": 1}))
            if cost <= 0 or spent + cost > budget:
                continue
            gain = _robust_value(selected | {cid}, claims_by_id,
                                 scenarios) - base_v
            if gain <= 0:
                continue
            ratio = Fraction(gain, cost)
            key = (ratio, -cost, cid)
            if best is None or key > best[0]:
                best = (key, cid, cost)
        if best is None:
            break
        selected.add(best[1])
        spent += best[2]
        pool.remove(best[1])
    return {"selected_ids": sorted(selected), "spent_tokens": spent,
            "budget": budget, "budget_ok": spent <= budget,
            "value": str(_robust_value(selected, claims_by_id, scenarios)),
            "selection_hash": hash_obj({"s": sorted(selected),
                                        "sp": spent, "b": budget})}


def selection_findings(selection: dict, reserved: dict) -> list[Finding]:
    out: list[Finding] = []
    if reserved.get("unreservable_requirements"):
        out.append(Finding("MANDATORY_REQUIREMENT_MISSING", P0, "reservation",
                           "mandatory requirement has no reservable support "
                           f"basis: {reserved['unreservable_requirements']}", {}))
    if not selection.get("budget_ok"):
        out.append(Finding("CONTEXT_BUDGET_INSUFFICIENT", P0, "selection",
                           "mandatory reservation exceeds the token budget "
                           "(cannot drop safety-critical context)",
                           {"spent": selection.get("spent_tokens"),
                            "budget": selection.get("budget")}))
    if not set(reserved.get("reserved_claim_ids", [])).issubset(
            set(selection.get("selected_ids", []))):
        out.append(Finding("MANDATORY_RETRIEVAL_STOPPED", P0, "selection",
                           "a reserved mandatory claim was evicted by "
                           "budgeted selection (forbidden)", {}))
    return out


# --- value-of-information retrieval ------------------------------------------
def voi_retrieval(steps: list, *, mandatory_unmet_at) -> dict:
    """Anytime retrieval stops when marginal VALUE is non-positive, BUT never
    stops while a mandatory atom is still unmet (Innovation 5, D-B6-052).

    ``steps``: ordered list of {"marginal_value": Fraction|number,
    "cost": number, "atoms_after": [...]}; ``mandatory_unmet_at(i)`` returns the
    mandatory atoms still unmet after step i."""
    taken = []
    stop_reason = "EXHAUSTED"
    for i, s in enumerate(steps):
        mv = Fraction(s["marginal_value"]) if not isinstance(
            s["marginal_value"], Fraction) else s["marginal_value"]
        unmet = mandatory_unmet_at(i)
        if mv <= 0 and not unmet:
            stop_reason = "MARGINAL_VALUE_NONPOSITIVE"
            break
        if mv <= 0 and unmet:
            taken.append(i)                 # forced to continue for mandatory
            stop_reason = "MANDATORY_FORCED_CONTINUE"
            continue
        taken.append(i)
    final_unmet = mandatory_unmet_at(len(taken) - 1 if taken else -1)
    return {"steps_taken": taken, "stop_reason": stop_reason,
            "mandatory_unmet_at_stop": sorted(final_unmet),
            "voi_hash": hash_obj({"t": taken, "r": stop_reason})}


def voi_findings(voi: dict) -> list[Finding]:
    out: list[Finding] = []
    if voi["mandatory_unmet_at_stop"]:
        out.append(Finding("MANDATORY_RETRIEVAL_STOPPED", P0, "voi",
                           "retrieval stopped with mandatory atoms still unmet: "
                           f"{voi['mandatory_unmet_at_stop']}", {}))
    return out


# --- anytime-valid monitoring (e-process) ------------------------------------
def eprocess_wealth(bets: list) -> Fraction:
    """Test-martingale wealth under H0. Each bet is a nonnegative multiplier with
    E[bet|H0]=1; the product is the e-value. Optional stopping is VALID — you may
    peek at every step without inflating error (Innovation 9)."""
    wealth = Fraction(1)
    for b in bets:
        wealth *= Fraction(b) if not isinstance(b, Fraction) else b
    return wealth


def anytime_decision(bets: list, *, alpha: Fraction = Fraction(1, 20)) -> dict:
    """Reject H0 the first time wealth >= 1/alpha; the decision is valid under
    continuous monitoring (no optional-stopping penalty)."""
    wealth = Fraction(1)
    threshold = Fraction(1) / alpha
    reject_at = None
    for i, b in enumerate(bets):
        wealth *= Fraction(b) if not isinstance(b, Fraction) else b
        if reject_at is None and wealth >= threshold:
            reject_at = i
    return {"final_wealth": str(wealth), "threshold": str(threshold),
            "reject_h0": reject_at is not None, "reject_at": reject_at,
            "anytime_valid": True,
            "decision_hash": hash_obj({"w": str(wealth), "r": reject_at})}


# --- conformal prediction with distribution-shift guard ----------------------
def conformal_interval(calibration_scores: list, new_score, *,
                       alpha: Fraction = Fraction(1, 10),
                       shift_detected: bool = False) -> dict:
    """Split-conformal p-value + coverage flag with an explicit SHIFT GUARD. If a
    distribution shift is detected the exchangeability assumption is broken, so
    the guarantee is DISABLED (surfaced, never silently assumed — Innovation 10,
    D-B6-138/139)."""
    n = len(calibration_scores)
    if n == 0:
        return {"covered": None, "p_value": None, "guarantee_active": False,
                "reason": "NO_CALIBRATION",
                "conformal_hash": hash_obj({"n": 0})}
    rank = sum(1 for s in calibration_scores if s >= new_score) + 1
    p_value = Fraction(rank, n + 1)
    guarantee_active = not shift_detected
    covered = None if shift_detected else bool(p_value > alpha)
    return {"covered": covered, "p_value": str(p_value),
            "guarantee_active": guarantee_active,
            "shift_detected": bool(shift_detected),
            "reason": "SHIFT_GUARD_TRIPPED" if shift_detected else "OK",
            "conformal_hash": hash_obj({"p": str(p_value),
                                        "g": guarantee_active})}


def statistics_findings(conformal: dict) -> list[Finding]:
    out: list[Finding] = []
    if conformal.get("shift_detected"):
        out.append(Finding("DISTRIBUTION_SHIFT_DETECTED", P1, "conformal",
                           "distribution shift breaks exchangeability: conformal "
                           "guarantee disabled (fail-closed, not assumed)", {}))
    if conformal.get("guarantee_active") is False and not conformal.get(
            "shift_detected"):
        out.append(Finding("CONFORMAL_GUARANTEE_DISABLED", P2, "conformal",
                           "conformal guarantee inactive (no calibration)", {}))
    return out
