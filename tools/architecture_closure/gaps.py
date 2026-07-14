"""Gap classification — closure vs production (SP0010 FUNCTION P, §10.11,
D-0010-44, AC-0010-166..174, 180).

SP0010 may close the constitutional ARCHITECTURE with non-blocking production
gaps, but NEVER with a constitutional blocker (INV-0010-55). Every gap is typed,
owned, and carries a next action. Blocking types (CONSTITUTIONAL_BLOCKER,
CROSS_TWIN_CONTRADICTION, GLOBAL_INVARIANT_GAP) prevent closure; the rest
(implementation, infrastructure, field-validation, SP0011-evaluation,
operational, regulatory, future-enhancement) remain visible in the final report
but do not block architecture closure. The real, honestly-recorded production
gaps for this repository come from the audit + swarm reviews (SWARM-A §F).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, GAP_TYPES, BLOCKING_GAP_TYPES

# The honestly-recorded standing production gaps (SWARM-A §F, audit + reviews).
# None of these is a constitutional blocker; each is a production/eval gap with
# an owner and a next action.
STANDING_GAPS = [
    {"gap_type": "PRODUCTION_INFRASTRUCTURE_GAP",
     "statement": "single-node SQLite + local filesystem persistence; no "
                  "production storage, no deployment/secrets/monitoring infra",
     "owner": "infra", "next_action": "provision production storage + "
     "deployment controller (post-SP0011)",
     "source": "docs/audits/AUDIT_REPORT_1_FULL_SYSTEM_TRUTH_AND_SP_"
     "INVENTORY.md"},
    {"gap_type": "PRODUCTION_INFRASTRUCTURE_GAP",
     "statement": "no CI / lockfile / build backend exist; each absence is "
                  "hashed explicitly into the SP0009 candidate genome",
     "owner": "release", "next_action": "add provider-neutral CI + pinned "
     "lockfile when a runtime target exists",
     "source": "docs/release/FINALIS_SWARM_REVIEW.md"},
    {"gap_type": "IMPLEMENTATION_GAP",
     "statement": "all external effects are mocks (telephony, email/SMS, "
                  "calendar, video, PDF, e-signature, payment, AV, OCR, "
                  "ASR/TTS, web fetch); no real provider wired",
     "owner": "product", "next_action": "wire real providers behind the "
     "existing replaceable adapters (SP0004 exit strategies)",
     "source": "docs/audits/AUDIT_REPORT_1_FULL_SYSTEM_TRUTH_AND_SP_"
     "INVENTORY.md"},
    {"gap_type": "FIELD_VALIDATION_GAP",
     "statement": "browser E2E file is environment-sensitive (live Chromium "
                  "selector-render timeouts under parallel load); excluded "
                  "from the deterministic release suite by convention",
     "owner": "release", "next_action": "stabilize module-scoped server/page "
     "fixtures + fixed-port allocation",
     "source": "docs/release/FINALIS_SWARM_REVIEW.md"},
    {"gap_type": "SP0011_EVALUATION_GAP",
     "statement": "reliability/evaluation and the 1000/1000 score are not "
                  "produced here; SP0011 interface is PENDING_SP0011 and "
                  "cannot carry evidence",
     "owner": "SP0011", "next_action": "execute SP0011 against this Program "
     "Seal + admission package",
     "source": "docs/release/FINALIS_SWARM_REVIEW.md"},
    {"gap_type": "OPERATIONAL_GAP",
     "statement": "auth is dev-grade; evidence is unanchored (no external "
                  "transparency log deployed); no rollback infra",
     "owner": "ops", "next_action": "production auth + anchored transparency "
     "(post-SP0011)",
     "source": "docs/audits/AUDIT_REPORT_1_FULL_SYSTEM_TRUTH_AND_SP_"
     "INVENTORY.md"},
]


def gap(*, gap_type: str, statement: str, owner: str, next_action: str,
        claim_refs=(), source: str = "") -> dict:
    if gap_type not in GAP_TYPES:
        raise ValueError(f"unknown gap_type {gap_type!r}")
    g = {"gap_type": gap_type, "statement": statement, "owner": owner,
         "next_action": next_action, "claim_refs": list(claim_refs),
         "source": source, "status": "OPEN",
         "blocks_closure": gap_type in BLOCKING_GAP_TYPES}
    g["gap_id"] = "GAP-" + hash_obj(g)[:16]
    return g


def build_ledger(closure_findings: list) -> dict:
    """The gap ledger: standing production gaps + any CONSTITUTIONAL_BLOCKER /
    contradiction / invariant gap derived from live closure findings."""
    gaps = [gap(**{k: g[k] for k in ("gap_type", "statement", "owner",
                                     "next_action", "source")})
            for g in STANDING_GAPS]
    # derive blockers from P0 closure findings in blocking domains
    for f in closure_findings:
        gt = _finding_to_gap_type(f)
        if gt:
            gaps.append(gap(gap_type=gt, statement=f["message"],
                            owner="architecture",
                            next_action="resolve before closure",
                            claim_refs=[f["subject"]], source=f["kind"]))
    return {
        "gaps": gaps,
        "constitutional_blockers": [g["gap_id"] for g in gaps
                                    if g["gap_type"] == "CONSTITUTIONAL_BLOCKER"],
        "blocking_gaps": [g["gap_id"] for g in gaps if g["blocks_closure"]],
        "production_gaps": [g["gap_id"] for g in gaps
                            if not g["blocks_closure"]],
    }


def _finding_to_gap_type(f: dict):
    kind = f.get("kind", "")
    if kind in ("CRITICAL_CLAIM_BOTH", "CRITICAL_CLAIM_NEITHER",
                "CRITICAL_CLAIM_REFUTED", "UNSUPPORTED_CIRCULAR_ASSURANCE",
                "CONSTITUTION_INTERFACE_INVALID", "ASSURANCE_HYPEREDGE_INVALID",
                "HYPEREDGE_PREMISE_MISSING", "DEFEATER_GROUNDED"):
        return "CONSTITUTIONAL_BLOCKER"
    if kind in ("CROSS_TWIN_CONTRADICTION", "PARALLEL_AUTHORITY_DETECTED",
                "PARALLEL_REGISTRY_DETECTED"):
        return "CROSS_TWIN_CONTRADICTION"
    if kind in ("GLOBAL_INVARIANT_FAILED", "GLOBAL_INVARIANT_UNKNOWN",
                "TENANT_NONINTERFERENCE_FAILED", "APPROVAL_ISOLATION_FAILED",
                "CONTROL_LANGUAGE_INVARIANCE_FAILED",
                "PROVIDER_ACCOUNT_ISOLATION_FAILED", "NONINTERFERENCE_FAILED",
                "NONINTERFERENCE_LIMIT_REACHED"):
        return "GLOBAL_INVARIANT_GAP"
    return None


def gap_findings(ledger: dict) -> list[Finding]:
    out: list[Finding] = []
    for g in ledger["gaps"]:
        if g["gap_type"] == "CONSTITUTIONAL_BLOCKER":
            out.append(Finding(
                "CONSTITUTIONAL_BLOCKER_OPEN", P0, g["gap_id"],
                f"constitutional blocker: {g['statement'][:100]}", g))
    return out


def gap_root(ledger: dict) -> str:
    return hash_obj(sorted(g["gap_id"] for g in ledger["gaps"]))
