"""Flake intelligence: environment-conditioned classification, systemic
co-occurrence clusters and governed quarantine (SP0009 FUNCTION F, §11.8/11.9,
§12.5/12.6, D-0009-19/20/21/22, AC-0009-100..115).

A single rerun-pass never proves a flake (D-0009-19). Classification requires
repeated controlled evidence, conditioned on ONE environment fingerprint at a
time (incompatible environments are never pooled, §12.5). Systemic analysis
builds a co-failure graph (Jaccard association with minimum support) — clusters
suggest a shared root cause but co-occurrence is association evidence, NEVER
causal proof (§12.6). Quarantine is a governed contract with owner + expiry;
a critical (tenant/authority/safety/proof) test can be quarantined only with an
equivalent-or-stronger compensating control (D-0009-22) — quarantine is never
skip, never deletion.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import FLAKE_CLASSES, Finding, P0, P1


def environment_fingerprint(*, os_id: str, runtime: str, browser=None,
                            dependency_lock_hash: str = "", shard=None) -> str:
    return "EF-" + hash_obj({"os": os_id, "runtime": runtime,
                             "browser": browser,
                             "deps": dependency_lock_hash,
                             "shard": shard})[:20]


def observe(registry: list, *, test_id: str, env_fingerprint: str,
            result: str, failure_signature=None) -> list:
    """Append one controlled observation to the flake observation registry."""
    entry = {"test_id": test_id, "environment_fingerprint": env_fingerprint,
             "result": result, "failure_signature": failure_signature,
             "observation_id": "FO-" + hash_obj(
                 {"t": test_id, "e": env_fingerprint, "r": result,
                  "n": len(registry)})[:20]}
    return registry + [entry]


def posterior(registry: list, *, test_id: str, env_fingerprint: str) -> dict:
    """Advisory Beta(1+f, 1+p) failure-probability posterior for ONE test in
    ONE environment (§12.5). Never pooled across environments; always labeled
    advisory with its sample count."""
    obs = [o for o in registry if o["test_id"] == test_id
           and o["environment_fingerprint"] == env_fingerprint]
    f = sum(1 for o in obs if o["result"] in ("FAIL", "TIMEOUT"))
    p = sum(1 for o in obs if o["result"] == "PASS")
    a, b = 1 + f, 1 + p
    mean = a / (a + b)
    return {"test_id": test_id, "environment_fingerprint": env_fingerprint,
            "alpha": a, "beta": b, "posterior_mean": round(mean, 6),
            "samples": f + p, "failures": f, "passes": p,
            "advisory_only": True,
            "note": "Beta(1+f,1+p) conditioned on one environment; not a "
                    "product-correctness statement (D-0009-21)"}


def classify(registry: list, *, test_id: str) -> dict:
    """Classify inconsistency using controlled evidence across environments.

    - fails AND passes within the SAME environment repeatedly => candidate
      TEST_FLAKE_CONFIRMED (needs >=2 of each, D-0009-19);
    - fails in one environment but consistently passes in others =>
      ENVIRONMENT_INSTABILITY;
    - a single rerun-pass with no other evidence => UNKNOWN (never confirmed);
    - no failure at all => NOT_REPRODUCED.
    """
    obs = [o for o in registry if o["test_id"] == test_id]
    if not obs:
        return {"test_id": test_id, "classification": "UNKNOWN",
                "reason": "no observations"}
    by_env: dict = {}
    for o in obs:
        by_env.setdefault(o["environment_fingerprint"], []).append(o["result"])
    mixed_envs = [e for e, rs in by_env.items()
                  if any(r in ("FAIL", "TIMEOUT") for r in rs)
                  and any(r == "PASS" for r in rs)]
    fail_only_envs = [e for e, rs in by_env.items()
                      if all(r in ("FAIL", "TIMEOUT") for r in rs)]
    any_fail = any(r in ("FAIL", "TIMEOUT")
                   for rs in by_env.values() for r in rs)
    if not any_fail:
        cls, reason = "NOT_REPRODUCED", "no failure observed"
    elif mixed_envs:
        env = mixed_envs[0]
        rs = by_env[env]
        f = sum(1 for r in rs if r in ("FAIL", "TIMEOUT"))
        p = sum(1 for r in rs if r == "PASS")
        if f >= 2 and p >= 2:
            cls, reason = "TEST_FLAKE_CONFIRMED", (
                f"{f} failures and {p} passes in the same environment {env}")
        else:
            cls, reason = "UNKNOWN", (
                "inconsistent within one environment but with insufficient "
                f"repetitions (f={f}, p={p}); a rerun alone cannot prove a "
                "flake (D-0009-19)")
    elif fail_only_envs and len(by_env) > len(fail_only_envs):
        cls, reason = "ENVIRONMENT_INSTABILITY", (
            f"fails consistently in {sorted(fail_only_envs)} but passes in "
            "other environments")
    else:
        cls, reason = "PRODUCT_NONDETERMINISM", (
            "fails everywhere it runs with no passing environment — this is "
            "candidate product-level nondeterminism, not a test flake")
    assert cls in FLAKE_CLASSES
    return {"test_id": test_id, "classification": cls, "reason": reason,
            "environments": {e: rs for e, rs in sorted(by_env.items())}}


# --- systemic co-occurrence (§11.8, §12.6, D-0009-20) ------------------------------
MIN_SUPPORT = 2          # a pair must co-fail at least this many runs
MIN_JACCARD = 0.6


def co_failure_graph(run_failures: list) -> dict:
    """run_failures: list of sets/lists of test_ids that failed together in one
    run. Returns weighted edges {(<a>,<b>): jaccard} for pairs meeting minimum
    support — association evidence only, never causality."""
    from itertools import combinations
    fail_runs: dict = {}
    for i, failed in enumerate(run_failures):
        for t in failed:
            fail_runs.setdefault(t, set()).add(i)
    edges = {}
    for a, b in combinations(sorted(fail_runs), 2):
        inter = fail_runs[a] & fail_runs[b]
        if len(inter) < MIN_SUPPORT:
            continue
        union = fail_runs[a] | fail_runs[b]
        j = len(inter) / len(union)
        if j >= MIN_JACCARD:
            edges[(a, b)] = round(j, 4)
    return edges


def clusters(edges: dict) -> list:
    """Connected components of the co-failure graph = flake cluster candidates
    (D-0009-20). Each cluster carries the explicit non-causality caveat."""
    adj: dict = {}
    for (a, b) in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen: set = set()
    out = []
    for node in sorted(adj):
        if node in seen:
            continue
        comp, stack = set(), [node]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(adj.get(n, ()) - comp)
        seen |= comp
        out.append({
            "cluster_id": "FC-" + hash_obj(sorted(comp))[:20],
            "test_refs": sorted(comp),
            "co_occurrence_measure": {f"{a}|{b}": w
                                      for (a, b), w in sorted(edges.items())
                                      if a in comp and b in comp},
            "classification": "UNKNOWN",
            "note": "co-occurrence is association evidence, not causal proof "
                    "(§12.6); investigate shared fixtures/environment",
        })
    return out


# --- governed quarantine (D-0009-22, AC-0009-112..114) ------------------------------
CRITICAL_TEST_MARKERS = ("tenant", "authority", "rbac", "safety", "proof",
                         "redteam", "mutation")


def quarantine(*, test_id: str, owner: str, expires_at: str,
               equivalent_control=None) -> dict:
    q = {"test_id": test_id, "owner": owner, "expires_at": expires_at,
         "equivalent_control": equivalent_control, "status": "PROPOSED"}
    q["quarantine_id"] = "QT-" + hash_obj(q)[:20]
    return q


def validate_quarantine(q: dict) -> list[Finding]:
    out: list[Finding] = []
    subject = str(q.get("quarantine_id") or "-")
    if not q.get("owner"):
        out.append(Finding("FLAKE_SUSPECTED", P1, subject,
                           "quarantine requires an owner (AC-0009-112)", {}))
    if not q.get("expires_at"):
        out.append(Finding("FLAKE_SUSPECTED", P1, subject,
                           "quarantine requires an expiry (AC-0009-113)", {}))
    tid = str(q.get("test_id") or "").lower()
    if any(m in tid for m in CRITICAL_TEST_MARKERS):
        ctrl = q.get("equivalent_control")
        if not (isinstance(ctrl, dict) and ctrl.get("verified") is True):
            out.append(Finding(
                "CRITICAL_TEST_QUARANTINE_BLOCKED", P0, subject,
                "critical (tenant/authority/safety/proof) test cannot be "
                "quarantined without a VERIFIED equivalent-or-stronger "
                "control (D-0009-22, AC-0009-114)", {"test_id": tid}))
    return out
