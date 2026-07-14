"""Typed model + constants for the Safety Kernel & Assurance Constitution.

Hard findings (P0/P1) are Boolean gates: a safety score can never override a hard
safety invariant (§12.2, INV-0005-10), UNKNOWN is never LOW (INV-0005-09), and a
prohibited action can never be allowed by optimization (INV-0005-10). Threat,
hazard, loss and risk are kept strictly distinct (INV-0005-02).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- severities -------------------------------------------------------------
P0, P1, P2 = "P0", "P1", "P2"

# --- loss / hazard ----------------------------------------------------------
LOSS_CATEGORIES = {"PHYSICAL", "FINANCIAL", "PRIVACY", "RIGHTS", "LEGAL",
                   "REPUTATION", "SAFETY_OF_SERVICE", "SOCIETAL", "SECURITY"}
CRITICALITY = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
CRITICAL_LEVELS = {"HIGH", "CRITICAL"}
HAZARD_STATUS = {"ACTIVE", "MITIGATED", "ACCEPTED", "RETIRED"}

# --- unsafe control actions (STPA — 4 categories, D-0005-06) ---------------
UCA_CATEGORIES = {"NOT_PROVIDED_WHEN_REQUIRED", "PROVIDED_WHEN_UNSAFE",
                  "WRONG_TIMING_OR_ORDER", "STOPPED_TOO_SOON_OR_APPLIED_TOO_LONG"}

# --- control types + status (D-0005-34/35) ---------------------------------
CONTROL_TYPES = {"PREVENTIVE", "DETECTIVE", "CONTAINMENT", "RECOVERY",
                 "VERIFICATION"}
CONTROL_STATUS = {"DECLARED", "IMPLEMENTED", "TESTED", "EVIDENCED",
                  "EFFECTIVE_FOR_SCOPE", "STALE", "FAILED"}
# a control counts as a real barrier only when at least tested+evidenced
EFFECTIVE_STATUS = {"EVIDENCED", "EFFECTIVE_FOR_SCOPE"}

# --- control independence (D-0005-37) --------------------------------------
INDEPENDENCE = {"INDEPENDENCE_ESTABLISHED", "PARTIALLY_INDEPENDENT",
                "INDEPENDENCE_NOT_ESTABLISHED", "UNKNOWN"}
SHARED_FAILURE_DOMAINS = ("model", "provider", "prompt", "policy_engine", "data",
                          "human", "code_path")

# --- proof obligations (D-0005-11/12) --------------------------------------
OBLIGATION_TYPES = {"PO-AUTHORITY", "PO-TENANT", "PO-TARGET", "PO-CONSENT",
                    "PO-RECIPIENT", "PO-DATA-SCOPE", "PO-SAFETY-CONSTRAINT",
                    "PO-HUMAN-OVERSIGHT", "PO-IDEMPOTENCY", "PO-REVERSIBILITY",
                    "PO-OUTCOME-OBSERVATION"}
OBLIGATION_STATUS = {"SATISFIED", "UNSATISFIED", "UNKNOWN", "STALE",
                     "NOT_APPLICABLE"}

# --- admission lease lifecycle (D-0005 §13.1) ------------------------------
LEASE_STATES = {"PROPOSED", "EVALUATING", "ACTIVE", "REVALIDATION_REQUIRED",
                "REVOKED", "EXPIRED", "CONSUMED"}
# material context fields whose change invalidates a lease (D-0005-15)
MATERIAL_CONTEXT_FIELDS = ("target", "recipient", "amount", "authority",
                           "tenant", "data_scope", "consent", "policy_version",
                           "semantic_epoch", "provider_contract_version",
                           "trajectory_state")

# --- safety state vector dimensions (D-0005-18) — kept distinct -------------
STATE_DIMENSIONS = ("consequence", "authority_depth", "irreversibility",
                    "affected_scope", "rights_sensitivity", "data_sensitivity",
                    "legal_sensitivity", "observability", "uncertainty",
                    "vulnerability_sensitivity")
# ordered risk levels for the control-class lattice (D-0005-19)
RISK_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
# control classes (the lattice codomain) — join is the max
CONTROL_CLASSES = ["CC0", "CC1", "CC2", "CC3", "CC4", "CC5"]

# --- irreversibility (D-0005-10) -------------------------------------------
IRREVERSIBILITY = {"REVERSIBLE", "PARTIALLY_REVERSIBLE", "IRREVERSIBLE",
                   "UNKNOWN"}

# --- assurance claim lifecycle (D-0005 §13.2) ------------------------------
CLAIM_STATES = {"UNSUPPORTED", "PARTIALLY_SUPPORTED", "SUPPORTED_CURRENT",
                "CHALLENGED", "STALE", "INVALIDATED"}

# --- evidence lifecycle (D-0005-42/43) -------------------------------------
EVIDENCE_STATUS = {"CURRENT", "EVIDENCE_REVIEW_REQUIRED", "EVIDENCE_STALE",
                   "SUPERSEDED"}

# --- regulatory source taxonomy (D-0005-48) --------------------------------
SOURCE_STATUS = {"BINDING_LAW", "ADOPTED_NOT_YET_APPLICABLE", "FORMAL_PROPOSAL",
                 "POLITICAL_AGREEMENT_NOT_YET_ENACTED", "FINAL_OFFICIAL_GUIDANCE",
                 "DRAFT_OFFICIAL_GUIDANCE", "OFFICIAL_CONSULTATION",
                 "VOLUNTARY_OFFICIAL_CODE", "INTERNATIONAL_STANDARD",
                 "SECURITY_FRAMEWORK", "RESEARCH", "VENDOR_GUIDANCE",
                 "INTERNAL_POLICY", "UNCERTAIN"}
# statuses that are NOT binding law (a draft/proposal/agreement is not law)
NON_BINDING_STATUS = {"FORMAL_PROPOSAL", "POLITICAL_AGREEMENT_NOT_YET_ENACTED",
                      "DRAFT_OFFICIAL_GUIDANCE", "OFFICIAL_CONSULTATION",
                      "RESEARCH", "VENDOR_GUIDANCE", "UNCERTAIN"}
REG_DATE_TYPES = ("proposal_date", "political_agreement_date", "adoption_date",
                  "publication_date", "entry_into_force_date",
                  "general_application_date", "special_application_dates",
                  "consultation_close_date", "transition_deadlines")
# only these date types can legitimately be an *applicable* date; a pre-enactment
# date (proposal/political-agreement/consultation/publication) is NEVER an
# applicable date (INV-0005-20, SWARM-N E5)
APPLICABLE_DATE_TYPES = frozenset({"entry_into_force_date",
                                   "general_application_date",
                                   "special_application_dates",
                                   "transition_deadlines"})
APPLICABILITY = {"APPLIES", "DOES_NOT_APPLY", "POSSIBLY_APPLIES",
                 "NOT_YET_APPLICABLE", "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW",
                 "SUPERSEDED"}

# --- internal high-impact classes (D-0005-51) — NOT legal classification ----
IMPACT_CLASSES = {"FINALIS_IMPACT_0", "FINALIS_IMPACT_1", "FINALIS_IMPACT_2",
                  "FINALIS_IMPACT_3", "FINALIS_IMPACT_4", "FINALIS_IMPACT_5"}

# --- safety oracle hierarchy (D-0005-61) — strongest first -----------------
ORACLE_TYPES = ["ENVIRONMENT_STATE", "ARTIFACT_CRYPTO_EVIDENCE",
                "INDEPENDENT_FORMAL_RULE_CHECKER", "CALIBRATED_STATISTICAL",
                "HUMAN_SPECIALIST", "LLM_JUDGE", "AGENT_SELF_REPORT"]
# oracles that can NEVER be the SOLE oracle for a hard property (INV-0005-11)
NON_PRIMARY_ORACLES = {"LLM_JUDGE", "AGENT_SELF_REPORT"}

# --- future admission outcomes (D-0005-82) ---------------------------------
ADMISSION_OUTCOMES = {"ALLOW", "DENY", "ABSTAIN", "REQUIRE_MORE_EVIDENCE",
                      "REQUIRE_HUMAN_REVIEW", "REQUIRE_SPECIALIST_REVIEW",
                      "QUARANTINE"}

# --- human oversight dimensions (D-0005-53) --------------------------------
OVERSIGHT_DIMENSIONS = ("sufficient_information", "reject_authority",
                        "time_to_intervene", "relevant_competence",
                        "stop_capability", "independence", "manageable_load")
# required material fields in a human review packet (D-0005-54)
REVIEW_PACKET_FIELDS = ("proposal", "rationale", "authority_used", "target",
                        "material_facts", "uncertainties", "risk_class",
                        "irreversibility", "constraints", "safe_alternative",
                        "consequence_approve", "consequence_reject")

# --- incident lifecycle (D-0005 §13.5) -------------------------------------
INCIDENT_STATES = {"DETECTED", "CONTAINING", "CONTAINED", "INVESTIGATING",
                   "REMEDIATING", "VERIFYING", "CLOSED"}

# --- finding / failure kinds (SP0005 §16 / §18) ----------------------------
INVALID_SAFETY_SCHEMA = "INVALID_SAFETY_SCHEMA"
UNKNOWN_HAZARD = "UNKNOWN_HAZARD"
UNCONTROLLED_CRITICAL_HAZARD = "UNCONTROLLED_CRITICAL_HAZARD"
INVALID_ACTION_SAFETY_CONTRACT = "INVALID_ACTION_SAFETY_CONTRACT"
INVALID_TRAJECTORY_CONTRACT = "INVALID_TRAJECTORY_CONTRACT"
TRAJECTORY_SAFETY_VIOLATION = "TRAJECTORY_SAFETY_VIOLATION"
PROOF_OBLIGATION_UNKNOWN = "PROOF_OBLIGATION_UNKNOWN"
PROOF_OBLIGATION_FAILED = "PROOF_OBLIGATION_FAILED"
SAFETY_ADMISSION_LEASE_INVALID = "SAFETY_ADMISSION_LEASE_INVALID"
SAFETY_ADMISSION_LEASE_EXPIRED = "SAFETY_ADMISSION_LEASE_EXPIRED"
SAFETY_TOCTOU_MISMATCH = "SAFETY_TOCTOU_MISMATCH"
MATERIAL_CONTEXT_CHANGED = "MATERIAL_CONTEXT_CHANGED"
PROHIBITED_ACTION = "PROHIBITED_ACTION"
PROHIBITED_PRACTICE_CANDIDATE = "PROHIBITED_PRACTICE_CANDIDATE"
CONTROL_CLASS_UNRESOLVED = "CONTROL_CLASS_UNRESOLVED"
CONTROL_INDEPENDENCE_NOT_ESTABLISHED = "CONTROL_INDEPENDENCE_NOT_ESTABLISHED"
CRITICAL_DEFEATER_OPEN = "CRITICAL_DEFEATER_OPEN"
ASSURANCE_COVERAGE_GAP = "ASSURANCE_COVERAGE_GAP"
ASSURANCE_EVIDENCE_STALE = "ASSURANCE_EVIDENCE_STALE"
SOURCE_STATUS_UNKNOWN = "SOURCE_STATUS_UNKNOWN"
LEGAL_TIMELINE_STATE_AMBIGUOUS = "LEGAL_TIMELINE_STATE_AMBIGUOUS"
LEGAL_APPLICABILITY_UNCERTAIN = "LEGAL_APPLICABILITY_UNCERTAIN"
DRAFT_SOURCE_USED_AS_BINDING = "DRAFT_SOURCE_USED_AS_BINDING"
POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW = "POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW"
HUMAN_OVERSIGHT_INSUFFICIENT = "HUMAN_OVERSIGHT_INSUFFICIENT"
HUMAN_REVIEW_PACKET_INCOMPLETE = "HUMAN_REVIEW_PACKET_INCOMPLETE"
SAFETY_ORACLE_INSUFFICIENT = "SAFETY_ORACLE_INSUFFICIENT"
INCIDENT_EVIDENCE_INCOMPLETE = "INCIDENT_EVIDENCE_INCOMPLETE"
NEAR_MISS_REVIEW_REQUIRED = "NEAR_MISS_REVIEW_REQUIRED"
SAFETY_IMPACT_UNRESOLVED = "SAFETY_IMPACT_UNRESOLVED"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
UNKNOWN_TREATED_AS_LOW = "UNKNOWN_TREATED_AS_LOW"
TAIL_RISK_NOT_CALIBRATED = "TAIL_RISK_NOT_CALIBRATED"
EXTERNAL_CONTENT_AS_AUTHORITY = "EXTERNAL_CONTENT_AS_AUTHORITY"
SELF_REPORT_AS_SOLE_ORACLE = "SELF_REPORT_AS_SOLE_ORACLE"


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
    """`valid` iff no P0 and no P1 remain open — no average safety score can hide
    critical debt (§12.2, D-0005-78, INV-0005-10)."""

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
