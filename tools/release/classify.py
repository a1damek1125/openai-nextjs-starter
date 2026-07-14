"""Change classification engine (SP0009 FUNCTION A, §11.1, AC-0009-023..033).

Classifies a change (a set of changed paths + optional deltas) into multi-label
change classes and derives the release risk vector. The rules are deterministic
path/AST-level triggers grounded in this repository's real layout (finalis/
product code, tools/ governance, docs/, tests/, migrations in
finalis/portal/db.py, auth/RBAC in finalis/portal/app.py + finalis/dashboard.py).

The constitutional rule AC-0009-033: a SMALL diff is never automatically low
risk — risk derives from WHICH surfaces changed, not how many lines. A one-line
change to an authority check classifies AUTHORITY_CHANGE with hard risk.
"""
from __future__ import annotations

from .model import (CHANGE_CLASSES, RISK_DIMS, HARD_RISK_DIMS, Finding, P1,
                    P2)

# deterministic path-trigger table: (predicate, classes)
_AUTH_HINTS = ("auth", "rbac", "permission", "role", "authority", "approval")
_SAFETY_HINTS = ("safety", "guardrail", "containment", "hazard")
_AI_HINTS = ("ai_employee", "prompt", "model", "provider", "tool_", "skill")


def classify_paths(paths: list) -> dict:
    """Multi-label classification of changed paths (AC-0009-024)."""
    classes: set = set()
    triggers: dict = {}

    def mark(cls: str, path: str) -> None:
        classes.add(cls)
        triggers.setdefault(cls, []).append(path)

    for p in sorted(set(paths)):
        low = p.lower()
        if p.startswith("finalis/portal/db.py"):
            mark("MIGRATION_CHANGE", p)
        if p.startswith("finalis/"):
            mark("SEMANTIC_CHANGE", p)
            if any(h in low for h in _AUTH_HINTS):
                mark("AUTHORITY_CHANGE", p)
            if any(h in low for h in _SAFETY_HINTS):
                mark("SAFETY_CHANGE", p)
            if any(h in low for h in _AI_HINTS):
                mark("AI_CLOSURE_CHANGE", p)
            if p.startswith("finalis/portal/app.py") or "contract" in low \
                    or "schema" in low or "event" in low:
                mark("CONTRACT_CHANGE", p)
        if p.startswith(".github/") or "workflow" in low and low.endswith(
                (".yml", ".yaml")):
            mark("CI_WORKFLOW_CHANGE", p)
        if p in ("pyproject.toml", "requirements.txt", "package-lock.json",
                 "uv.lock", "poetry.lock") or low.endswith(".lock"):
            mark("DEPENDENCY_CHANGE", p)
        if p.startswith("tests/"):
            mark("TEST_CHANGE", p)
        if p.startswith("docs/"):
            mark("DOCS_CHANGE", p)
        if p.startswith("tools/"):
            mark("GOVERNANCE_TOOLING_CHANGE", p)
    if not classes:
        classes.add("UNKNOWN_CHANGE")
    for c in classes:
        assert c in CHANGE_CLASSES, c
    return {"classes": sorted(classes), "triggers": triggers,
            "path_count": len(set(paths))}


def risk_vector(classification: dict) -> dict:
    """Derive the ten-dimension risk vector (D-0009-05). Dimensions are set
    individually; nothing is averaged; unknown stays UNKNOWN. Small diffs get
    no discount (AC-0009-033): the vector depends only on classes."""
    classes = set(classification.get("classes") or [])
    vec = {d: "UNKNOWN" for d in RISK_DIMS}
    vec["epistemic_unknown"] = "ELEVATED" if "UNKNOWN_CHANGE" in classes \
        else "LOW"
    if "AUTHORITY_CHANGE" in classes:
        vec["authority"] = "HIGH"
        vec["tenant"] = "ELEVATED"
    if "SAFETY_CHANGE" in classes:
        vec["safety"] = "HIGH"
    if "MIGRATION_CHANGE" in classes:
        vec["migration"] = "HIGH"
        vec["irreversibility"] = "HIGH"   # forward-only migrations
    if "CONTRACT_CHANGE" in classes:
        vec["compatibility"] = "ELEVATED"
    if "DEPENDENCY_CHANGE" in classes or "CI_WORKFLOW_CHANGE" in classes:
        vec["supply_chain"] = "HIGH"
    if "AI_CLOSURE_CHANGE" in classes:
        vec["externality"] = "ELEVATED"
    if classes <= {"DOCS_CHANGE", "TEST_CHANGE", "GOVERNANCE_TOOLING_CHANGE"}:
        # additive governance/docs/tests: product dimensions are LOW, never
        # silently UNKNOWN
        for d in ("tenant", "authority", "safety", "privacy", "compatibility",
                  "migration", "externality", "irreversibility"):
            vec[d] = "LOW"
        if "GOVERNANCE_TOOLING_CHANGE" not in classes:
            vec["supply_chain"] = "LOW"
        else:
            vec["supply_chain"] = "LOW"
    vec["hard_flags"] = sorted(d for d in HARD_RISK_DIMS
                               if vec.get(d) == "HIGH")
    return vec


def classification_findings(classification: dict, vec: dict) -> list:
    out = []
    if "UNKNOWN_CHANGE" in (classification.get("classes") or []):
        out.append(Finding(
            "CHANGE_CLASSIFICATION_UNKNOWN", P1, "classification",
            "change could not be classified; unknown change classes block "
            "qualification until resolved", {}))
    if vec.get("hard_flags"):
        out.append(Finding(
            "CHANGE_CLASSIFIED", P2, "classification",
            f"hard risk flags raised: {vec['hard_flags']} — a small diff does "
            "not reduce this risk (AC-0009-033)",
            {"hard_flags": vec["hard_flags"]}))
    return out
