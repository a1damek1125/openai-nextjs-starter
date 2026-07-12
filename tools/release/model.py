"""Shared vocabulary for the Release Assurance kernel (SP0009 §13, §16,
D-0009-05/07).

Fixes the closed alphabets every module reasons over: gate applicability vs
result (kept SEPARATE, D-0009-07), candidate/gate/attempt/flake/artifact/trust/
waiver/defeater state machines (§13), the ten-dimension release risk vector
(D-0009-05, never averaged), and the event/reason-code registry (§16). Reuses
the proven Finding/Report shape: a Report is valid iff zero P0 and zero P1.

Governance tooling only; never imported by product code (INV-0009-66/67).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities (proven pattern) ---------------------------------------------
P0 = "P0"
P1 = "P1"
P2 = "P2"
SEVERITIES = (P0, P1, P2)

# --- gate applicability vs result: SEPARATE dimensions (D-0009-07) -----------
APPLICABILITY = ("REQUIRED", "NOT_APPLICABLE", "REVIEW_REQUIRED")
GATE_RESULTS = ("PASS", "FAIL", "UNKNOWN", "STALE", "INVALID", "WAIVED")
GATE_SEVERITIES = ("HARD", "ADVISORY")

# --- candidate lifecycle (§13.1) ---------------------------------------------
CANDIDATE_STATES = (
    "DRAFT", "CLASSIFIED", "IMPACT_ANALYZED", "SLICE_CLOSED", "GATES_PLANNED",
    "VERIFYING", "QUALIFIED", "ARTIFACT_CLOSURE_SEALED",
    "READY_FOR_LATER_PROMOTION",
    # alternative states
    "BLOCKED", "PAUSED", "CANCELLED", "SUPERSEDED", "INVALIDATED",
    "SUSPENDED_BY_DEFEATER", "REQUALIFICATION_REQUIRED",
)

# --- test attempt results (§13.3) --------------------------------------------
ATTEMPT_RESULTS = ("PLANNED", "STARTED", "PASS", "FAIL", "TIMEOUT",
                   "ENVIRONMENT_INVALID", "ABORTED")

# --- flake classification (§13.4, D-0009-19) ----------------------------------
FLAKE_CLASSES = ("TEST_FLAKE_CONFIRMED", "PRODUCT_NONDETERMINISM",
                 "ENVIRONMENT_INSTABILITY", "DEPENDENCY_INSTABILITY",
                 "NOT_REPRODUCED", "UNKNOWN")

# --- artifact lifecycle (§13.5) ------------------------------------------------
ARTIFACT_STATES = ("BUILDING", "BUILT", "REPRODUCED", "ATTESTED",
                   "CLOSURE_COMPLETE", "SEALED", "REJECTED", "INVALIDATED")

# --- trust root lifecycle (§13.6) ----------------------------------------------
TRUST_ROOT_STATES = ("PROPOSED", "ACTIVE", "ROTATING", "SUPERSEDED",
                     "EXPIRED", "REVOKED")

# --- waiver lifecycle (§13.7) --------------------------------------------------
WAIVER_STATES = ("PROPOSED", "REVIEWED", "ACTIVE", "EXPIRED", "REJECTED",
                 "REVOKED")

# --- feature flag lifecycle (§13.8) --------------------------------------------
FLAG_STATES = ("PROPOSED", "VALIDATED", "DORMANT", "LIMITED", "ACTIVE",
               "RETIRING", "REMOVED")

# --- defeater lifecycle (§13.10) -----------------------------------------------
DEFEATER_STATES = ("OPEN", "VALIDATED", "BLOCKING",
                   "REQUALIFICATION_TRIGGERED", "RESOLVED", "REJECTED")

# --- release risk vector dimensions (D-0009-05) — never averaged ----------------
RISK_DIMS = ("tenant", "authority", "safety", "privacy", "compatibility",
             "migration", "supply_chain", "externality", "irreversibility",
             "epistemic_unknown")
# dimensions whose flag alone is a hard release concern
HARD_RISK_DIMS = frozenset({"tenant", "authority", "safety", "supply_chain",
                            "irreversibility"})
RISK_LEVELS = ("HIGH", "ELEVATED", "LOW", "UNKNOWN")

# --- change classes (§11.1, AC-0009-025..032) -----------------------------------
CHANGE_CLASSES = (
    "CONTRACT_CHANGE", "SEMANTIC_CHANGE", "SAFETY_CHANGE", "AUTHORITY_CHANGE",
    "MIGRATION_CHANGE", "DEPENDENCY_CHANGE", "CI_WORKFLOW_CHANGE",
    "AI_CLOSURE_CHANGE", "TEST_CHANGE", "DOCS_CHANGE", "GOVERNANCE_TOOLING_CHANGE",
    "UNKNOWN_CHANGE",
)

# --- SBOM completeness (D-0009-35) ----------------------------------------------
SBOM_COMPLETENESS = ("COMPLETE", "INCOMPLETE", "INCOMPLETE_FIRST_PARTY",
                     "INCOMPLETE_THIRD_PARTY", "UNKNOWN")

# --- scanner diversity classes (§11.19) -----------------------------------------
SCANNER_DIVERSITY = ("INDEPENDENT_ENOUGH", "PARTIALLY_DEPENDENT",
                     "COMMON_MODE_DOMINATED", "UNKNOWN")

# --- taint flow status (10.14) ---------------------------------------------------
TAINT_STATUSES = ("UNRESOLVED", "SAFE_TRANSFORMED", "BLOCKED")

# --- reason codes / events (§16, §18) — the closed failure vocabulary -------------
REASON_CODES = frozenset({
    # change / candidate
    "CHANGE_CLASSIFIED", "CHANGE_CLASSIFICATION_UNKNOWN",
    "RELEASE_SLICE_NOT_CLOSED", "CANDIDATE_CREATED", "CANDIDATE_SUPERSEDED",
    "CANDIDATE_PAUSED", "CANDIDATE_RESUMED", "CANDIDATE_GENOME_MISMATCH",
    "CANDIDATE_INVALID", "IMPACT_CONE_INCOMPLETE",
    # gates / obligations
    "GATE_REQUIRED", "GATE_FAILED", "GATE_UNKNOWN", "GATE_STALE",
    "GATE_INVALID", "NON_WAIVABLE_GATE_FAILED", "GATE_DEPENDENCY_CYCLE",
    "GATE_EVIDENCE_MISSING", "DOD_OBLIGATION_OPEN", "DOD_INCOMPLETE",
    # tests / flakes / mutation
    "TEST_COVERAGE_GAP", "TEST_COVERAGE_INCOMPLETE", "TEST_FAILURE_RECORDED",
    "TEST_RERUN_RECORDED", "FLAKE_SUSPECTED", "FLAKE_CLUSTER_DETECTED",
    "PRODUCT_NONDETERMINISM_SUSPECTED", "ENVIRONMENT_INSTABILITY_SUSPECTED",
    "CRITICAL_TEST_QUARANTINE_BLOCKED", "FLAKE_CLASSIFICATION_UNKNOWN",
    "MUTATION_SURVIVED",
    # builds / artifacts
    "BUILD_INPUT_UNDECLARED", "BUILD_INPUT_UNKNOWN", "BUILD_NOT_REPRODUCIBLE",
    "BUILDER_DIVERSITY_INSUFFICIENT", "BUILDER_QUORUM_FAILED",
    "ARTIFACT_DIGEST_MISMATCH", "ARTIFACT_SUBSTITUTION",
    "ARTIFACT_CLOSURE_INCOMPLETE", "ARTIFACT_SEALED_MUTATION",
    # provenance / trust / transparency
    "PROVENANCE_MISSING", "PROVENANCE_SUBJECT_MISMATCH",
    "UNKNOWN_PREDICATE_REJECTED", "ATTESTATION_INVALID",
    "TRUST_ROOT_EXPIRED", "TRUST_ROOT_REVOKED", "TRUST_ROOT_INVALID",
    "TRUST_ROOT_ROLLBACK_DETECTED", "TRUST_FREEZE_DETECTED",
    "TRUST_THRESHOLD_NOT_MET", "TRANSPARENCY_RECEIPT_INVALID",
    "TRANSPARENCY_RECEIPT_MISSING", "ATTESTATION_QUORUM_FAILED",
    # sbom / vuln / vex
    "SBOM_MISSING", "SBOM_INCOMPLETE", "SBOM_SUBJECT_MISMATCH",
    "AI_ML_BOM_INCOMPLETE", "VULNERABILITY_POLICY_FAILED",
    "VULNERABILITY_EVIDENCE_STALE", "VEX_EVIDENCE_INSUFFICIENT",
    "LICENSE_POLICY_FAILED", "SECRET_EXPOSURE_DETECTED",
    # CI / agentic security
    "DEPENDENCY_NOT_PINNED", "CI_TOKEN_OVERPRIVILEGED",
    "DANGEROUS_CI_WORKFLOW", "AGENTIC_WORKFLOW_INJECTION_PATH",
    "CI_TAINT_UNRESOLVED", "SCANNER_COMMON_MODE_RISK",
    "SCANNER_DIVERSITY_INSUFFICIENT", "EXTERNAL_CONTENT_AUTHORITY_REJECTED",
    # waivers / approvals
    "WAIVER_EXPIRED", "WAIVER_INVALID", "SELF_APPROVAL_REJECTED",
    "NON_WAIVABLE_WAIVER_REJECTED",
    # rollback / flags
    "ROLLBACK_NOT_PROVEN", "FORWARD_FIX_REQUIRED", "FEATURE_FLAG_EXPIRED",
    "FEATURE_FLAG_AUTHORITY_VIOLATION", "FEATURE_FLAG_INVALID",
    # AI closure
    "OPAQUE_PROVIDER_UPDATE_SUSPECTED", "AI_RELEASE_CLOSURE_INCOMPLETE",
    "AI_BOM_INVALID", "SP0011_EVIDENCE_FABRICATION_REJECTED",
    # delivery
    "CANARY_SAMPLE_RATIO_MISMATCH", "CANARY_INTERFERENCE_DETECTED",
    "PROGRESSIVE_ABORT_REQUIRED", "SEQUENTIAL_POLICY_NOT_PREDECLARED",
    # qualification / defeaters
    "RELEASE_QUALIFIED", "RELEASE_DEFEATER_OPENED",
    "RELEASE_REQUALIFICATION_REQUIRED", "RELEASE_INVALIDATED",
    "RELEASE_PROOF_MISMATCH", "DEFEATER_BLOCKING", "UNKNOWN_BUDGET_EXCEEDED",
    # boundary / analysis
    "BOUNDARY_VIOLATION", "ANALYSIS_LIMIT_REACHED",
    "PROGRAM_DEPENDENCY_BLOCKED", "ROADMAP_SCOPE_MISMATCH",
})


def _require_code(code: str) -> str:
    if code not in REASON_CODES:
        raise ValueError(f"unknown reason code {code!r}")
    return code


# --- Finding / Report (proven cross-mission shape) ----------------------------
@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    subject: str
    message: str
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"bad severity {self.severity!r}")
        _require_code(self.kind)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "subject": self.subject, "message": self.message,
                "details": self.details}


@dataclass(frozen=True)
class Report:
    findings: tuple = ()

    @property
    def valid(self) -> bool:
        return not any(f.severity in (P0, P1) for f in self.findings)

    def by_severity(self, sev: str) -> list:
        return [f for f in self.findings if f.severity == sev]

    def as_dict(self) -> dict:
        return {"valid": self.valid,
                "counts": {s: len(self.by_severity(s)) for s in SEVERITIES},
                "findings": [f.as_dict() for f in self.findings]}


def report(findings) -> Report:
    return Report(tuple(findings))
