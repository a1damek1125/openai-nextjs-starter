"""Purpose/Scope Binding + Data Minimization + Hidden-Work Detector +
Least-Authority (SP0006 §9.9, D-0006-46/47/48, INV-0006-30).

Every data access and every executed action is BOUND to the work's declared
privacy purpose and allowed scope. Purpose is authorization, not convenience:
memory or "it was handy" can NEVER manufacture a new purpose (D-0006-46) — an
incompatible access is PURPOSE_BINDING_FAILURE (P0). Execution must match the
admitted plan (or an approved replan): any executed step with no admitted
counterpart is HIDDEN_WORK_DETECTED (P0), the anti-scope-creep invariant
(D-0006-47, INV-0006-30). Among otherwise-valid plans, the one requiring the
NARROWEST authority is preferred (least authority, D-0006-48); this is advisory
unless one plan deterministically dominates the others.

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, PURPOSE_BINDING_FAILURE,
                    HIDDEN_WORK_DETECTED)
from .canon import core_hash

_MEMORY_SOURCES = {"memory", "convenience", "cache", "recall"}


def _as_set(v) -> set:
    if isinstance(v, (list, set, tuple)):
        return {str(x) for x in v}
    if v is None:
        return set()
    return {str(v)}


def purpose_compatible(access: dict, work: dict) -> bool:
    """True iff the access is compatible with work['privacy_purpose'] (D-0006-46).
    Fail-closed: an access with no declared purpose is incompatible, and a
    memory/convenience source can never introduce a purpose the work lacks."""
    access = access or {}
    work = work or {}
    wp = work.get("privacy_purpose")
    ap = access.get("purpose")
    if wp is None or ap is None:
        return False
    # compatibility comes from the WORK ORDER's declared compatible purposes,
    # never from access-supplied fields (an access cannot self-authorize a new
    # purpose) (SWARM-M E7; D-0006-46)
    compatible = (ap == wp) or (ap in _as_set(work.get("compatible_purposes")))
    # normalize the source so "memory " / "Memory" cannot evade the guard
    if str(access.get("source", "")).strip().lower() in _MEMORY_SOURCES \
            and ap != wp:
        return False
    return compatible


def purpose_binding_findings(accesses: list[dict], work: dict) -> list[Finding]:
    """Every access must be purpose-compatible; each incompatible access is a
    PURPOSE_BINDING_FAILURE (P0)."""
    out: list[Finding] = []
    for a in accesses or []:
        if not purpose_compatible(a, work):
            subj = str(a.get("access_id") or a.get("data_class") or "-")
            out.append(Finding(PURPOSE_BINDING_FAILURE, P0, subj,
                               "data access incompatible with work privacy "
                               "purpose", {"access_purpose": a.get("purpose"),
                                           "work_purpose":
                                           (work or {}).get("privacy_purpose"),
                                           "source": a.get("source")}))
    return out


def scope_binding_findings(steps: list[dict], work: dict) -> list[Finding]:
    """Every step target must lie within allowed_scope and outside forbidden_scope
    (D-0006-46). A forbidden target is P0; a target merely outside allowed scope
    is P1."""
    work = work or {}
    allowed = _as_set(work.get("allowed_scope"))
    forbidden = _as_set(work.get("forbidden_scope"))
    out: list[Finding] = []
    for s in steps or []:
        target = s.get("target")
        subj = str(s.get("step_id") or target or "-")
        tset = _as_set(target)
        if forbidden and (tset & forbidden):
            out.append(Finding(PURPOSE_BINDING_FAILURE, P0, subj,
                               "step target is within forbidden scope",
                               {"target": target,
                                "forbidden": sorted(tset & forbidden)}))
        elif allowed and tset and not (tset <= allowed):
            out.append(Finding(PURPOSE_BINDING_FAILURE, P1, subj,
                               "step target outside allowed scope",
                               {"target": target,
                                "outside": sorted(tset - allowed)}))
    return out


def data_minimization_findings(accesses: list[dict],
                               work: dict) -> list[Finding]:
    """Flag accesses to data classes beyond those declared in required_inputs.
    Advisory (P2) — unless the access is also purpose-incompatible, which is a
    hard PURPOSE_BINDING_FAILURE (P0)."""
    work = work or {}
    required = _as_set(work.get("required_inputs"))
    out: list[Finding] = []
    for a in accesses or []:
        dc = a.get("data_class")
        if dc is None or str(dc) in required:
            continue
        subj = str(a.get("access_id") or dc)
        if not purpose_compatible(a, work):
            out.append(Finding(PURPOSE_BINDING_FAILURE, P0, subj,
                               "access beyond required inputs AND purpose-"
                               "incompatible", {"data_class": dc,
                                                "reason": "purpose_incompatible"}))
        else:
            out.append(Finding(PURPOSE_BINDING_FAILURE, P2, subj,
                               "access to data class beyond required_inputs "
                               "(minimization)", {"data_class": dc,
                                                  "reason": "data_minimization"}))
    return out


def _step_fingerprint(step: dict) -> str:
    # fingerprint the FULL material step so a step matching an admitted
    # action+target but carrying new material parameters (amount, recipient,
    # ...) is NOT deemed admitted (SWARM-M E6; D-0006-47)
    step = step or {}
    return core_hash({"action": step.get("action"),
                      "target": step.get("target"),
                      "parameters": step.get("parameters"),
                      "amount": step.get("amount"),
                      "recipient": step.get("recipient"),
                      "effect_class": step.get("effect_class")})


def hidden_work(admitted_steps: list[dict],
                executed_steps: list[dict]) -> list[Finding]:
    """Any executed step with no counterpart in the admitted plan / approved
    replan is HIDDEN_WORK_DETECTED (P0). Steps are compared by a fingerprint over
    their action and target (D-0006-47)."""
    admitted = {_step_fingerprint(s) for s in (admitted_steps or [])}
    out: list[Finding] = []
    for s in executed_steps or []:
        fp = _step_fingerprint(s)
        if fp not in admitted:
            subj = str((s or {}).get("step_id") or (s or {}).get("target") or "-")
            out.append(Finding(HIDDEN_WORK_DETECTED, P0, subj,
                               "executed step not present in admitted plan",
                               {"fingerprint": fp,
                                "action": (s or {}).get("action"),
                                "target": (s or {}).get("target")}))
    return out


def _authority(plan: dict) -> tuple[set, set]:
    plan = plan or {}
    return _as_set(plan.get("effect_classes")), _as_set(plan.get("targets"))


def least_authority_path(plans: list[dict]) -> dict:
    """Among valid plans, prefer the one requiring the narrowest authority —
    fewest effect classes and targets (D-0006-48). Dominance is STRICT when the
    preferred plan's effect and target sets are subsets of EVERY other valid
    plan's; otherwise the preference is ADVISORY (a tie or partial order)."""
    valid = [p for p in (plans or []) if p.get("valid", True)]
    if not valid:
        return {"preferred_plan_id": None, "dominance": "ADVISORY"}

    def size(p):
        e, t = _authority(p)
        return len(e) + len(t)

    preferred = min(valid, key=lambda p: (size(p),
                                          str(p.get("plan_id") or "")))
    pe, pt = _authority(preferred)
    others = [p for p in valid if p is not preferred]
    strict = bool(others) and all(
        pe <= oe and pt <= ot and (pe < oe or pt < ot)
        for oe, ot in (_authority(o) for o in others))
    return {"preferred_plan_id": preferred.get("plan_id"),
            "dominance": "STRICT" if strict else "ADVISORY"}
