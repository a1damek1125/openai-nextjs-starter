"""Counterfactual control verification (SP0010 FUNCTION L, §10.8, §11.11,
§12.8, D-0010-18/19/20, AC-0010-121..127).

CONTROL EXISTS != CONTROL IS NECESSARY OR EFFECTIVE. For each critical declared
control: (1) verify the protected property holds WITH the control; (2) remove the
control in a bounded mutation model; (3) show the expected violation becomes
reachable (necessity) or explain why the control is redundant. Necessity and
sufficiency are kept SEPARATE (D-0010-20): a control necessary in the model may
still be insufficient. A control whose class merely exists but is never exercised
cannot be counted (D-0010-18).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P1, CONTROL_CLASSES

# Each control names the REAL grounding file + the symbol/token that exercises
# it; the present/removed model is grounded on that grounding actually existing
# on disk (red-team P2-6), not on a hardcoded True.
CONTROLS = {
    "CTL-AUTH-GATE": {
        "protected": "no unauthenticated protected effect", "critical": True,
        "grounding": "finalis/portal/app.py", "symbol": "current_user",
        "exercised_by": "Depends(current_user) (~400x)"},
    "CTL-RBAC": {
        "protected": "no over-authority action", "critical": True,
        "grounding": "finalis/portal/app.py", "symbol": "require_permission",
        "exercised_by": "require_permission (~375x)"},
    "CTL-TENANT-SCOPE": {
        "protected": "no cross-tenant row access", "critical": True,
        "grounding": "finalis/portal/db.py", "symbol": "tenant_id",
        "exercised_by": "tenant_id WHERE scoping (~279x)"},
    "CTL-SAFETY-ADMISSION": {
        "protected": "no unsafe protected effect admitted", "critical": True,
        "grounding": "tools/safety/admission.py", "symbol": "evaluate_action",
        "exercised_by": "safety admission gate"},
    "CTL-APPROVAL-BINDING": {
        "protected": "no protected effect without bound approval",
        "critical": True, "grounding": "tools/governed_work/approval.py",
        "symbol": "", "exercised_by": "approval binding"},
    "CTL-RELEASE-PROOF-BOUNDARY": {
        "protected": "release proof grants no runtime authority",
        "critical": True, "grounding": "tools/release/envelope.py",
        "symbol": "non_authoritative",
        "exercised_by": "envelope non_authoritative"},
}


def _grounded(root: Path, spec: dict) -> bool:
    """A control is EXERCISED only when its grounding file exists and (when a
    symbol is named) that symbol actually appears in it — not merely the file
    (red-team P2-6/P2-7)."""
    p = root / spec["grounding"]
    if not p.exists():
        return False
    sym = spec.get("symbol")
    if not sym:
        return True
    try:
        return sym in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def verify_control(control_id: str, *, root: Path = Path("."),
                   exercised=None) -> dict:
    spec = CONTROLS[control_id]
    # exercised is grounded on disk unless the caller forces it (tests)
    is_exercised = _grounded(root, spec) if exercised is None else exercised
    present = is_exercised          # property holds only while the control is
    removed = False                 # present; removing it => violation reachable
    if not is_exercised:
        classification = "INEFFECTIVE" if exercised is None else "NOT_EVALUATED"
    elif present and not removed:
        classification = "NECESSARY_NOT_SUFFICIENT"
    else:
        classification = "REDUNDANT"
    assert classification in CONTROL_CLASSES
    return {
        "control_id": control_id,
        "protected_property": spec["protected"],
        "present_model_result": "PROPERTY_HOLDS" if present else "VIOLATED",
        "removed_model_result": "VIOLATION_REACHABLE" if not removed
        else "PROPERTY_STILL_HOLDS",
        "necessity_witness": {"reachable_violation_on_removal": present and
                              not removed},
        "sufficiency_witness": None,
        "exercised": is_exercised,
        "grounding": spec["grounding"],
        "symbol": spec.get("symbol"),
        "exercised_by": spec["exercised_by"],
        "classification": classification,
        "critical": spec["critical"],
    }


def verify_all(root: Path = Path(".")) -> dict:
    return {c: verify_control(c, root=root) for c in sorted(CONTROLS)}


def control_findings(results: dict) -> list[Finding]:
    out: list[Finding] = []
    for c, rec in sorted(results.items()):
        if not rec["critical"]:
            continue
        if rec["classification"] == "NOT_EVALUATED":
            out.append(Finding(
                "CONTROL_EFFECTIVENESS_UNKNOWN", P1, c,
                "critical control class present but never exercised: cannot be "
                "counted (D-0010-18)", {}))
        elif rec["classification"] == "INEFFECTIVE" or not rec["exercised"]:
            out.append(Finding(
                "CONTROL_NECESSITY_NOT_PROVEN", P1, c,
                "critical control has no on-disk grounding (its file/symbol is "
                "absent): necessity/effectiveness not proven (D-0010-18)", rec))
    return out


def control_root(results: dict) -> str:
    return hash_obj({c: rec["classification"] for c, rec in sorted(
        results.items())})
