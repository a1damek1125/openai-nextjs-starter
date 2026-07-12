"""Closed vocabulary for the FINALIS Context Governance kernel (TOOL-B10 §9, §13,
§16, §18, D-B6-*).

Fixes the alphabets the kernel reasons over: the FOUR-VALUED claim lattice
(SUPPORTED_ONLY / REFUTED_ONLY / BOTH / NEITHER — BOTH is not TRUE, NEITHER is
not FALSE), TOCTOU consumption verdicts, delta materiality classes, the semantic
taint lattice, view classes, consumer classes, the snapshot/lease/evidence/claim/
memory/branch/capsule/receipt/requalification state machines, the reason-code
registry, and the Finding/Report shape (valid iff zero P0 and zero P1).

Reference kernel only; never imported by product runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities --------------------------------------------------------------
P0 = "P0"
P1 = "P1"
P2 = "P2"
SEVERITIES = (P0, P1, P2)

# --- four-valued claim lattice (§9.1, D-B6-031..034) -------------------------
SUPPORTED_ONLY = "SUPPORTED_ONLY"   # (1,0)
REFUTED_ONLY = "REFUTED_ONLY"       # (0,1)
BOTH = "BOTH"                       # (1,1) — never TRUE
NEITHER = "NEITHER"                 # (0,0) — never FALSE
CLAIM_STATES4 = (SUPPORTED_ONLY, REFUTED_ONLY, BOTH, NEITHER)


def claim_state(support: bool, refute: bool) -> str:
    """Strict booleans only — a truthy string is not support (D-B6; INV-29/30)."""
    s = support is True
    r = refute is True
    if s and not r:
        return SUPPORTED_ONLY
    if r and not s:
        return REFUTED_ONLY
    if s and r:
        return BOTH
    return NEITHER


def closes_critical(state: str) -> bool:
    """A critical requirement is satisfied ONLY by SUPPORTED_ONLY (BOTH/NEITHER
    never satisfy; D-B6-032/033)."""
    return state == SUPPORTED_ONLY


# --- TOCTOU consumption verdicts (Innovation 2) ------------------------------
TOCTOU_VERDICTS = ("VALID", "VALID_WITH_NONMATERIAL_DELTA", "RECOMPILE_REQUIRED",
                   "REQUALIFICATION_REQUIRED", "BLOCKED", "UNKNOWN")

# --- delta materiality (§12.2) ----------------------------------------------
DELTA_CLASSES = ("MATERIAL_RECOMPILE", "MATERIAL_REQUALIFY",
                 "NONMATERIAL_ALLOWED", "UNKNOWN")

# --- semantic taint lattice (§9, X) — join = max severity --------------------
TAINT_LEVELS = ("UNTAINTED", "EXTERNAL", "TOOL_OUTPUT", "UNTRUSTED_DERIVED",
                "SUSPECTED_INJECTION", "QUARANTINED")
_TAINT_RANK = {t: i for i, t in enumerate(TAINT_LEVELS)}
# an UNRECOGNIZED taint label is ranked ABOVE every known level, so it can never
# be silently dropped to UNTAINTED (fail-closed; red-team fix)
_UNKNOWN_TAINT_RANK = len(TAINT_LEVELS)


def _taint_rank(t: str) -> int:
    return _TAINT_RANK.get(t, _UNKNOWN_TAINT_RANK)


def taint_join(a: str, b: str) -> str:
    """Taint join (propagation) takes the MORE severe level; an unrecognized label
    is treated as most-severe (fail-closed), and taint survives transformation
    until removal is PROVEN (D-B6-042/043/044)."""
    return a if _taint_rank(a) >= _taint_rank(b) else b


# --- channels (authority air-gap, §D-B6-022/023) -----------------------------
CHANNELS = ("INFORMATION", "AUTHORITY")

# --- view / consumer classes (§9.5) ------------------------------------------
VIEW_CLASSES = ("PLANNER_VIEW", "REASONING_MODEL_VIEW", "TOOL_GATEWAY_VIEW",
                "HUMAN_APPROVER_VIEW", "AUDITOR_VIEW", "DOWNSTREAM_AGENT_VIEW",
                "CUSTOMER_RENDER_VIEW", "MEMORY_WRITEBACK_REVIEW_VIEW")
CONSUMER_CLASSES = ("REASONING_MODEL", "PLANNER", "TOOL_GATEWAY", "AUDITOR",
                    "DOWNSTREAM_AGENT", "HUMAN_REVIEWER")

# --- truncation states (§J) --------------------------------------------------
TRUNCATION_STATES = ("NONE", "DETECTED", "UNKNOWN")

# --- basis types -------------------------------------------------------------
BASIS_TYPES = ("SUPPORT", "REFUTATION", "MISSING")

# --- independence classes ----------------------------------------------------
INDEPENDENCE = ("INDEPENDENT", "COMMON_MODE", "SINGLE_SOURCE", "UNKNOWN")

# --- languages (D-B6-103/104) ------------------------------------------------
LANGUAGES = ("PL", "EN", "DE", "ES")
CONTROL_LANGUAGE = "PL"

# --- state machines (§13) ----------------------------------------------------
SNAPSHOT_STATES = ("REQUESTED", "ENTITLEMENT_BOUND", "VERSION_VECTOR_CAPTURED",
                   "SNAPSHOT_CREATED", "LEASED", "ACTIVE", "STALE", "EXPIRED",
                   "REVOKED", "RECOMPILE_REQUIRED", "QUARANTINED")
LEASE_STATES = ("ISSUED", "ACTIVE", "REVALIDATING", "EXPIRED", "INVALIDATED",
                "MATERIAL_DELTA", "UNKNOWN_DELTA", "CONSUMED_LIMIT_REACHED")
EVIDENCE_STATES = ("DISCOVERED", "NORMALIZED", "HASHED", "PROVENANCE_BOUND",
                   "VERSIONED", "ACTIVE", "INVALID", "REVOKED", "STALE",
                   "SUPERSEDED", "QUARANTINED")
CLAIM_LIFECYCLE = ("EXTRACTED", "BITEMPORALIZED", "SUPPORT_ANALYZED",
                   "ADMISSION_PENDING", "ADMITTED", "SELECTED", "REJECTED",
                   "STALE", "SUPERSEDED", "TAINTED", "QUARANTINED")
MEMORY_STATES = ("PROPOSED", "EVIDENCE_BOUND", "LINEAGE_CHECKING",
                 "POISONING_CHECKING", "POLICY_CHECKING", "REVIEW_READY",
                 "ADMITTED", "HELD", "REJECTED", "QUARANTINED", "CONTRADICTED",
                 "EXPIRED")
BRANCH_STATES = ("CREATED", "DERIVING", "READY_TO_MERGE", "MERGE_CHECKING",
                 "MERGED", "CONFLICTED", "SCOPE_INVALID", "BASE_STALE",
                 "REJECTED")
CAPSULE_STATES = ("DRAFT", "SNAPSHOT_BOUND", "REQUIREMENTS_BOUND",
                  "MANDATORY_RESERVED", "SELECTING", "COMPACTING", "MERGING",
                  "VIEW_COMPILING", "ABI_RENDERING", "VERIFYING", "CERTIFIED",
                  "SEALED", "INCOMPLETE", "BUDGET_INSUFFICIENT", "TOCTOU_INVALID",
                  "TAINT_BLOCKED", "CONFLICT_BLOCKED", "NONINTERFERENCE_FAILED",
                  "CERTIFICATE_INVALID", "STALE", "QUARANTINED")
RECEIPT_STATES = ("PROPOSED", "VIEW_BOUND", "ABI_BOUND", "BYTES_HASHED",
                  "LEASE_REVALIDATED", "ISSUED", "CONSUMED", "TRUNCATION_DETECTED",
                  "TRUNCATION_UNKNOWN", "LEASE_INVALID", "RENDER_MISMATCH",
                  "REJECTED")

# --- reason codes / events (§16, §18) ----------------------------------------
REASON_CODES = frozenset({
    # roadmap / baseline
    "TOOL_B10_SCOPE_MISMATCH", "TOOL_B5_MISSING", "BASELINE_NOT_CLEAN",
    "BASELINE_REGRESSION_FAILED",
    # TCB / entitlement
    "CONTEXT_TCB_INCOMPLETE", "ENTITLEMENT_MISSING", "ENTITLEMENT_EXPIRED",
    "SOURCE_TENANT_MISMATCH", "SOURCE_ACCOUNT_MISMATCH", "SOURCE_PURPOSE_MISMATCH",
    # snapshot / lease / toctou / cache
    "SNAPSHOT_VERSION_MISSING", "SNAPSHOT_LEASE_MISSING", "SNAPSHOT_LEASE_EXPIRED",
    "SNAPSHOT_MATERIAL_DELTA", "SNAPSHOT_UNKNOWN_DELTA", "TOCTOU_REVALIDATION_FAILED",
    "CACHE_SCOPE_MISMATCH", "CACHE_VERSION_MISMATCH", "LEASE_REPLAY_DETECTED",
    # source / evidence / claim
    "SOURCE_UNKNOWN", "SOURCE_REVOKED", "SOURCE_VERSION_CHANGED",
    "EVIDENCE_PROVENANCE_MISSING", "EVIDENCE_TAMPERED", "CLAIM_BOTH", "CLAIM_NEITHER",
    # security / taint / memory
    "PROMPT_INJECTION_SUSPECTED", "TOOL_POISONING_SUSPECTED",
    "MEMORY_POISONING_SUSPECTED", "TAINT_REMOVAL_UNPROVEN",
    "AUTHORITY_INFERENCE_REJECTED", "MEMORY_WRITEBACK_QUARANTINED",
    # requirements / bases / selection
    "MINIMAL_SUPPORT_MISSING", "COMMON_MODE_SUPPORT_INSUFFICIENT",
    "MANDATORY_REQUIREMENT_MISSING", "CONTEXT_BUDGET_INSUFFICIENT",
    "PRIVACY_EXPOSURE_EXCEEDED", "ROBUST_UTILITY_INSUFFICIENT",
    "RETRIEVAL_VALUE_NONPOSITIVE", "MANDATORY_RETRIEVAL_STOPPED",
    # statistics
    "CALIBRATION_INVALID", "DISTRIBUTION_SHIFT_DETECTED",
    "CONFORMAL_GUARANTEE_DISABLED", "OPTIONAL_STOPPING_VIOLATION",
    # compaction
    "COMPRESSION_CLAIM_LOSS", "COMPRESSION_NEGATION_CHANGED",
    "COMPRESSION_QUANTITY_CHANGED", "COMPRESSION_SCOPE_CHANGED",
    "COMPRESSION_UNCERTAINTY_LOST", "COMPRESSION_CONTRADICTION_LOST",
    "COMPRESSION_PROVENANCE_LOST", "COMPRESSION_TAINT_STRIPPED",
    # branch / merge
    "BRANCH_BASE_MISMATCH", "MERGE_CRITICAL_CONFLICT", "MERGE_AUTHORITY_AMPLIFICATION",
    # views / abi / consumption
    "VIEW_LEAKAGE", "NONINTERFERENCE_FAILED", "ABI_VERSION_UNSUPPORTED",
    "ABI_RENDER_MISMATCH", "PROVIDER_TRUNCATION_DETECTED", "PROVIDER_TRUNCATION_UNKNOWN",
    "CONSUMPTION_RECEIPT_INVALID", "PROVIDER_TOKEN_IN_CAPSULE",
    # ctxbom / transparency / non-use
    "CTXBOM_INCOMPLETE", "TRANSPARENCY_RECEIPT_INVALID", "PROOF_OF_NON_USE_FAILED",
    # capsule / replay / requalification
    "CAPSULE_CERTIFICATE_INVALID", "CAPSULE_REPLAY_DIVERGED",
    "CAPSULE_REQUALIFICATION_REQUIRED", "GENERATOR_SELF_CERTIFICATION",
    "RESOURCE_LIMIT_REACHED", "BOUNDARY_VIOLATION", "LIVE_EFFECT_ATTEMPTED",
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
