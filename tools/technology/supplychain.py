"""Supply-Chain & BOM/AI-BOM Strategy (SP0004 D-0004-77/78/79, §5.8/5.9/5.10,
INV-0004 supply-chain).

SP0004 defines STRATEGY only: it explicitly evaluates SLSA, CycloneDX, SPDX and
AI/ML-BOM and records a decision — it does NOT implement a production SBOM
pipeline and NEVER claims compliance without implementation evidence (D-0004-77,
AC-0004-128/129). An attestation is a claim requiring verification, distinct from
verification itself (D-0004-79, AC-0004-134).
"""
from __future__ import annotations

from .model import Finding, P0, P1, FALSE_SLSA_COMPLIANCE, INVALID_TDR

STANDARDS = {"SLSA", "CYCLONEDX", "SPDX", "AI_ML_BOM"}
DECISIONS = {"ADOPT_TARGET", "EVALUATE", "DEFER", "REJECT", "NOT_APPLICABLE"}


def validate_strategy(strategy: dict) -> list[Finding]:
    out: list[Finding] = []
    covered = {s.get("standard") for s in strategy.get("standards", [])}
    for required in STANDARDS:
        if required not in covered:
            out.append(Finding(INVALID_TDR, P1, required,
                               f"supply-chain strategy does not evaluate "
                               f"{required} (AC-0004-128/130/131/132)", {}))
    for s in strategy.get("standards", []):
        sid = s.get("standard", "-")
        if s.get("decision") not in DECISIONS:
            out.append(Finding(INVALID_TDR, P1, sid,
                               f"invalid supply-chain decision {s.get('decision')!r}",
                               {}))
        # never claim compliance without implementation evidence (D-0004-77)
        if s.get("claims_compliance") and not s.get("implementation_evidence"):
            out.append(Finding(FALSE_SLSA_COMPLIANCE, P0, sid,
                               f"{sid} claims compliance without implementation "
                               "evidence (AC-0004-129)", {}))
    return out


def attestation_verified(attestation: dict) -> bool:
    """An attestation alone is not sufficient — a verification policy must inspect
    it (D-0004-79, AC-0004-134)."""
    return bool(attestation.get("verified_by_policy"))
