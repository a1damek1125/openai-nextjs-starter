"""Shared vocabulary for the FINALIS Evaluation Kernel (SP0011 §13, §16, §18,
D-0011-*).

Fixes the closed alphabets the evaluation reasons over: the maturity ladder
(M0..M5, never auto-promoted), outcome classes (SUCCESS/FAILURE/PARTIAL/UNKNOWN —
UNKNOWN and PARTIAL are never success), the oracle hierarchy (deterministic
outranks LLM judge), the claim/credit/scenario/run/judge/scorecard/seal state
machines, the non-compensatory hard-gate ids, the qualification-credit accounting
(200 indivisible 5-credit claims → 1000), and the event/reason-code registry.
Reuses the proven Finding/Report shape: a Report is valid iff zero P0 and zero P1.

Evaluation tooling only; never imported by product code (INV D-0011).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities --------------------------------------------------------------
P0 = "P0"
P1 = "P1"
P2 = "P2"
SEVERITIES = (P0, P1, P2)

# --- maturity ladder (§2.3, D-0011-029) — evidence never auto-promotes -------
MATURITY_LEVELS = ("M0", "M1", "M2", "M3", "M4", "M5")
MATURITY_NAMES = {
    "M0": "DEFINITION_ONLY", "M1": "REPOSITORY_EVIDENCED",
    "M2": "CONTROLLED_REPLAY_QUALIFIED", "M3": "SANDBOX_SYSTEM_QUALIFIED",
    "M4": "FIELD_PILOT_QUALIFIED", "M5": "PRODUCTION_QUALIFIED",
}
_MATURITY_RANK = {m: i for i, m in enumerate(MATURITY_LEVELS)}


def maturity_meets(achieved: str, required: str) -> bool:
    """Achieved maturity satisfies required ONLY when it is at least as high.
    Strict: an unknown level never satisfies (fail-closed)."""
    if achieved not in _MATURITY_RANK or required not in _MATURITY_RANK:
        return False
    return _MATURITY_RANK[achieved] >= _MATURITY_RANK[required]


# --- outcome / effect / activity (§11.8, D-0011-011, INV 17-21) --------------
OUTCOME_CLASSES = ("SUCCESS", "FAILURE", "PARTIAL", "UNKNOWN")


def is_success(outcome: str) -> bool:
    """Only SUCCESS is success. PARTIAL and UNKNOWN are never success
    (INV-20/21); a truthy string is not SUCCESS (strict)."""
    return outcome == "SUCCESS"


# --- oracle hierarchy (§11.9, D-0011-044) — deterministic outranks judge ------
ORACLE_TYPES = ("DETERMINISTIC", "CRYPTOGRAPHIC", "CONTRACT", "EXTERNAL_STATE",
                "HUMAN", "AGENT_AS_JUDGE", "LLM_JUDGE", "UNRESOLVED")
ORACLE_PRIORITY = {t: i for i, t in enumerate(ORACLE_TYPES)}
# oracle types that may NOT solely close a critical claim (D-0011-045/046)
UNTRUSTED_SOLE_ORACLES = frozenset({"AGENT_AS_JUDGE", "LLM_JUDGE", "UNRESOLVED"})

# --- identifiability (causal attribution, §11.19, D-0011-073) ----------------
IDENTIFIABILITY = ("IDENTIFIED", "PARTIALLY_IDENTIFIED", "NOT_IDENTIFIED",
                   "ASSOCIATIONAL_ONLY")

# --- contamination classes (§11.11, D-0011-030/031) --------------------------
CONTAMINATION_CLASSES = ("CLEAN", "METADATA_EXPOSURE", "QUESTION_CONTEXT_EXPOSURE",
                         "ANSWER_EXPOSURE", "UNKNOWN")

# --- statistical design (§11.12/11.13) ---------------------------------------
STAT_DESIGNS = ("FIXED_SAMPLE", "SEQUENTIAL", "ANYTIME_VALID")

# --- fidelity (§11.24) -------------------------------------------------------
FIDELITY_LEVELS = ("STATIC", "UNIT", "REPLAY", "SANDBOX", "FIELD", "PRODUCTION")
FIDELITY_TO_MATURITY = {"STATIC": "M0", "UNIT": "M1", "REPLAY": "M2",
                        "SANDBOX": "M3", "FIELD": "M4", "PRODUCTION": "M5"}

# --- state machines (§13) ----------------------------------------------------
PLAN_STATES = ("DRAFT", "PREREGISTERED", "FROZEN", "RUNNING", "ANALYZING",
               "VERIFIED", "CLOSED", "INVALIDATED", "PAUSED", "SUPERSEDED",
               "LIMIT_REACHED")
SCENARIO_STATES = ("PROPOSED", "VALIDATING", "ORACLE_VALIDATED",
                   "INTEGRITY_CHECKED", "ESCROWED", "ACTIVE", "RETIRED",
                   "AMBIGUOUS", "UNSOLVABLE", "CONTAMINATED", "QUARANTINED",
                   "SUPERSEDED")
RUN_STATES = ("CREATED", "ENVIRONMENT_READY", "EXECUTING", "OUTCOME_PENDING",
              "ORACLE_CHECKING", "EVIDENCE_SEALED", "COMPLETE", "FAILED",
              "PARTIAL", "UNKNOWN_OUTCOME", "CONTAMINATED", "TAMPERED",
              "INVALIDATED")
CLAIM_STATES = ("NOT_EVALUATED", "EVIDENCE_COLLECTING", "ANALYZING", "QUALIFIED",
                "EVIDENCE_INSUFFICIENT", "REFUTED", "BOTH", "STALE", "DEFEATED",
                "OUT_OF_SCOPE")
CREDIT_STATES = ("UNAWARDED", "EVIDENCE_BOUND", "CERTIFICATE_GENERATED",
                 "KERNEL_CHECKING", "AWARDED", "CERTIFICATE_INVALID", "BLOCKED",
                 "STALE", "REVOKED", "SUPERSEDED")
JUDGE_STATES = ("REGISTERED", "CALIBRATING", "META_EVALUATED", "QUALIFIED",
                "ACTIVE", "UNQUALIFIED", "LANGUAGE_RESTRICTED", "TASK_RESTRICTED",
                "STALE", "SUSPENDED", "RETIRED")
SCORECARD_STATES = ("DRAFT", "COMPUTED", "HARD_GATE_CHECKED", "ENVELOPE_ATTACHED",
                    "INDEPENDENTLY_VERIFIED", "PUBLISHED", "BLOCKED", "EXPIRED",
                    "INVALIDATED", "REQUALIFICATION_REQUIRED", "SUPERSEDED")
SEAL_STATES = ("CANDIDATE", "KERNEL_VERIFIED", "INDEPENDENTLY_VERIFIED",
               "SEALED", "SUPERSEDED", "INVALIDATED", "EXPIRED",
               "REQUALIFICATION_REQUIRED")

# --- Finalis 1000 accounting (§2.2, §12.1) -----------------------------------
DOMAIN_COUNT = 10
CLAIMS_PER_DOMAIN = 20
CLAIM_COUNT = DOMAIN_COUNT * CLAIMS_PER_DOMAIN          # 200
CREDIT_PER_CLAIM = 5
MAX_CREDITS = CLAIM_COUNT * CREDIT_PER_CLAIM            # 1000

# --- non-compensatory hard gates (§2.5) --------------------------------------
HARD_GATES = (
    "PROGRAM_SEAL_VALID", "EVALUATION_SEAL_VALID", "P0_ZERO", "P1_ZERO",
    "TENANT_ISOLATION_CRITICAL_PASS", "AUTHORITY_CONSERVATION_CRITICAL_PASS",
    "CONSENT_CRITICAL_PASS", "PROTECTED_EFFECT_APPROVAL_PASS",
    "NO_PROOF_AS_AUTHORITY", "NO_RELEASE_PROOF_AS_AUTHORITY",
    "NO_EVALUATOR_TAMPERING", "NO_METRIC_TAMPERING", "NO_HELD_OUT_LEAKAGE",
    "NO_CRITICAL_CONTAMINATION", "NO_CRITICAL_UNRESOLVED_OUTCOME",
    "NO_OWNED_WORK_ORPHANING", "NO_CRITICAL_CALIBRATION_FAILURE",
    "NO_INVALID_CRITICAL_ORACLE", "NO_INVALID_CRITICAL_JUDGE",
    "NO_CRITICAL_LLM_JUDGE_SOLE", "NO_CRITICAL_UNKNOWN_AS_PASS",
    "NO_OUT_OF_SCOPE_STATISTICAL_CERT", "NO_STALE_CRITICAL_CREDIT",
    "NO_LOW_FIDELITY_PROMOTED", "NO_UNLOGGED_ADAPTIVE_SELECTION",
    "NO_HIDDEN_WEAK_STRATUM", "NO_FABRICATED_FIELD_EVIDENCE",
    "NO_FABRICATED_PRODUCTION_EVIDENCE",
)

# --- gap taxonomy ------------------------------------------------------------
GAP_TYPES = (
    "EVALUATION_INFRASTRUCTURE_GAP", "FIELD_EVIDENCE_GAP",
    "PRODUCTION_EVIDENCE_GAP", "MATURITY_GAP", "COVERAGE_GAP",
    "STATISTICAL_EVIDENCE_GAP", "ORACLE_GAP", "JUDGE_META_EVALUATION_GAP",
    "CONTAMINATION_GAP", "ACCEPTED_FUTURE_ENHANCEMENT",
)

# --- reason codes / events (§16, §18) — the closed vocabulary ----------------
REASON_CODES = frozenset({
    # roadmap / dependency / baseline
    "ROADMAP_SCOPE_MISMATCH", "PROGRAM_DEPENDENCY_BLOCKED", "PROGRAM_SEAL_INVALID",
    "PROGRAM_SEAL_ADMITTED", "BASELINE_NOT_CLEAN", "BASELINE_CHANGED",
    "EVALUATION_BASELINE_FROZEN",
    # TCB / kernel
    "EVALUATION_TCB_INCOMPLETE", "TRUSTED_KERNEL_INVALID", "TRUSTED_KERNEL_VERIFIED",
    "KERNEL_SUBSTITUTION_DETECTED",
    # configuration
    "CONFIGURATION_IDENTITY_INCOMPLETE", "EVALUATION_CONFIGURATION_CHANGED",
    # plan / estimand / statistics
    "EVALUATION_PLAN_INVALID", "ESTIMAND_UNDEFINED", "DEPENDENCE_STRUCTURE_UNDEFINED",
    "STATISTICAL_PLAN_VIOLATION", "OPTIONAL_STOPPING_VIOLATION",
    "MULTIPLE_TESTING_VIOLATION", "DEPENDENCE_ADJUSTMENT_MISSING",
    "SAMPLE_SIZE_INSUFFICIENT", "SEQUENTIAL_LIMIT_REACHED",
    # coverage / scenarios / escrow
    "CRITICAL_COVERAGE_INCOMPLETE", "SCENARIO_INVALID", "SCENARIO_AMBIGUOUS",
    "SCENARIO_UNSOLVABLE", "SCENARIO_CONTAMINATED", "CHALLENGE_ESCROW_INVALID",
    "HOLDOUT_ACCESS_VIOLATION", "SCENARIO_SATURATION",
    # contamination / integrity
    "MEMORY_CONTAMINATION", "EVALUATOR_TAMPERING", "METRIC_TAMPERING",
    "REWARD_HACKING", "SEARCH_TIME_CONTAMINATION", "CONTAMINATION_UNKNOWN",
    # oracles
    "ORACLE_MISSING", "ORACLE_INVALID", "ORACLE_DISAGREEMENT",
    "CRITICAL_LLM_JUDGE_SOLE",
    # robust / rare / long-horizon
    "WORST_STRATUM_FAILED", "ROBUST_MIXTURE_FAILED", "TAIL_RISK_LIMIT_EXCEEDED",
    "RARE_FAILURE_BOUND_INSUFFICIENT", "OBSERVED_CATASTROPHIC_FAILURE",
    "LONG_HORIZON_EXTRAPOLATION_LIMIT", "HIDDEN_WEAK_STRATUM",
    # causal / calibration
    "CAUSAL_IDENTIFICATION_FAILED", "CAUSAL_OVERCLAIM", "CALIBRATION_FAILED",
    "CONFORMAL_SCOPE_VIOLATION", "CONFIDENCE_AS_AUTHORITY",
    # judges / human
    "JUDGE_UNQUALIFIED", "JUDGE_BIAS_DETECTED", "HUMAN_REVIEW_UNRELIABLE",
    "ADJUDICATION_REQUIRED",
    # invariance / providers / fidelity / adaptive
    "MULTILINGUAL_INVARIANCE_FAILED", "PROVIDER_NONINFERIORITY_FAILED",
    "LOW_FIDELITY_EVIDENCE_PROMOTION", "ADAPTIVE_SELECTION_LOG_MISSING",
    "CRITICAL_SCENARIO_OMITTED",
    # credits / gates / score
    "CREDIT_CERTIFICATE_INVALID", "CREDIT_CERTIFICATE_CHECKED",
    "HARD_GATE_FAILED", "EVIDENCE_MATURITY_INSUFFICIENT", "EVIDENCE_EXPIRED",
    "EVIDENCE_MISSING", "EVIDENCE_STALE", "SCORECARD_INVALID",
    "SCORE_ARITHMETIC_INVALID", "QUALIFICATION_ENVELOPE_INVALID",
    "MATURITY_OVERSTATED", "SCORE_FABRICATION_REJECTED",
    # drift / requalification / genome / seal
    "REQUALIFICATION_REQUIRED", "EVALUATION_GENOME_MISMATCH",
    "EVALUATION_SEAL_MISMATCH", "EVALUATION_SEAL_CREATED", "RESOURCE_LIMIT_REACHED",
    # boundary
    "BOUNDARY_VIOLATION", "PRODUCTION_READINESS_FABRICATION_REJECTED",
})


def _require(code: str) -> str:
    if code not in REASON_CODES:
        raise ValueError(f"unknown reason code {code!r}")
    return code


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
        _require(self.kind)

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
