"""Typed model + constants for the Continuous Technology Sovereignty Constitution.

Hard findings (P0/P1) are Boolean gates: a hard-requirement failure or a
sovereignty violation can never be offset by a good advisory score (INV-0004-07,
§12.6). Advisory signals (P2) never override them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- severities -------------------------------------------------------------
P0, P1, P2 = "P0", "P1", "P2"

# --- technology criticality (D-0004-15) ------------------------------------
CRITICALITY = ["T0", "T1", "T2", "T3", "T4"]
CRITICAL_CLASSES = {"T3", "T4"}   # require stronger exit evidence (AC-0004-040)

# --- strategic-IP class (D-0004-61) ----------------------------------------
STRATEGIC_CLASSES = {"OWN", "ADAPT", "BUY", "STANDARDIZE", "DEFER"}

# --- technology lifecycle status -------------------------------------------
TECH_STATUS = {"ACTIVE", "LEGACY", "UNUSED", "PLANNED", "RETIRED"}
RUNTIME_SCOPES = {"PRODUCTION", "DEV", "TEST", "BUILD"}

# --- TDR lifecycle (D-0004-03 / §13.1) -------------------------------------
TDR_STATES = ["PROPOSED", "RESEARCHING", "TRIAL", "ACCEPTED", "ACTIVE",
              "REVIEW_DUE", "SUPERSEDED", "RETIRED", "REJECTED", "DEFERRED",
              "INVALIDATED"]
# states considered a committed/accepted decision whose record is append-only
FROZEN_TDR_STATES = {"ACCEPTED", "ACTIVE", "REVIEW_DUE", "SUPERSEDED", "RETIRED",
                     "INVALIDATED"}

# --- fitness status (D-0004-75 / §13.2) ------------------------------------
FITNESS_STATES = {"NOT_EVALUATED", "ACTIVE_AND_FIT", "REVIEW_DUE",
                  "ACTIVE_DEGRADED", "INVALIDATED"}

# --- provider certification (§13.3) ----------------------------------------
CERT_STATES = ["UNREGISTERED", "REGISTERED", "CONTRACT_VALIDATED",
               "FAULT_TESTED", "SHADOW_VALIDATED", "PRODUCTION_ELIGIBLE",
               "SUSPENDED", "RETIRED"]

# --- exit readiness (§13.4) ------------------------------------------------
EXIT_STATES = {"UNKNOWN", "DOCUMENTED", "EXPORT_VALIDATED",
               "SUBSTITUTE_VALIDATED", "DRILLED", "STALE"}
EXIT_DIMENSIONS = ("data_export", "state_export", "adapter_portability",
                   "replacement_availability", "replay_coverage",
                   "rollback_readiness", "operational_readiness",
                   "documentation_readiness")

# --- evidence lifecycle (§13.5) --------------------------------------------
EVIDENCE_STATES = {"CURRENT", "REVIEW_DUE", "STALE", "SUPERSEDED"}
EVIDENCE_TYPES = {"OFFICIAL_DOCUMENTATION", "OFFICIAL_SPECIFICATION",
                  "PRIMARY_SOURCE", "VENDOR_CLAIM", "BENCHMARK",
                  "RESEARCH_PAPER", "REPOSITORY_FACT", "ARCHITECTURAL_INFERENCE"}

# --- reversibility (D-0004-12) ---------------------------------------------
REVERSIBILITY = {"R0", "R1", "R2", "R3", "R4"}

# --- switching-cost vector dimensions (D-0004-13) --------------------------
SWITCHING_COST_DIMS = ("adapter", "data", "state", "revalidation", "operations",
                       "training", "downtime")

# --- lock-in dimensions (D-0004-14) — kept separate, never collapsed -------
LOCK_IN_DIMENSIONS = ("protocol_lock_in", "data_lock_in", "state_lock_in",
                      "semantic_lock_in", "operational_lock_in",
                      "commercial_lock_in", "skills_lock_in",
                      "governance_lock_in", "identity_lock_in",
                      "observability_lock_in")

# --- substitutability (D-0004-35 / §11.10) — NOT Boolean -------------------
SUBSTITUTABILITY = {"CONTRACT_EQUIVALENT", "FUNCTIONALLY_ACCEPTABLE",
                    "PARTIALLY_SUBSTITUTABLE", "NON_EQUIVALENT", "UNKNOWN"}

# --- diversity classes (D-0004-18) -----------------------------------------
DIVERSITY = {"DIVERSITY_REAL", "DIVERSITY_PARTIAL", "DIVERSITY_COSMETIC"}

# --- provider failure/error taxonomy (D-0004-27) ---------------------------
PROVIDER_OUTCOMES = {"SUCCESS", "FAILED", "UNKNOWN_OUTCOME"}
ERROR_TAXONOMY = {"TIMEOUT", "RATE_LIMIT", "QUOTA_EXHAUSTED",
                  "AUTHENTICATION_FAILURE", "AUTHORIZATION_FAILURE",
                  "PROVIDER_OUTAGE", "DATA_REJECTED", "PARTIAL_SUCCESS",
                  "UNKNOWN_OUTCOME"}

# --- hard-constraint result (D-0004-06) — UNKNOWN != PASS ------------------
CONSTRAINT_RESULTS = {"PASS", "FAIL", "UNKNOWN"}

# --- radar (D-0004-57) -----------------------------------------------------
RADAR_RINGS = {"ADOPT", "TRIAL", "ASSESS", "HOLD"}

# --- fitness mode ----------------------------------------------------------
FITNESS_MODES = {"DETERMINISTIC", "ADVISORY"}

# --- finding / failure kinds (SP0004 §16 / §18) ----------------------------
INVALID_TDR = "INVALID_TDR"
UNKNOWN_CANDIDATE = "UNKNOWN_CANDIDATE"
CANDIDATE_INCOMPLETE = "CANDIDATE_INCOMPLETE"
MISSING_HARD_REQUIREMENT = "MISSING_HARD_REQUIREMENT"
HARD_REQUIREMENT_FAILED = "HARD_REQUIREMENT_FAILED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
DECISION_NOT_CALIBRATED = "DECISION_NOT_CALIBRATED"
TECHNOLOGY_DECISION_STALE = "TECHNOLOGY_DECISION_STALE"
TECHNOLOGY_DECISION_INVALIDATED = "TECHNOLOGY_DECISION_INVALIDATED"
CANDIDATE_DOMINATED = "CANDIDATE_DOMINATED"
DECISION_SENSITIVE = "DECISION_SENSITIVE"
APPEND_ONLY_VIOLATION = "APPEND_ONLY_VIOLATION"
COMMON_MODE_DEPENDENCY = "COMMON_MODE_DEPENDENCY"
COSMETIC_PROVIDER_DIVERSITY = "COSMETIC_PROVIDER_DIVERSITY"
CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN = "CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN"
PROVIDER_CONTRACT_LEAKAGE = "PROVIDER_CONTRACT_LEAKAGE"
PROVIDER_IDENTITY_LEAKAGE = "PROVIDER_IDENTITY_LEAKAGE"
PROVIDER_ERROR_AS_BUSINESS_STATE = "PROVIDER_ERROR_AS_BUSINESS_STATE"
CREDENTIAL_SCOPE_VIOLATION = "CREDENTIAL_SCOPE_VIOLATION"
RAW_SECRET_EXPOSURE = "RAW_SECRET_EXPOSURE"
PROVIDER_CONFORMANCE_FAILURE = "PROVIDER_CONFORMANCE_FAILURE"
DATA_EXPORT_GAP = "DATA_EXPORT_GAP"
EXIT_PLAN_MISSING = "EXIT_PLAN_MISSING"
EXIT_PLAN_STALE = "EXIT_PLAN_STALE"
SUBSTITUTION_EVIDENCE_STALE = "SUBSTITUTION_EVIDENCE_STALE"
PROTOCOL_VERSION_STALE = "PROTOCOL_VERSION_STALE"
PROTOCOL_VERSION_UNSUPPORTED = "PROTOCOL_VERSION_UNSUPPORTED"
PROTOCOL_DEPRECATION_REVIEW_REQUIRED = "PROTOCOL_DEPRECATION_REVIEW_REQUIRED"
TECHNOLOGY_FITNESS_DEGRADED = "TECHNOLOGY_FITNESS_DEGRADED"
TECHNOLOGY_FITNESS_FAILED = "TECHNOLOGY_FITNESS_FAILED"
PROVIDER_IMPLEMENTATION_IDENTITY_UNCERTAINTY = \
    "PROVIDER_IMPLEMENTATION_IDENTITY_UNCERTAINTY"
FLOATING_VERSION = "FLOATING_VERSION"
EXTENSION_REDEFINES_CORE = "EXTENSION_REDEFINES_CORE"
UNIVERSAL_PROVIDER_CONTRACT = "UNIVERSAL_PROVIDER_CONTRACT"
ONE_WAY_MIGRATION_RISK = "ONE_WAY_MIGRATION_RISK"
BUSINESS_STATE_PROVIDER_ONLY = "BUSINESS_STATE_PROVIDER_ONLY"
FALSE_SLSA_COMPLIANCE = "FALSE_SLSA_COMPLIANCE"
WAIVER_INVALID = "WAIVER_INVALID"
SHADOW_EXTERNAL_EFFECT_BLOCKED = "SHADOW_EXTERNAL_EFFECT_BLOCKED"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
REGRET_NOT_CALIBRATED = "REGRET_ANALYSIS_NOT_CALIBRATED"


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    subject: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "subject": self.subject, "message": self.message,
                "detail": self.detail}


class Report:
    """`valid` iff no P0 and no P1 remain open (§12.6 no averaged safety)."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def extend(self, fs) -> None:
        for f in fs:
            self.add(f)

    def counts(self) -> dict:
        c = {P0: 0, P1: 0, P2: 0}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c

    @property
    def valid(self) -> bool:
        c = self.counts()
        return c[P0] == 0 and c[P1] == 0

    def to_dict(self) -> dict:
        return {"valid": self.valid, "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "metrics": self.metrics}
