"""Shared model for the Compatibility, Migration & Versioning Constitution
(SP0007): severities, finding kinds / reason codes (§16), contract/claim/
migration/deprecation state alphabets (§13), the compatibility dimensions and
directions (D-0007-01/02), loss dimensions (D-0007-38), and Finding/Report.

A hard-dimension failure can never be averaged away (D-0007-02, INV-0007-07);
UNKNOWN is never COMPATIBLE (INV-0007-08); a Report is valid only with zero P0
and zero P1. Governance tooling only; product runtime never imports it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities -------------------------------------------------------------
P0 = "P0"
P1 = "P1"
P2 = "P2"

# --- contract surfaces (§2.2 taxonomy, D-0007-08) ---------------------------
CONTRACT_KINDS = ("HTTP_API", "EVENT_MESSAGE", "STORED_DATA", "DB_SCHEMA",
                  "WORKFLOW_HISTORY", "SEMANTIC", "PROVIDER", "PROOF_HASH",
                  "CLI_CONFIG", "UI_PROJECTION")
STABILITY = ("EXPERIMENTAL", "BETA", "STABLE", "DEPRECATED", "RETIRED")
CRITICALITY = ("C0", "C1", "C2", "C3", "C4")

# --- version identities kept distinct (D-0007-03) ---------------------------
VERSION_IDENTITIES = ("contract_version", "implementation_version",
                      "deployment_version", "provider_version",
                      "protocol_version", "semantic_epoch", "validator_version")

# --- compatibility algebra (D-0007-01/02) -----------------------------------
COMPAT_DIMENSIONS = ("syntactic", "structural", "semantic", "behavioral",
                     "temporal", "state", "replay", "proof_hash", "security",
                     "operational")
# a failure in a hard dimension can never be averaged away (D-0007-02)
HARD_DIMENSIONS = frozenset({"semantic", "behavioral", "state", "replay",
                             "proof_hash", "security"})
COMPAT_STATES = ("COMPATIBLE", "INCOMPATIBLE", "UNKNOWN", "REVIEW_REQUIRED",
                 "NOT_APPLICABLE")
DIRECTIONS = ("NEW_PRODUCER_TO_OLD_CONSUMER", "OLD_PRODUCER_TO_NEW_CONSUMER",
              "NEW_WRITER_TO_OLD_READER", "OLD_WRITER_TO_NEW_READER")

# SP0002 semantic relations reused verbatim (D-0007-09)
SEMANTIC_RELATIONS = ("EQUIVALENT", "NARROWING", "WIDENING", "INCOMPATIBLE",
                      "REVIEW_REQUIRED")

# --- evolution policies (D-0007-16..23) -------------------------------------
UNKNOWN_FIELD_POLICIES = ("PRESERVE", "IGNORE_SAFELY", "REJECT", "QUARANTINE",
                          "REVIEW_REQUIRED")
ENUM_WORLDS = ("OPEN", "CLOSED")

# --- claim lifecycle (§13.2, D-0007-07) -------------------------------------
CLAIM_STATES = ("PROPOSED", "EVALUATING", "VERIFIED", "PARTIALLY_VERIFIED",
                "INCOMPATIBLE", "STALE", "INVALIDATED")

# --- contract version lifecycle (§13.1) -------------------------------------
VERSION_STATES = ("DRAFT", "REVIEWED", "RELEASED", "ACTIVE", "DEPRECATED",
                  "SUNSET_READY", "RETIRED")
IMMUTABLE_STATES = frozenset({"RELEASED", "ACTIVE", "DEPRECATED",
                              "SUNSET_READY", "RETIRED"})

# --- migration lifecycle (§13.3/13.4) ---------------------------------------
PLAN_STATES = ("DRAFT", "REVIEWED", "APPROVED", "EXPANDING", "MIGRATING",
               "VERIFYING", "CONTRACT_READY", "COMPLETED", "PAUSED", "FAILED",
               "ROLLBACK_READY", "ROLLING_BACK", "FORWARD_FIX_REQUIRED",
               "QUARANTINED")
STEP_STATES = ("PENDING", "RESERVED", "RUNNING", "CHECKPOINTED", "VERIFIED",
               "COMPLETED", "FAILED", "RETRYABLE", "NON_RETRYABLE",
               "ROLLED_BACK")
PHASES = ("EXPAND", "MIGRATE", "VERIFY", "CONTRACT")
REVERSIBILITY = ("REVERSIBLE", "ONE_WAY", "UNKNOWN")

# --- loss vector (D-0007-38/39) ---------------------------------------------
LOSS_DIMENSIONS = ("field_loss", "semantic_loss", "precision_loss",
                   "history_loss", "provenance_loss", "authority_loss",
                   "evidence_loss", "ordering_loss", "referential_loss")
LOSS_LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH", "TOTAL", "UNKNOWN")
# losses that no low cost / low downtime can compensate (D-0007-39)
CRITICAL_LOSS_DIMENSIONS = frozenset({"authority_loss", "evidence_loss",
                                      "provenance_loss"})

# --- deprecation lifecycle (§13.5/13.6, D-0007-57..61) -----------------------
DEPRECATION_STATES = ("PROPOSED", "ANNOUNCED", "MIGRATION_AVAILABLE",
                      "CONSUMERS_MIGRATING", "SUPPORT_WINDOW_ENDING",
                      "SUNSET_READY", "RETIRED")
SUPPORT_WINDOW_STATES = ("ACTIVE", "REVIEW_DUE", "ENDING", "EXPIRED",
                         "EXTENDED_WITH_WAIVER")

# --- fixture corpus (D-0007-29/30) ------------------------------------------
FIXTURE_KINDS = ("REQUEST", "RESPONSE", "EVENT", "STATE", "WORKFLOW_HISTORY",
                 "PROOF_ENVELOPE")
CORPUS_CLASSES = ("COMMON", "EDGE", "ADVERSARIAL", "RARE_CRITICAL",
                  "INCIDENT_REPRODUCTION")

# --- finding kinds / reason codes (§16/§18) ----------------------------------
CONTRACT_OWNER_MISSING = "CONTRACT_OWNER_MISSING"
CONTRACT_VERSION_MUTATED = "CONTRACT_VERSION_MUTATED"
BREAKING_CHANGE_DETECTED = "BREAKING_CHANGE_DETECTED"
SEMVER_MISMATCH = "SEMVER_MISMATCH"
CONSUMER_INCOMPATIBLE = "CONSUMER_INCOMPATIBLE"
UNKNOWN_CONSUMER = "UNKNOWN_CONSUMER"
COMPATIBILITY_EVIDENCE_STALE = "COMPATIBILITY_EVIDENCE_STALE"
SEMANTIC_COMPATIBILITY_REQUIRED = "SEMANTIC_COMPATIBILITY_REQUIRED"
UNKNOWN_FIELD_LOSS = "UNKNOWN_FIELD_LOSS"
RESERVED_IDENTIFIER_REUSED = "RESERVED_IDENTIFIER_REUSED"
ENUM_EVOLUTION_BREAKING = "ENUM_EVOLUTION_BREAKING"
DEFAULT_VALUE_BEHAVIOR_CHANGED = "DEFAULT_VALUE_BEHAVIOR_CHANGED"
VERSION_DOWNGRADE_DETECTED = "VERSION_DOWNGRADE_DETECTED"
EVENT_IDENTITY_CHANGED = "EVENT_IDENTITY_CHANGED"
IDEMPOTENCY_CONTRACT_CHANGED = "IDEMPOTENCY_CONTRACT_CHANGED"
WORKFLOW_REPLAY_FAILED = "WORKFLOW_REPLAY_FAILED"
PROOF_VERSION_UNREADABLE = "PROOF_VERSION_UNREADABLE"
MIGRATION_PATH_MISSING = "MIGRATION_PATH_MISSING"
MIGRATION_LOSS_UNDECLARED = "MIGRATION_LOSS_UNDECLARED"
ROUND_TRIP_FAILED = "ROUND_TRIP_FAILED"
DUAL_READ_DIVERGENCE = "DUAL_READ_DIVERGENCE"
DUAL_WRITE_DIVERGENCE = "DUAL_WRITE_DIVERGENCE"
BACKFILL_CHECKPOINT_INVALID = "BACKFILL_CHECKPOINT_INVALID"
ROLLBACK_NOT_AVAILABLE = "ROLLBACK_NOT_AVAILABLE"
LAST_SAFE_ROLLBACK_POINT_REACHED = "LAST_SAFE_ROLLBACK_POINT_REACHED"
DEPRECATION_WITH_ACTIVE_CONSUMER = "DEPRECATION_WITH_ACTIVE_CONSUMER"
SUNSET_NOT_READY = "SUNSET_NOT_READY"
COMPATIBILITY_FITNESS_DEGRADED = "COMPATIBILITY_FITNESS_DEGRADED"
CROSS_TENANT_MIGRATION_DETECTED = "CROSS_TENANT_MIGRATION_DETECTED"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
MIGRATION_CONCURRENCY_CONFLICT = "MIGRATION_CONCURRENCY_CONFLICT"
SECURITY_DOWNGRADE_BLOCKED = "SECURITY_DOWNGRADE_BLOCKED"
TRANSITIVITY_ASSUMED = "TRANSITIVITY_ASSUMED"
INVALID_COMPAT_SCHEMA = "INVALID_COMPAT_SCHEMA"
ANALYSIS_LIMIT_REACHED = "ANALYSIS_LIMIT_REACHED"
MODEL_CHECK_LIMIT_REACHED = "MODEL_CHECK_LIMIT_REACHED"


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
    compatibility finding (D-0007-02)."""

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
