"""Shared model for the Governed Work Constitution (SP0006): severities, finding
kinds / reason codes (§16), state-machine alphabets (§13), enums, and the
Finding/Report result types. A hard finding (P0/P1) can never be offset by a
score (§11.7/§12.4); a Report is valid only with zero P0 and zero P1.

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities -------------------------------------------------------------
P0 = "P0"   # hard safety/authority violation — blocks
P1 = "P1"   # material governance defect — blocks admission/validity
P2 = "P2"   # advisory

# --- candidate intent / work order ------------------------------------------
INTERPRETATION_SOURCES = {"LLM", "HUMAN", "MEMORY", "EXTERNAL_EVENT", "DOCUMENT"}
INTENT_STATUS = {"UNTRUSTED_PROPOSAL"}

# --- governed work state machine (§13.1) ------------------------------------
WORK_STATES = [
    "DRAFT", "NORMALIZING", "AMBIGUOUS", "CONFLICTED", "ADMITTED", "PLANNING",
    "PLAN_READY", "DELEGATION_READY", "DELEGATED", "SHADOW_EXECUTION", "RUNNING",
    "PAUSED_FOR_DRIFT", "AWAITING_APPROVAL", "COMMIT_READY", "OUTCOME_PRODUCED",
    "OUTCOME_VERIFYING", "VERIFIED_COMPLETE", "PARTIALLY_VERIFIED", "FAILED",
    "CANCEL_REQUESTED", "CANCELLED", "EXPIRED", "QUARANTINED", "SUPERSEDED",
]
# states that can never (re)enter an executable state
NON_EXECUTABLE_STATES = {"AMBIGUOUS", "CONFLICTED", "EXPIRED", "CANCELLED",
                         "QUARANTINED", "SUPERSEDED", "FAILED"}
EXECUTABLE_STATES = {"RUNNING", "SHADOW_EXECUTION", "COMMIT_READY"}
TERMINAL_STATES = {"VERIFIED_COMPLETE", "CANCELLED", "EXPIRED", "SUPERSEDED",
                   "FAILED"}

# --- lease / delegation / approval / outcome sub-machines (§13.2..13.7) ------
LEASE_STATES = ["PROPOSED", "VALIDATED", "ACTIVE", "PARTIALLY_CONSUMED",
                "CONSUMED", "EXPIRED", "REVOKED", "INVALIDATED"]
LEASE_TERMINAL = {"CONSUMED", "EXPIRED", "REVOKED", "INVALIDATED"}
DELEGATION_STATES = ["PROPOSED", "ATTENUATION_VERIFIED", "BUDGET_RESERVED",
                     "ACTIVE", "COMPLETED", "REVOKED", "FAILED"]
APPROVAL_STATES = ["PROPOSED", "ISSUED", "ACTIVE", "CONSUMED", "EXPIRED",
                   "REVOKED", "INVALIDATED_BY_CONTEXT_CHANGE"]
OUTCOME_STATES = ["CLAIMED", "EVIDENCED", "VERIFYING", "VERIFIED",
                  "PARTIALLY_VERIFIED", "DISPUTED", "INVALIDATED"]
CANCEL_BARRIER_STATES = ["OPEN", "NEW_ACTIONS_BLOCKED", "LEASES_REVOKING",
                         "IN_FLIGHT_RECONCILING", "SAFE_TERMINATION_CONFIRMED",
                         "CLOSED"]
RECURRENCE_INSTANCE_STATES = ["SCHEDULED", "REAUTHORIZING", "ADMITTED",
                              "SKIPPED_NOT_AUTHORIZED", "EXPIRED"]

# --- capability lease dimensions (D-0006-16) --------------------------------
LEASE_SUBSET_DIMS = ("allowed_operations", "targets", "data_classes",
                     "effect_classes")
LEASE_CEILING_DIMS = ("risk_ceiling", "cost_ceiling")  # numeric ≤
EFFECT_CLASSES = {"READ", "DRAFT", "SIMULATE", "LOCAL_WRITE", "LOCAL_COMMIT",
                  "REVERSIBLE_EXTERNAL", "IRREVERSIBLE_EXTERNAL", "PAYMENT",
                  "COMMUNICATION"}

# --- budget dimensions (D-0006-23) ------------------------------------------
BUDGET_DIMENSIONS = ("financial_cost", "model_cost", "tool_call_quota",
                     "external_effect_quota", "data_access_quota",
                     "resource_capacity")   # additive dimensions
# non-additive dimensions handled specially: risk_vector, deadline (§D-0006-26/27)
RESERVATION_STATES = {"RESERVED", "CONSUMED", "RELEASED", "EXPIRED", "RECONCILED"}

# --- risk vector (D-0006-27) ------------------------------------------------
RISK_DIMENSIONS = ("operational", "financial", "privacy", "security", "legal",
                   "rights", "reputation", "irreversibility")
RISK_LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN")
CONTROL_CLASSES = ("CC0", "CC1", "CC2", "CC3", "CC4", "CC5")

# --- approval class lattice (D-0006-34) -------------------------------------
APPROVAL_CLASSES = ["A0", "A1", "A2", "A3", "A4", "A5"]
APPROVAL_CLASS_RANK = {c: i for i, c in enumerate(APPROVAL_CLASSES)}

# --- goal drift (D-0006-42..44) ---------------------------------------------
DRIFT_BANDS = ("ALIGNED", "DRIFT_OBSERVED", "PAUSE_AND_REPLAN",
               "BLOCK_AND_ESCALATE")
HARD_DRIFT_TRIGGERS = ("tenant", "purpose", "target", "forbidden_scope",
                       "capability_ceiling", "outcome_redefinition",
                       "hard_constraint_removed", "approval_context")

# --- outcome predicate families (§9.4) --------------------------------------
OUTCOME_PREDICATE_TYPES = {
    "ARTIFACT_EXISTS", "ARTIFACT_HASH", "SCHEMA_VALID", "CONTENT_INVARIANT",
    "SOURCE_COMPLETE", "MATERIAL_CLAIM_SUPPORTED", "NUMERICAL_RECONCILIATION",
    "TARGET_STATE_EQUALS", "BOUNDED_STATE_DELTA", "EXTERNAL_ACKNOWLEDGMENT",
    "HUMAN_APPROVAL_RECEIPT", "DEADLINE_MET", "COST_CEILING", "NO_FORBIDDEN_EFFECT",
    "TENANT_COMPLIANT", "PURPOSE_COMPLIANT", "INDEPENDENT_VERIFICATION",
}
VERIFICATION_MODES = {"DETERMINISTIC", "INDEPENDENT_QUALIFIED", "HYBRID",
                      "SELF_REPORT_ADVISORY"}
# oracles that can never SOLELY verify a critical outcome (D-0006-57, INV-0006 §)
NON_PRIMARY_OUTCOME_ORACLES = {"AGENT_SELF_REPORT", "LLM_JUDGE"}

# --- finding kinds / reason codes (§16) -------------------------------------
WORK_ORDER_AMBIGUOUS = "WORK_ORDER_AMBIGUOUS"
WORK_ORDER_CONFLICTED = "WORK_ORDER_CONFLICTED"
WORK_ORDER_REJECTED = "WORK_ORDER_REJECTED"
WORK_ORDER_EXPIRED = "WORK_ORDER_EXPIRED"
UNDEFINED_OUTCOME = "UNDEFINED_OUTCOME"
UNDEFINED_ACCOUNTABLE_OWNER = "UNDEFINED_ACCOUNTABLE_OWNER"
CONTEXT_USED_AS_AUTHORITY = "CONTEXT_USED_AS_AUTHORITY"
MEMORY_USED_AS_AUTHORITY = "MEMORY_USED_AS_AUTHORITY"
DELEGATION_AUTHORITY_AMPLIFICATION = "DELEGATION_AUTHORITY_AMPLIFICATION"
DELEGATION_CYCLE_DETECTED = "DELEGATION_CYCLE_DETECTED"
DELEGATION_DEPTH_EXCEEDED = "DELEGATION_DEPTH_EXCEEDED"
DELEGATION_FANOUT_EXCEEDED = "DELEGATION_FANOUT_EXCEEDED"
LEASE_ATTENUATION_FAILURE = "LEASE_ATTENUATION_FAILURE"
LEASE_EXPIRED = "LEASE_EXPIRED"
LEASE_REVOKED = "LEASE_REVOKED"
REVOCATION_PROPAGATION_STALE = "REVOCATION_PROPAGATION_STALE"
BUDGET_OVERCOMMITMENT = "BUDGET_OVERCOMMITMENT"
BUDGET_CONSERVATION_FAILURE = "BUDGET_CONSERVATION_FAILURE"
QUANTITATIVE_RISK_NOT_CALIBRATED = "QUANTITATIVE_RISK_NOT_CALIBRATED"
APPROVAL_CLASS_INSUFFICIENT = "APPROVAL_CLASS_INSUFFICIENT"
APPROVAL_CONTEXT_MISMATCH = "APPROVAL_CONTEXT_MISMATCH"
SELF_APPROVAL_DETECTED = "SELF_APPROVAL_DETECTED"
GOAL_DRIFT_OBSERVED = "GOAL_DRIFT_OBSERVED"
HARD_GOAL_DRIFT = "HARD_GOAL_DRIFT"
HIDDEN_WORK_DETECTED = "HIDDEN_WORK_DETECTED"
PURPOSE_BINDING_FAILURE = "PURPOSE_BINDING_FAILURE"
RECURRENCE_REAUTHORIZATION_FAILED = "RECURRENCE_REAUTHORIZATION_FAILED"
CANCELLATION_BARRIER_INCOMPLETE = "CANCELLATION_BARRIER_INCOMPLETE"
UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED = "UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED"
OUTCOME_EVIDENCE_INCOMPLETE = "OUTCOME_EVIDENCE_INCOMPLETE"
OUTCOME_DISPUTED = "OUTCOME_DISPUTED"
OUTCOME_DEFEATER_OPEN = "OUTCOME_DEFEATER_OPEN"
ACCOUNTABILITY_CHAIN_BROKEN = "ACCOUNTABILITY_CHAIN_BROKEN"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
INVALID_WORK_SCHEMA = "INVALID_WORK_SCHEMA"
INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
OUTPUT_NOT_OUTCOME = "OUTPUT_NOT_OUTCOME"
SELF_REPORT_AS_SOLE_OUTCOME_ORACLE = "SELF_REPORT_AS_SOLE_OUTCOME_ORACLE"

# blocking finding kinds default to P0 unless issued at another severity
P0_KINDS = frozenset({
    CONTEXT_USED_AS_AUTHORITY, MEMORY_USED_AS_AUTHORITY,
    DELEGATION_AUTHORITY_AMPLIFICATION, DELEGATION_CYCLE_DETECTED,
    LEASE_ATTENUATION_FAILURE, BUDGET_CONSERVATION_FAILURE,
    SELF_APPROVAL_DETECTED, HARD_GOAL_DRIFT, HIDDEN_WORK_DETECTED,
    PURPOSE_BINDING_FAILURE, ACCOUNTABILITY_CHAIN_BROKEN,
    SELF_REPORT_AS_SOLE_OUTCOME_ORACLE,
})


@dataclass
class Finding:
    kind: str
    severity: str
    subject: str
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "subject": self.subject, "message": self.message,
                "details": self.details}


class Report:
    """`valid` iff no P0 and no P1 remain — no aggregate score can hide a hard
    governance finding (§11.7, §12.4)."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.metrics: dict = {}

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def extend(self, fs) -> None:
        for f in (fs.findings if isinstance(fs, Report) else fs):
            self.findings.append(f)

    def counts(self) -> dict:
        c = {"P0": 0, "P1": 0, "P2": 0}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c

    @property
    def valid(self) -> bool:
        c = self.counts()
        return c["P0"] == 0 and c["P1"] == 0

    def to_dict(self) -> dict:
        return {"valid": self.valid, "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "metrics": self.metrics}
