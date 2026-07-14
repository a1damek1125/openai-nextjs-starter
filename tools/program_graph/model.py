"""Typed model + constants for the Program Dependency & Uncertainty Constitution.

Severities stay Boolean gates: a hard finding (P0/P1) can never be overridden by
any probabilistic score or advisory signal (INV-0003-12, P2 is advisory only).

Canonical program data (nodes, dependency contracts, gates, scenarios, conflicts,
evidence) is kept DISTINCT from derived analytics (critical path, criticality,
dominators, cut sets, forecasts, VOI) — see INV-0003-17. This module defines only
the canonical vocabulary and the Finding/Report result type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- severities -------------------------------------------------------------
P0, P1, P2 = "P0", "P1", "P2"

# --- node kinds & blocks ----------------------------------------------------
NODE_TYPES = {"SP", "MILESTONE", "GATE_NODE", "RESEARCH", "REFACTOR", "PILOT",
              "PACK", "INFRA", "DOC"}

# --- node lifecycle (D-0003 §13.2) -----------------------------------------
NODE_STATES = {"NOT_STARTED", "BLOCKED", "READY", "IN_PROGRESS", "VERIFYING",
               "COMPLETE", "PARTIAL", "SUPERSEDED", "CANCELLED"}
COMPLETE_STATES = {"COMPLETE"}
# statuses that count as "prerequisite satisfied" for a downstream dependency:
# only evidence-derived completion satisfies a hard prerequisite (D-0003-15).
SATISFYING_STATES = {"COMPLETE"}

STATUS_SOURCES = {"EVIDENCE_DERIVED", "DECLARED", "IMPORTED"}

# --- dependency logic (D-0003-01/02/03) ------------------------------------
DEPENDENCY_LOGIC = {"ALL_OF", "ANY_OF", "AT_LEAST_K_OF_N"}

# --- dependency TYPE (why) — orthogonal to logic (how), D-0003-05 ----------
DEPENDENCY_TYPES = {
    "ARCHITECTURE_PRECONDITION", "SEMANTIC_PRECONDITION", "SAFETY_PRECONDITION",
    "AUTHORITY_PRECONDITION", "TENANT_ISOLATION_PRECONDITION",
    "HUMAN_OVERSIGHT_PRECONDITION", "EXTERNAL_EFFECT_PRECONDITION",
    "PRODUCTION_READINESS_PRECONDITION", "DATA_PRECONDITION",
    "CAPABILITY_PRECONDITION", "EVALUATION_PRECONDITION",
    "TECHNOLOGY_DECISION_PRECONDITION",
}

# --- dependency lifecycle (D-0003-34 / §13.1) ------------------------------
DEPENDENCY_STATES = {"PROPOSED", "UNDER_RESEARCH", "VERIFIED", "ACTIVE",
                     "REJECTED", "DEPRECATED"}
# only ACTIVE + VERIFIED hard dependencies block canonical readiness.
BLOCKING_DEPENDENCY_STATES = {"ACTIVE"}

# --- gate kinds (D-0003-12) -------------------------------------------------
GATE_TYPES = {"ARCHITECTURE_GATE", "SAFETY_GATE", "GOVERNANCE_GATE",
              "EVALUATION_GATE", "PRODUCTION_GATE", "HUMAN_REVIEW_GATE",
              "THRESHOLD_PREREQUISITE"}
# gates that are scenario-invariant — cannot be deactivated by scenario choice
# (INV-0003-09 / §17.1). A global safety/governance gate always applies.
GLOBAL_GATE_TYPES = {"SAFETY_GATE", "GOVERNANCE_GATE", "HUMAN_REVIEW_GATE"}

# --- rework edge kinds (D-0003-10) — NEVER hard prerequisites (INV-0003-07) -
REWORK_TYPES = {"MAY_INVALIDATE", "REVERIFY_IF_CHANGED", "REWORK_TRIGGER",
                "RECALIBRATE_IF_CHANGED", "MIGRATE_IF_CHANGED"}

# --- duration model modes (D-0003-20) — UNKNOWN never becomes a fake number -
DURATION_MODES = {"UNKNOWN", "STRUCTURAL_UNIT", "EXPERT_POINT_ESTIMATE",
                  "THREE_POINT_ESTIMATE", "EMPIRICAL_DISTRIBUTION",
                  "BAYESIAN_POSTERIOR"}
# modes that carry a usable numeric duration for estimate-based CPM:
ESTIMATED_MODES = {"EXPERT_POINT_ESTIMATE", "THREE_POINT_ESTIMATE",
                   "EMPIRICAL_DISTRIBUTION", "BAYESIAN_POSTERIOR"}

# --- dependency uncertainty decision impact --------------------------------
DECISION_IMPACT = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

# --- temporal constraint kinds (D-0003-24/26) ------------------------------
TEMPORAL_TYPES = {"REQUIREMENT", "DEADLINE", "RELEASE_TIME", "OVERLAP",
                  "CONTINGENT"}

# --- scenario condition operators (D-0003-06, declarative only) ------------
CONDITION_OPERATORS = {"EQUALS", "NOT_EQUALS", "IN", "NOT_IN"}

# --- finding / failure kinds (SP0003 §16 / §18) ----------------------------
INVALID_PROGRAM_SCHEMA = "INVALID_PROGRAM_SCHEMA"
UNKNOWN_NODE = "UNKNOWN_NODE"
DUPLICATE_NODE = "DUPLICATE_NODE"
INVALID_HYPEREDGE = "INVALID_HYPEREDGE"
SELF_DEPENDENCY = "SELF_DEPENDENCY"
HARD_DEPENDENCY_CYCLE = "HARD_DEPENDENCY_CYCLE"
UNPROVEN_HARD_DEPENDENCY = "UNPROVEN_HARD_DEPENDENCY"
JOINT_PREREQUISITE_CORRUPTION = "JOINT_PREREQUISITE_CORRUPTION"
SCENARIO_COMPILATION_ERROR = "SCENARIO_COMPILATION_ERROR"
UNKNOWN_SCENARIO_VARIABLE = "UNKNOWN_SCENARIO_VARIABLE"
SCENARIO_CONDITION_ERROR = "SCENARIO_CONDITION_ERROR"
GATE_BYPASS = "GATE_BYPASS"
GATE_BYPASS_RISK = "GATE_BYPASS_RISK"
FALSE_PARALLELISM = "FALSE_PARALLELISM"
RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
REWORK_CLUSTER_DETECTED = "REWORK_CLUSTER_DETECTED"
REWORK_MODEL_ERROR = "REWORK_MODEL_ERROR"
TEMPORAL_CONSTRAINT_INCONSISTENCY = "TEMPORAL_CONSTRAINT_INCONSISTENCY"
COMPLETION_EVIDENCE_MISSING = "COMPLETION_EVIDENCE_MISSING"
INVALID_DURATION_MODEL = "INVALID_DURATION_MODEL"
INCOMPARABLE_DURATION_EVIDENCE = "INCOMPARABLE_DURATION_EVIDENCE"
DEPENDENCY_UNCERTAINTY = "DEPENDENCY_UNCERTAINTY"
FORECAST_MODEL_STALE = "FORECAST_MODEL_STALE"
VOI_NOT_CALIBRATED = "VOI_NOT_CALIBRATED"
STALE_PROGRAM_TWIN = "STALE_PROGRAM_TWIN"
ROADMAP_DRIFT = "ROADMAP_DRIFT"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
LLM_DEPENDENCY_ACTIVATION = "LLM_DEPENDENCY_ACTIVATION"
PARTIAL_PROGRAM_UPDATE = "PARTIAL_PROGRAM_UPDATE"


@dataclass(frozen=True)
class Finding:
    """A single validation finding. Severity is a hard gate for P0/P1."""
    kind: str
    severity: str          # P0 | P1 | P2
    subject: str           # node_id / dependency_id / gate_id ...
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "subject": self.subject, "message": self.message,
                "detail": self.detail}


class Report:
    """Accumulates findings. `valid` iff no P0 and no P1 remain open — a program
    plan is valid only when every hard finding is clear (INV-0003-19; a partial
    update can never be declared valid)."""

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
