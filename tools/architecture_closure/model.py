"""Shared vocabulary for the Architecture Assurance Closure kernel (SP0010 §13,
§16, D-0010-02/03).

Fixes the closed alphabets the closure reasons over: the FOUR-VALUED epistemic
lattice (support and refutation tracked INDEPENDENTLY — never subtracted or
averaged), the claim/defeater/evidence/seal/candidate state machines (§13), the
gap taxonomy (FUNCTION P), and the event/reason-code registry (§16/§18). Reuses
the proven Finding/Report shape: a Report is valid iff zero P0 and zero P1.

Governance tooling only; never imported by product code (INV-0010-61/62).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- severities (proven pattern) ---------------------------------------------
P0 = "P0"
P1 = "P1"
P2 = "P2"
SEVERITIES = (P0, P1, P2)

# --- four-valued epistemic lattice (D-0010-02, §11.4, §12.1) -------------------
SUPPORTED_ONLY = "SUPPORTED_ONLY"   # (support=1, refute=0) — the ONLY closing state
REFUTED_ONLY = "REFUTED_ONLY"       # (0,1)
BOTH = "BOTH"                       # (1,1) — contradiction, never PASS
NEITHER = "NEITHER"                 # (0,0) — unresolved, never PASS
EPISTEMIC_STATES = (SUPPORTED_ONLY, REFUTED_ONLY, BOTH, NEITHER)


def epistemic_state(support: bool, refute: bool) -> str:
    """(1,0)->SUPPORTED_ONLY, (0,1)->REFUTED_ONLY, (1,1)->BOTH, (0,0)->NEITHER.
    Strict booleans only — a truthy string is not True (INV-0010; §231/232)."""
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
    """A critical claim closes ONLY in SUPPORTED_ONLY (D-0010-03)."""
    return state == SUPPORTED_ONLY


# --- SCC circularity classes (FUNCTION H, §11.6) ------------------------------
SCC_CLASSES = ("ANCHORED", "UNSUPPORTED", "PARTIALLY_ANCHORED",
               "SELF_REFERENTIAL", "REVIEW_REQUIRED")

# --- claim lifecycle (§13.2) --------------------------------------------------
CLAIM_STATES = ("PROPOSED", "EVIDENCE_COLLECTING", SUPPORTED_ONLY,
                REFUTED_ONLY, BOTH, NEITHER, "STALE", "DEFEATED", "SUPERSEDED")

# --- defeater lifecycle (§13.3) + kinds ---------------------------------------
DEFEATER_STATES = ("PROPOSED", "VALIDATING", "GROUNDED", "BLOCKING",
                   "RESOLVED", "REJECTED", "STALE", "SUPERSEDED")
DEFEATER_KINDS = ("REBUTTAL", "UNDERCUT", "EVIDENCE_ATTACK",
                  "ASSUMPTION_INVALIDATION", "FRESHNESS_INVALIDATION",
                  "COMMON_MODE_REVELATION")
DEFEATER_TARGETS = ("CLAIM", "ARGUMENT", "EVIDENCE")

# --- evidence lifecycle (§13.4) -----------------------------------------------
EVIDENCE_STATES = ("OBSERVED", "VALIDATING", "CURRENT", "STALE", "SUPERSEDED",
                   "CONTRADICTED", "INVALID", "SELF_REFERENTIAL",
                   "COMMON_MODE_ONLY")

# --- closure candidate lifecycle (§13.1) --------------------------------------
CANDIDATE_STATES = (
    "DRAFT", "BASELINE_FROZEN", "INTERFACES_EXTRACTED", "HYPERGRAPH_BUILT",
    "EPISTEMIC_CLOSURE_COMPUTED", "CROSS_TWIN_VALIDATED",
    "GLOBAL_INVARIANTS_VERIFIED", "HYPERPROPERTIES_VERIFIED",
    "ASSURANCE_BUILT", "BOOTSTRAP_VERIFIED", "INDEPENDENTLY_VERIFIED",
    "SEALED", "BLOCKED", "PAUSED", "INVALIDATED", "SUPERSEDED",
    "REQUALIFICATION_REQUIRED",
)

# --- program seal lifecycle (§13.5) -------------------------------------------
SEAL_STATES = ("CANDIDATE", "VERIFIED", "SEALED", "SUPERSEDED",
               "INVALIDATED", "REQUALIFICATION_REQUIRED")

# --- independence / resilience classes (FUNCTION M) ---------------------------
RESILIENCE_CLASSES = ("SINGLE_POINT_OF_ASSURANCE", "RESILIENT_TO_ONE_DOMAIN_LOSS",
                      "RESILIENT_TO_CONFIGURED_K_LOSS", "NOT_EVALUATED",
                      "LIMIT_REACHED")
INDEPENDENCE_CLASSES = ("INDEPENDENT", "COMMON_MODE", "SELF_REFERENTIAL",
                        "UNKNOWN")

# --- counterfactual control classes (FUNCTION L) ------------------------------
CONTROL_CLASSES = ("NECESSARY", "NECESSARY_NOT_SUFFICIENT", "REDUNDANT",
                   "INEFFECTIVE", "NOT_EVALUATED")

# --- hyperproperty status (FUNCTION K) ----------------------------------------
HYPERPROPERTY_STATUS = ("PASS", "FAIL", "UNKNOWN", "LIMIT_REACHED")

# --- gap taxonomy (FUNCTION P) ------------------------------------------------
GAP_TYPES = (
    "CONSTITUTIONAL_BLOCKER", "CROSS_TWIN_CONTRADICTION",
    "ASSURANCE_EVIDENCE_GAP", "GLOBAL_INVARIANT_GAP", "IMPLEMENTATION_GAP",
    "PRODUCTION_INFRASTRUCTURE_GAP", "FIELD_VALIDATION_GAP",
    "SP0011_EVALUATION_GAP", "OPERATIONAL_GAP", "REGULATORY_REVIEW_GAP",
    "ACCEPTED_FUTURE_ENHANCEMENT",
    # V5 additions (§0): proof-carrying / dual-graph / causal / CEGAR gaps
    "PROOF_HOLE", "HYPERPROPERTY_GAP", "CONTROL_EFFECTIVENESS_GAP",
    "DUAL_GRAPH_CONFLICT", "EXTRACTION_UNGROUNDED", "CERTIFICATE_MISSING",
    "CEGAR_LIMIT", "CAUSAL_UNIDENTIFIED", "FEDERATION_DIVERGENCE",
)
# gap types that BLOCK architecture closure (the rest are production/future).
# V5: a declared-vs-real CONFLICT, a critical claim with no valid certificate
# (PROOF_HOLE / CERTIFICATE_MISSING), an ungrounded critical node, a not-
# identified critical control, and verifier-backend divergence all block.
BLOCKING_GAP_TYPES = frozenset({"CONSTITUTIONAL_BLOCKER",
                                "CROSS_TWIN_CONTRADICTION",
                                "GLOBAL_INVARIANT_GAP",
                                "DUAL_GRAPH_CONFLICT", "PROOF_HOLE",
                                "CERTIFICATE_MISSING", "EXTRACTION_UNGROUNDED",
                                "CAUSAL_UNIDENTIFIED", "FEDERATION_DIVERGENCE"})

# --- V5 classification alphabets ----------------------------------------------
# Dual-Graph conformance classes (§0, FUNCTION S): how a node in the declared
# Architecture Description Graph relates to the independently-built Repository
# Evidence Graph. CONFLICT is a hard blocker; AMBIGUOUS is fail-closed (treated
# as unresolved, never as MATCH).
DUAL_GRAPH_CLASSES = ("MATCH", "DECLARED_ONLY", "IMPLEMENTATION_ONLY",
                      "CONFLICT", "AMBIGUOUS")

# Extraction grounding (§0, FUNCTION T): a declared node either has a verifiable
# on-disk source span (GROUNDED), some spans that resolve and some that do not
# (PARTIALLY_GROUNDED), or no resolvable span (UNGROUNDED — quarantined, can
# never become hard truth).
EXTRACTION_GROUNDING = ("GROUNDED", "PARTIALLY_GROUNDED", "UNGROUNDED")

# Causal identifiability (§0, FUNCTION U): whether a control's effect on the
# protected property is causally identifiable from the structural causal model.
IDENTIFIABILITY = ("IDENTIFIED", "PARTIALLY_IDENTIFIED", "NOT_IDENTIFIED")

# CEGAR outcomes (§0, FUNCTION V): an abstract counterexample is either
# concretizable into a real violation (REAL), refuted as an abstraction artifact
# (SPURIOUS), or the refinement budget was exhausted (LIMIT_REACHED — NOT a
# pass). PROVED = the abstraction verified the property with no counterexample.
CEGAR_OUTCOMES = ("PROVED", "REAL_COUNTEREXAMPLE", "SPURIOUS_REFINED",
                  "LIMIT_REACHED")

# Certificate lifecycle (§0, FUNCTION W): a proof-carrying closure certificate.
# A solver verdict WITHOUT a VALID certificate is ADVISORY only (never closing).
CERTIFICATE_STATES = ("ISSUED", "VALID", "INVALID", "ADVISORY_ONLY", "MISSING")

# Federated backend convergence (§0, FUNCTION X)
FEDERATION_STATES = ("CONVERGED", "DIVERGED", "INSUFFICIENT_BACKENDS")

# --- cross-twin dimensions (FUNCTION I) ---------------------------------------
CROSS_TWIN_DIMENSIONS = ("identity", "semantic_epoch", "valid_time",
                         "contract_version", "ownership", "authority",
                         "tenant_scope", "effect_class")

# --- reason codes / events (§16, §18) — the closed vocabulary ------------------
REASON_CODES = frozenset({
    # roadmap / baseline
    "ROADMAP_SCOPE_MISMATCH", "PROGRAM_DEPENDENCY_BLOCKED",
    "BASELINE_NOT_CLEAN", "BASELINE_CHANGED", "BASELINE_FROZEN",
    "BASELINE_CHANGED_AFTER_FREEZE",
    # interfaces / hypergraph
    "CONSTITUTION_INTERFACE_INVALID", "ASSURANCE_HYPEREDGE_INVALID",
    "HYPEREDGE_PREMISE_MISSING", "HYPEREDGE_LIMIT_REACHED",
    # epistemic
    "CLAIM_SUPPORTED_ONLY", "CLAIM_REFUTED_ONLY", "CLAIM_BOTH",
    "CLAIM_NEITHER", "CRITICAL_CLAIM_NOT_CLOSED", "CRITICAL_CLAIM_BOTH",
    "CRITICAL_CLAIM_NEITHER", "CRITICAL_CLAIM_REFUTED",
    # defeaters
    "DEFEATER_GROUNDED", "DEFEATER_UNRESOLVED", "DEFEATER_RESOLUTION_INCOMPLETE",
    # circularity
    "UNSUPPORTED_CIRCULAR_ASSURANCE", "ANCHORED_ASSURANCE_CYCLE",
    "UNSUPPORTED_ASSURANCE_CYCLE",
    # evidence
    "EVIDENCE_SELF_REFERENCE", "EVIDENCE_COMMON_MODE_RISK", "EVIDENCE_STALE",
    "EVIDENCE_INDEPENDENCE_INSUFFICIENT", "SUPPORT_SET_LIMIT_REACHED",
    "REFUTATION_SET_LIMIT_REACHED",
    # cross-twin
    "CROSS_TWIN_CONTRADICTION", "CROSS_TWIN_IDENTITY_AMBIGUOUS",
    "PARALLEL_AUTHORITY_DETECTED", "PARALLEL_REGISTRY_DETECTED",
    # global invariants / hyperproperties
    "GLOBAL_INVARIANT_FAILED", "GLOBAL_INVARIANT_UNKNOWN",
    "TENANT_NONINTERFERENCE_FAILED", "APPROVAL_ISOLATION_FAILED",
    "CONTROL_LANGUAGE_INVARIANCE_FAILED", "PROVIDER_ACCOUNT_ISOLATION_FAILED",
    "NONINTERFERENCE_FAILED", "NONINTERFERENCE_LIMIT_REACHED",
    # counterfactual controls
    "CONTROL_NECESSITY_NOT_PROVEN", "CONTROL_SUFFICIENCY_NOT_PROVEN",
    "CONTROL_EFFECTIVENESS_UNKNOWN",
    # resilience
    "ASSURANCE_SINGLE_POINT_OF_FAILURE", "ASSURANCE_RESILIENCE_FAILED",
    "VERIFIER_COMMON_MODE_RISK",
    # bootstrap / verifier
    "BOOTSTRAP_VERIFIER_MISMATCH", "BOOTSTRAP_VERIFIER_INVALID",
    "INDEPENDENT_VERIFIER_DISAGREEMENT", "INDEPENDENT_VERIFIER_CONFLICT",
    "FROZEN_VERIFIER_MODIFIED",
    # incremental / seal
    "INCREMENTAL_FULL_MISMATCH", "ARCHITECTURE_GENOME_MISMATCH",
    "PROGRAM_SEAL_MISMATCH", "PROGRAM_SEAL_CREATED", "PROGRAM_SEAL_INVALIDATED",
    "ARCHITECTURE_REQUALIFICATION_REQUIRED",
    # gaps
    "CONSTITUTIONAL_BLOCKER_OPEN", "PRODUCTION_GAP_RECORDED",
    "SP0011_ADMISSION_READY", "SP0011_EVIDENCE_FABRICATION_REJECTED",
    # boundary / analysis
    "BOUNDARY_VIOLATION", "ANALYSIS_LIMIT_REACHED",
    # --- V5: dual-graph conformance (FUNCTION S) ---
    "DUAL_GRAPH_CONFLICT", "DUAL_GRAPH_DECLARED_ONLY",
    "DUAL_GRAPH_IMPLEMENTATION_ONLY", "DUAL_GRAPH_AMBIGUOUS",
    # --- V5: extraction uncertainty firewall (FUNCTION T) ---
    "EXTRACTION_NODE_UNGROUNDED", "EXTRACTION_SPAN_MISSING",
    "EXTRACTION_PARTIALLY_GROUNDED",
    # --- V5: trusted computing base (FUNCTION Y) ---
    "TCB_MEMBER_MISSING", "TCB_UNTRUSTED_INFLUENCE",
    # --- V5: proof-carrying certificates (FUNCTION W) ---
    "CERTIFICATE_MISSING", "CERTIFICATE_INVALID", "PROOF_HOLE",
    "SOLVER_VERDICT_ADVISORY_ONLY", "CERTIFICATE_CHECKED",
    # --- V5: causal control verification (FUNCTION U) ---
    "CONTROL_EFFECT_NOT_IDENTIFIED", "CONTROL_EFFECT_PARTIALLY_IDENTIFIED",
    # --- V5: CEGAR (FUNCTION V) ---
    "CEGAR_REAL_COUNTEREXAMPLE", "CEGAR_LIMIT_REACHED",
    # --- V5: robustness frontier (FUNCTION Z) ---
    "ASSURANCE_CUT_SINGLE", "ROBUSTNESS_LIMIT_REACHED",
    # --- V5: correction sets / repair portfolios ---
    "CORRECTION_WOULD_WEAKEN_INVARIANT", "REPAIR_REQUIRED",
    # --- V5: federated N-version verification (FUNCTION X) ---
    "FEDERATION_DIVERGENCE", "FEDERATION_INSUFFICIENT_BACKENDS",
    "FEDERATION_CONVERGED",
})


def _require(code: str) -> str:
    if code not in REASON_CODES:
        raise ValueError(f"unknown reason code {code!r}")
    return code


# --- Finding / Report ---------------------------------------------------------
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
