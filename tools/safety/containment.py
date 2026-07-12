"""Independent Containment Boundary + Emergency Containment (SP0005 D-0005-31/32/
33, INV-0005-01, §5.20).

For boundary-enforceable hard safety properties, the effect-mediating layer must
enforce the property INDEPENDENTLY of model cooperation (INV-0005-01): the model
is an untrusted proposer (D-0005-02). A containment proof applies only to the
MODELED scope (action types, state, boundary events, assumptions) — never a
universal AI-safety claim (D-0005-32, AC-0005-070). Emergency containment must be
enforceable OUTSIDE the same model whose behavior may be unsafe (D-0005-33,
AC-0005-071).
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_SAFETY_SCHEMA


def validate_containment(spec: dict) -> list[Finding]:
    out: list[Finding] = []
    sid = spec.get("boundary_id", "-")
    # scope must be explicit (no universal claim)
    if not spec.get("modeled_action_types") or not spec.get("assumptions"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "containment boundary must declare modeled_action_types "
                           "and assumptions (scope explicit, AC-0005-070)", {}))
    # the property must NOT depend on model correctness (INV-0005-01)
    if spec.get("depends_on_model_correctness"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "containment property depends on model correctness — a "
                           "hard boundary must be model-independent (INV-0005-01)",
                           {}))
    return out


def validate_emergency(spec: dict) -> list[Finding]:
    out: list[Finding] = []
    sid = spec.get("emergency_id", "-")
    # emergency containment must not require the primary model's cooperation
    if spec.get("requires_primary_model_cooperation"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "emergency containment requires primary-model "
                           "cooperation — forbidden (AC-0005-071, D-0005-33)", {}))
    if not spec.get("enforced_by"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                           "emergency containment must declare an enforcer outside "
                           "the acting model", {}))
    return out
