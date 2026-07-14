"""Test inventory, coverage graphs and risk-adaptive selection (SP0009
FUNCTION D, §11.6/11.7, D-0009-15/16/17, AC-0009-081..092).

Selection order is constitutional: (1) mandatory tests, (2) directly impacted
contract tests, (3) impacted invariant tests, (4) incident regressions — all
BEFORE any cost optimization. The optimizer then chooses among the remaining
candidates: an exact branch-and-bound set cover under explicit bounds, else a
deterministic weighted-greedy fallback that can only ADD coverage, never remove
mandatory items. Every selection ships with a Test Selection Proof mapping each
impacted obligation to at least one selected test (AC-0009-089).
"""
from __future__ import annotations

import re
from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0

EXACT_BOUND_TESTS = 20        # branch-and-bound only under these bounds
EXACT_BOUND_OBLIGATIONS = 20


def test_inventory(root: Path) -> list:
    """Real Test Inventory Adapter: every test file under tests/ with its
    deterministic id and advisory cost proxy (file size)."""
    out = []
    for p in sorted((root / "tests").glob("test_*.py")):
        out.append({"test_id": p.name,
                    "path": str(p.relative_to(root)),
                    "cost": max(1, p.stat().st_size // 1024)})
    return out


def coverage_graph(inventory: list) -> dict:
    """Deterministic test-to-concern mapping from naming conventions: this
    repository encodes its concern in the test filename (contract, invariant
    kernel, incident/red-team regressions)."""
    edges = {"contract": {}, "invariant": {}, "incident": {}}
    for t in inventory:
        tid = t["test_id"]
        stem = tid[len("test_"):-3]
        if re.search(r"(redteam|mutation|regression)", stem):
            edges["incident"].setdefault(stem, []).append(tid)
        if re.search(r"(contract|compat|inventory|api|schema)", stem):
            edges["contract"].setdefault(stem, []).append(tid)
        edges["invariant"].setdefault(stem.split("_")[0], []).append(tid)
    return edges


def mandatory_set(inventory: list, impacted_stems: list) -> list:
    """Constitutionally mandatory tests (FUNCTION D steps 1-4): incident
    regressions always; every test whose stem matches an impacted area."""
    mand = set()
    for t in inventory:
        stem = t["test_id"][len("test_"):-3]
        if re.search(r"(redteam|mutation)", stem):
            mand.add(t["test_id"])
        for s in impacted_stems:
            if s and s in stem:
                mand.add(t["test_id"])
    return sorted(mand)


# --- exact bounded set cover (§11.6) ----------------------------------------------
def exact_set_cover(tests: list, obligations: list, covers: dict,
                    *, required: dict | None = None):
    """Branch-and-bound minimum-cost cover. tests: [{test_id,cost}],
    obligations: [id], covers: {test_id: set(obligation ids)}. Returns
    (selection, cost) or None when bounds are exceeded (caller falls back)."""
    if len(tests) > EXACT_BOUND_TESTS or len(obligations) > \
            EXACT_BOUND_OBLIGATIONS:
        return None
    required = required or {u: 1 for u in obligations}
    tests = sorted(tests, key=lambda t: (t["cost"], t["test_id"]))
    best = {"cost": None, "sel": None}

    def feasible(uncovered):
        # every uncovered obligation must be coverable by SOME remaining test
        return all(any(u in covers.get(t["test_id"], ()) for t in tests)
                   for u in uncovered)

    def bb(idx, chosen, cost, counts):
        uncovered = [u for u in obligations
                     if counts.get(u, 0) < required.get(u, 1)]
        if not uncovered:
            if best["cost"] is None or cost < best["cost"]:
                best["cost"], best["sel"] = cost, sorted(chosen)
            return
        if idx >= len(tests):
            return
        if best["cost"] is not None and cost >= best["cost"]:
            return
        t = tests[idx]
        gain = covers.get(t["test_id"], set()) & set(uncovered)
        if gain:
            nc = dict(counts)
            for u in gain:
                nc[u] = nc.get(u, 0) + 1
            bb(idx + 1, chosen + [t["test_id"]], cost + t["cost"], nc)
        bb(idx + 1, chosen, cost, counts)

    if not feasible(obligations):
        return None
    bb(0, [], 0, {})
    if best["sel"] is None:
        return None
    return best["sel"], best["cost"]


# --- deterministic greedy fallback (§11.7) -----------------------------------------
def greedy_cover(tests: list, obligations: list, covers: dict,
                 *, mandatory: list | None = None) -> list:
    """Weighted greedy: maximize new coverage / cost; ties break by critical
    coverage, then deterministic test id. Mandatory tests are pre-selected and
    can never be dropped (D-0009-15)."""
    selected = sorted(set(mandatory or []))
    covered: set = set()
    for tid in selected:
        covered |= set(covers.get(tid, ()))
    remaining = [t for t in tests if t["test_id"] not in selected]
    while True:
        uncovered = [u for u in obligations if u not in covered]
        if not uncovered:
            break
        scored = []
        for t in remaining:
            gain = len(set(covers.get(t["test_id"], ())) & set(uncovered))
            if gain:
                scored.append((-gain / t["cost"], t["test_id"]))
        if not scored:
            break   # coverage gap surfaces via selection_proof, never silently
        scored.sort()
        pick = scored[0][1]
        selected.append(pick)
        covered |= set(covers.get(pick, ()))
        remaining = [t for t in remaining if t["test_id"] != pick]
    return sorted(selected)


def selection_proof(selection: list, obligations: list, covers: dict) -> dict:
    """Test Selection Proof (AC-0009-089): every impacted obligation maps to at
    least one selected test — or the gap is an explicit P0 finding."""
    mapping = {}
    gaps = []
    for u in obligations:
        hit = sorted(t for t in selection if u in covers.get(t, ()))
        if hit:
            mapping[u] = hit
        else:
            gaps.append(u)
    return {"mapping": mapping, "gaps": sorted(gaps),
            "proof_hash": hash_obj({"sel": sorted(selection),
                                    "map": mapping, "gaps": sorted(gaps)})}


def proof_findings(proof: dict) -> list:
    return [Finding("TEST_COVERAGE_GAP", P0, u,
                    "impacted obligation has NO selected covering test; "
                    "optimization may not remove mandatory coverage "
                    "(D-0009-15)", {})
            for u in proof.get("gaps", [])]
