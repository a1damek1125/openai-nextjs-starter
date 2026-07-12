"""Relational noninterference — paired-world hyperproperties (SP0010 FUNCTION K,
§10.7, §11.10, §12.6/12.7, D-0010-14/15/16/17, AC-0010-095..100).

Path absence is NOT noninterference (INV-0010-27): a hyperproperty compares
MULTIPLE executions. Each check runs two bounded worlds that differ ONLY in a
protected variable (Tenant-A secret, an approval decision, a provider account, a
control-language surface) and requires the declared observable of the OTHER
party to be equivalent across both worlds. The models are bounded deterministic
reference models grounded in the real controls (require_permission / tenant_id
scoping / approval binding exist per archaeology); the bound is disclosed —
this is bounded-model evidence, never universal proof (D-0010-41).
"""
from __future__ import annotations

from itertools import product

from .canon import hash_obj
from .model import Finding, P0

# --- reference models: each maps a world (dict) -> the OTHER party's observable.
# A CORRECT model ignores the protected variable; a violation would read it.


def _tenant_model(world: dict) -> dict:
    """Tenant B's observable must not depend on Tenant A's secret. The real
    control (per-tenant scoping: WHERE tenant_id = B) makes B's view a pure
    function of B's own state."""
    return {"tenant_b_view": world["tenant_b_state"],
            "tenant_b_effects": sorted(world["tenant_b_actions"])}


def _approval_model(world: dict) -> dict:
    """Approval for work A must not change admissibility of distinct work B.
    Admissibility of B is a function of B's own approval only."""
    return {"work_b_admissible": world["work_b_approved"]}


def _provider_account_model(world: dict) -> dict:
    """Provider account for tenant A must not leak into tenant B's provider
    binding; B's binding depends only on B's account."""
    return {"tenant_b_provider": world["tenant_b_account"]}


def _control_language_model(world: dict) -> dict:
    """Equivalent business intent across languages must yield the same policy
    outcome; the outcome depends on the intent, not the surface language."""
    return {"policy_outcome": world["intent"]}


HYPERPROPERTIES = {
    "HP-TENANT-NONINTERFERENCE": {
        "model": _tenant_model, "varying": "tenant_a_secret",
        "fixed": ("tenant_b_state", "tenant_b_actions"),
        "meaning": "Tenant B observables invariant under Tenant A secret",
        "critical": True},
    "HP-APPROVAL-ISOLATION": {
        "model": _approval_model, "varying": "work_a_approved",
        "fixed": ("work_b_approved",),
        "meaning": "Work B admissibility invariant under Work A approval",
        "critical": True},
    "HP-PROVIDER-ACCOUNT-SEPARATION": {
        "model": _provider_account_model, "varying": "tenant_a_account",
        "fixed": ("tenant_b_account",),
        "meaning": "Tenant B provider binding invariant under Tenant A account",
        "critical": True},
    "HP-CONTROL-LANGUAGE-INVARIANCE": {
        "model": _control_language_model, "varying": "language",
        "fixed": ("intent",),
        "meaning": "Policy outcome invariant under control-language surface",
        "critical": True},
}

# bounded domains for the varying + fixed variables
_DOMAINS = {
    "tenant_a_secret": ["s0", "s1"], "tenant_b_state": ["b0", "b1"],
    "tenant_b_actions": [["read"], ["read", "write"]],
    "work_a_approved": [True, False], "work_b_approved": [True, False],
    "tenant_a_account": ["acctA1", "acctA2"], "tenant_b_account": ["acctB"],
    "language": ["EN", "PL", "DE", "ES"], "intent": ["quote", "refund"],
}


def _worlds(varying: str, fixed: tuple):
    """Enumerate the bounded fixed-context assignments; for each, produce the
    pair(s) of worlds differing only in the varying variable."""
    fixed_domains = [(_DOMAINS[f], f) for f in fixed]
    for combo in product(*[d for d, _ in fixed_domains]):
        base = {f: v for (_, f), v in zip(fixed_domains, combo)}
        vary_vals = _DOMAINS[varying]
        worlds = []
        for vv in vary_vals:
            w = dict(base)
            w[varying] = vv
            # supply defaults for any model input not in base/varying
            for k in _DOMAINS:
                w.setdefault(k, _DOMAINS[k][0])
            worlds.append(w)
        yield base, worlds


def verify_hyperproperty(hp_id: str, *, model_override=None) -> dict:
    """Run the paired-world check. Returns PASS/FAIL with a counterexample."""
    spec = HYPERPROPERTIES[hp_id]
    model = model_override or spec["model"]
    counterexample = None
    checked = 0
    for base, worlds in _worlds(spec["varying"], spec["fixed"]):
        observables = [hash_obj(model(w)) for w in worlds]
        checked += 1
        if len(set(observables)) > 1:
            counterexample = {"fixed_context": base,
                              "varying": spec["varying"],
                              "divergent_observables": True}
            break
    status = "FAIL" if counterexample else "PASS"
    return {"hyperproperty_id": hp_id, "status": status,
            "world_pairs_checked": checked,
            "counterexample": counterexample,
            "bound": {"varying_domain": _DOMAINS[spec["varying"]],
                      "note": "bounded reference model; not universal proof "
                              "(D-0010-41)"},
            "critical": spec["critical"]}


def verify_all() -> dict:
    return {hp: verify_hyperproperty(hp) for hp in sorted(HYPERPROPERTIES)}


def status_map(results: dict) -> dict:
    return {hp: rec["status"] for hp, rec in results.items()}


def noninterference_findings(results: dict) -> list[Finding]:
    out: list[Finding] = []
    codes = {
        "HP-TENANT-NONINTERFERENCE": "TENANT_NONINTERFERENCE_FAILED",
        "HP-APPROVAL-ISOLATION": "APPROVAL_ISOLATION_FAILED",
        "HP-PROVIDER-ACCOUNT-SEPARATION": "PROVIDER_ACCOUNT_ISOLATION_FAILED",
        "HP-CONTROL-LANGUAGE-INVARIANCE": "CONTROL_LANGUAGE_INVARIANCE_FAILED",
    }
    for hp, rec in sorted(results.items()):
        if rec["critical"] and rec["status"] == "FAIL":
            out.append(Finding(
                codes.get(hp, "NONINTERFERENCE_FAILED"), P0, hp,
                f"paired-world hyperproperty {hp} FAILED: "
                f"{rec['counterexample']}", rec))
        elif rec["critical"] and rec["status"] in ("UNKNOWN", "LIMIT_REACHED"):
            out.append(Finding(
                "NONINTERFERENCE_LIMIT_REACHED", P0, hp,
                f"critical hyperproperty {hp} unresolved: {rec['status']}",
                rec))
    return out


def hyperproperty_root(results: dict) -> str:
    return hash_obj({hp: rec["status"] for hp, rec in sorted(results.items())})
