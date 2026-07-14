"""Global invariant registry + composition (SP0010 FUNCTION J, §10, D-0010-13,
AC-0010-081..094).

Global invariants are the cross-cutting properties that no single constitution
owns alone: tenant isolation, authority conservation, delegation attenuation,
approval context binding, safety dominance of protected effects, proof-not-
authority, release/runtime separation, zero-lost-work, outcome evidence,
historical interpretability, learning promotion gating. Each has an OWNER
constitution, EVIDENCE requirements, and a criticality flag. Global invariants
are NON-COMPENSATORY (D-0010-13): no average architecture score offsets a failed
hard invariant. An invariant with UNKNOWN status blocks closure (fail-closed).
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0

# invariant_id -> owner, critical, the guarantee claim(s) that establish it,
# and the real product control(s) whose existence grounds it.
GLOBAL_INVARIANTS = {
    "INV-TENANT-ISOLATION": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-authority-conserved"],
        "control_refs": ["finalis/portal/app.py:require_permission",
                         "finalis/portal/db.py:tenant_id"],
        "hyperproperty": "HP-TENANT-NONINTERFERENCE"},
    "INV-AUTHORITY-CONSERVATION": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-authority-conserved"],
        "control_refs": ["finalis/portal/app.py:require_role"],
        "hyperproperty": None},
    "INV-DELEGATION-ATTENUATION": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-authority-conserved"],
        "control_refs": ["tools/governed_work"], "hyperproperty": None},
    "INV-APPROVAL-CONTEXT-BOUND": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-approval-context-bound"],
        "control_refs": ["tools/governed_work"],
        "hyperproperty": "HP-APPROVAL-ISOLATION"},
    "INV-SAFETY-DOMINATOR": {
        "owner": "SP0005", "critical": True,
        "established_by": ["CL-SP0005-safety-dominates-protected-effects"],
        "control_refs": ["tools/safety"], "hyperproperty": None},
    "INV-PROOF-NOT-AUTHORITY": {
        "owner": "SP0009", "critical": True,
        "established_by": ["CL-SP0009-release-proof-not-runtime-authority"],
        "control_refs": ["tools/release/envelope.py"], "hyperproperty": None},
    "INV-RELEASE-RUNTIME-SEPARATION": {
        "owner": "SP0009", "critical": True,
        "established_by": ["CL-SP0009-release-proof-not-runtime-authority"],
        "control_refs": ["tools/release"], "hyperproperty": None},
    "INV-ZERO-LOST-WORK": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-zero-lost-work"],
        "control_refs": ["tools/governed_work"], "hyperproperty": None},
    "INV-OUTCOME-EVIDENCE": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-zero-lost-work"],
        "control_refs": ["tools/governed_work"], "hyperproperty": None},
    "INV-HISTORICAL-INTERPRETABILITY": {
        "owner": "SP0002", "critical": True,
        "established_by": ["CL-SP0002-historical-epoch-interpretable",
                          "CL-SP0007-historical-envelope-epoch-bound"],
        "control_refs": ["tools/compatibility"], "hyperproperty": None},
    "INV-LEARNING-PROMOTION-GATED": {
        "owner": "SP0006", "critical": True,
        "established_by": ["CL-SP0006-authority-conserved"],
        "control_refs": ["tools/governed_work"], "hyperproperty": None},
    "INV-CONTROL-LANGUAGE-INVARIANCE": {
        "owner": "SP0002", "critical": True,
        "established_by": ["CL-SP0002-semantics-versioned"],
        "control_refs": ["tools/semantics"],
        "hyperproperty": "HP-CONTROL-LANGUAGE-INVARIANCE"},
    "INV-PROVIDER-ACCOUNT-SEPARATION": {
        "owner": "SP0004", "critical": True,
        "established_by": ["CL-SP0004-provider-replaceable"],
        "control_refs": ["tools/technology"],
        "hyperproperty": "HP-PROVIDER-ACCOUNT-SEPARATION"},
}


def _control_present(root: Path, ref: str) -> bool:
    """A control ref 'path:symbol' HOLDS only when the file exists AND the named
    symbol actually appears in it — not merely the file (red-team P2-7). A bare
    'path' (dir or file, no symbol) requires only existence."""
    parts = ref.split(":", 1)
    path = root / parts[0]
    if not path.exists():
        return False
    if len(parts) == 1:
        return True
    sym = parts[1]
    target = path if path.is_file() else None
    if target is None:
        return True                 # a directory ref with a symbol: existence
    try:
        return sym in target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def evaluate_invariants(root: Path, supported: set, *,
                        hyperproperty_status: dict | None = None) -> dict:
    """An invariant HOLDS when its establishing guarantee claim(s) are all
    SUPPORTED_ONLY, its grounding control ref(s) exist on disk, and its
    associated hyperproperty (if any) PASSes. Otherwise UNKNOWN/FAILED."""
    hp = hyperproperty_status or {}
    results = {}
    for inv, spec in sorted(GLOBAL_INVARIANTS.items()):
        claims_ok = all(c in supported for c in spec["established_by"])
        controls_present = all(_control_present(root, ref)
                               for ref in spec["control_refs"])
        hp_id = spec.get("hyperproperty")
        hp_ok = True if hp_id is None else hp.get(hp_id) == "PASS"
        hp_unknown = hp_id is not None and hp.get(hp_id) in (None, "UNKNOWN",
                                                             "LIMIT_REACHED")
        if claims_ok and controls_present and hp_ok:
            status = "HOLD"
        elif hp_unknown or not claims_ok:
            status = "UNKNOWN"
        else:
            status = "FAILED"
        results[inv] = {"status": status, "owner": spec["owner"],
                        "critical": spec["critical"],
                        "claims_supported": claims_ok,
                        "controls_present": controls_present,
                        "hyperproperty": hp_id, "hyperproperty_ok": hp_ok}
    return results


def invariant_findings(results: dict) -> list[Finding]:
    out: list[Finding] = []
    for inv, rec in sorted(results.items()):
        if not rec["critical"]:
            continue
        if rec["status"] == "FAILED":
            out.append(Finding(
                "GLOBAL_INVARIANT_FAILED", P0, inv,
                f"critical global invariant {inv} FAILED (owner "
                f"{rec['owner']}); non-compensatory (D-0010-13)", rec))
        elif rec["status"] == "UNKNOWN":
            out.append(Finding(
                "GLOBAL_INVARIANT_UNKNOWN", P0, inv,
                f"critical global invariant {inv} is UNKNOWN: an unknown hard "
                "invariant blocks closure (fail-closed)", rec))
    return out


def invariant_root(results: dict) -> str:
    return hash_obj({inv: rec["status"] for inv, rec in sorted(results.items())})
