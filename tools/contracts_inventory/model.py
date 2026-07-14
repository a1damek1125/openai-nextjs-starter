"""Shared vocabulary for the Canonical Contract Surface Inventory (SP0008).

This module fixes the closed alphabets the whole inventory reasons over so that
every detector, evidence claim, criticality judgement and proof envelope speaks
one language (D-0008-01/13, §12.6, §13, §16). Nothing here performs discovery or
I/O; it only defines vocabulary + the Finding/Report result shape reused from the
proven cross-mission pattern (Report is valid iff there are zero P0 and zero P1
findings).

Governance/analysis tooling only; product runtime never imports it (INV-0008-53).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# severities (proven pattern: a Report is valid iff no P0 and no P1)
# ---------------------------------------------------------------------------
P0 = "P0"   # correctness / safety violation of the inventory contract
P1 = "P1"   # a required inventory property is unmet
P2 = "P2"   # advisory / observational
SEVERITIES = (P0, P1, P2)


# ---------------------------------------------------------------------------
# surface kinds — the declared universe of contract surfaces (§2.1, §5)
# ---------------------------------------------------------------------------
# Every real repository record the inventory materializes is classified into
# exactly one of these kinds. The union is the "declared universe" against which
# negative-space verification and residual estimation reason (D-0008-30/34).
SURFACE_KINDS = (
    "HTTP_ROUTE",          # an HTTP endpoint (method+path) exposed by the portal
    "REQUEST_SHAPE",       # the request body/params a route consumes
    "RESPONSE_SHAPE",      # the response body a route produces
    "AUDIT_EVENT",         # an emitted audit event family (dotted event_type)
    "RUN_LEDGER_EVENT",    # an ai_employee run-ledger event type
    "DB_TABLE",            # a persisted table / relation (migration DDL)
    "DB_MIGRATION",        # a forward-only schema migration step
    "STATE_MACHINE",       # a workflow/lifecycle state machine
    "STATE_TRANSITION",    # a single transition within a state machine
    "PROOF_ARTIFACT",      # a hash/proof/envelope surface
    "UI_SURFACE",          # a user-facing view/component contract
    "PROVIDER_BINDING",    # an external provider/integration seam
    "CONFIG_KEY",          # a configuration / environment key
    "CLI_COMMAND",         # a command-line entry point
    "BACKGROUND_JOB",      # a scheduled / async worker surface
)
SURFACE_KIND_SET = frozenset(SURFACE_KINDS)

# effect-bearing kinds — surfaces that ARE an external/irreversible effect (the
# reachability SINKS). HTTP_ROUTE is deliberately excluded: a route is the
# ingress SOURCE that reaches effects through its handler, not an effect itself.
EFFECT_BEARING_KINDS = frozenset({
    "AUDIT_EVENT", "RUN_LEDGER_EVENT", "DB_TABLE", "DB_MIGRATION",
    "PROVIDER_BINDING", "BACKGROUND_JOB",
})


# ---------------------------------------------------------------------------
# detector diversity / common-mode classification (§7, D-0008-09/10)
# ---------------------------------------------------------------------------
# Two detectors that agree only because they share the same blind method give a
# false sense of corroboration. Diversity is graded, never assumed.
DIVERSITY_REAL = "DIVERSITY_REAL"        # independent methods, independent blind spots
DIVERSITY_PARTIAL = "DIVERSITY_PARTIAL"  # overlapping method or shared blind spot
DIVERSITY_COSMETIC = "DIVERSITY_COSMETIC"  # same method, agreement is not corroboration
DIVERSITY_LEVELS = (DIVERSITY_REAL, DIVERSITY_PARTIAL, DIVERSITY_COSMETIC)


# ---------------------------------------------------------------------------
# identity resolution outcomes (§8, D-0008-11)
# ---------------------------------------------------------------------------
MATCHED_EXISTING = "MATCHED_EXISTING"        # resolves to a known SP0007 contract
NEW_SURFACE = "NEW_SURFACE"                  # not previously registered
ALIAS_CANDIDATE = "ALIAS_CANDIDATE"          # likely another name for a known surface
DUPLICATE_CANDIDATE = "DUPLICATE_CANDIDATE"  # likely a duplicate of another surface
AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"    # cannot be resolved without a human
IDENTITY_OUTCOMES = (MATCHED_EXISTING, NEW_SURFACE, ALIAS_CANDIDATE,
                     DUPLICATE_CANDIDATE, AMBIGUOUS_IDENTITY)


# ---------------------------------------------------------------------------
# consumer-certainty typing (D-0008-13) — how well a consumer is known
# ---------------------------------------------------------------------------
STATIC_CONFIRMED = "STATIC_CONFIRMED"              # a static call/reference is present
TEST_CONFIRMED = "TEST_CONFIRMED"                  # a test exercises the surface
DECLARED = "DECLARED"                              # declared but not otherwise evidenced
HISTORICALLY_EVIDENCED = "HISTORICALLY_EVIDENCED"  # past evidence (bitemporal)
TRANSITIVE_INFERRED = "TRANSITIVE_INFERRED"        # inferred through a chain
UNKNOWN = "UNKNOWN"                                # not established — never "zero"
CONSUMER_CERTAINTY = (STATIC_CONFIRMED, TEST_CONFIRMED, DECLARED,
                      HISTORICALLY_EVIDENCED, TRANSITIVE_INFERRED, UNKNOWN)


# ---------------------------------------------------------------------------
# criticality VECTOR dimensions (§12.6) — hard flags are conjunctive, never
# averaged. A single hard flag makes a surface critical regardless of the rest.
# ---------------------------------------------------------------------------
CRITICALITY_DIMS = (
    "authority",              # governs who may act
    "tenant",                 # crosses / isolates tenants
    "data",                   # persists or exposes data
    "externality",            # reaches an external system
    "irreversibility",        # its effect cannot be undone
    "centrality",             # many surfaces depend on it
    "proof",                  # produces evidence relied on downstream
    "historical_obligation",  # carries a standing historical obligation
)
# the subset whose truth alone forces CRITICAL (hard, non-compensatory)
HARD_CRITICALITY_DIMS = frozenset({
    "authority", "tenant", "externality", "irreversibility", "proof",
    "historical_obligation",
})
CRITICALITY_LEVELS = ("CRITICAL", "ELEVATED", "STANDARD", "UNKNOWN")


# ---------------------------------------------------------------------------
# behavioral witness kinds (§ witnesses) — source-grounded, LLM candidate-only
# ---------------------------------------------------------------------------
WITNESS_KINDS = (
    "POSITIVE",       # a case the surface accepts / produces
    "NEGATIVE",       # a case the surface rejects
    "FAILURE",        # a failure/error path
    "METAMORPHIC",    # a relation between inputs/outputs
    "TENANT",         # a tenant-isolation witness
    "AUTHORITY",      # an authority-enforcement witness
)
WITNESS_OUTCOMES = ("CONFIRMED", "REFUTED", "UNKNOWN_OUTCOME")


# ---------------------------------------------------------------------------
# bitemporal / provenance vocabulary (§ evidence, D-0008-18/22)
# ---------------------------------------------------------------------------
BITEMPORAL_KEYS = ("valid_from", "valid_to", "observed_at", "superseded_at")
# W3C PROV projection
PROV_NODE_KINDS = ("ENTITY", "ACTIVITY", "AGENT")
PROV_EDGE_KINDS = ("WAS_GENERATED_BY", "USED", "WAS_ATTRIBUTED_TO",
                   "WAS_DERIVED_FROM", "WAS_INFORMED_BY")

# cut-set exactness (§ dominators / minimal cut sets)
CUT_SET_EXACTNESS = ("EXACT", "BOUNDED", "LIMIT_REACHED")


# ---------------------------------------------------------------------------
# lifecycle states of an inventoried surface record (§13)
# ---------------------------------------------------------------------------
SURFACE_STATES = (
    "DISCOVERED",     # observed by >=1 detector, not yet reconciled
    "RECONCILED",     # identity resolved against the registry
    "EVIDENCED",      # at least one grounded evidence claim attached
    "CLASSIFIED",     # criticality vector assigned
    "WITNESSED",      # behavioral witnesses attached (or NONE recorded)
    "SEALED",         # folded into the Contract Genome (Merkle)
    "CONTRADICTED",   # detectors/evidence disagree — preserved, not resolved
    "RETIRED",        # historically present, no longer observed
)


# ---------------------------------------------------------------------------
# finding / reason codes (§16). Grouped by concern; every emitted Finding.kind
# is one of these so the corpus of failures is itself a closed, queryable set.
# ---------------------------------------------------------------------------
# --- schema / structural integrity
INVALID_INVENTORY_SCHEMA = "INVALID_INVENTORY_SCHEMA"
NON_DETERMINISTIC_OUTPUT = "NON_DETERMINISTIC_OUTPUT"
GENOME_ROOT_MISMATCH = "GENOME_ROOT_MISMATCH"
PROOF_ENVELOPE_MISMATCH = "PROOF_ENVELOPE_MISMATCH"
# --- discovery / detection
DETECTOR_DISAGREEMENT = "DETECTOR_DISAGREEMENT"
DETECTOR_COMMON_MODE = "DETECTOR_COMMON_MODE"
DETECTOR_BLIND_SPOT = "DETECTOR_BLIND_SPOT"
UNCLASSIFIED_SURFACE = "UNCLASSIFIED_SURFACE"
# --- identity
AMBIGUOUS_IDENTITY_UNRESOLVED = "AMBIGUOUS_IDENTITY_UNRESOLVED"
DUPLICATE_SURFACE_SUSPECTED = "DUPLICATE_SURFACE_SUSPECTED"
PARALLEL_REGISTRY_DETECTED = "PARALLEL_REGISTRY_DETECTED"
# --- evidence / provenance
EVIDENCE_UNGROUNDED = "EVIDENCE_UNGROUNDED"
BITEMPORAL_INCONSISTENT = "BITEMPORAL_INCONSISTENT"
PROVENANCE_BROKEN = "PROVENANCE_BROKEN"
CONTRADICTION_PRESERVED = "CONTRADICTION_PRESERVED"
# --- consumers / ownership
DARK_CONSUMER = "DARK_CONSUMER"
ORPHAN_PRODUCER = "ORPHAN_PRODUCER"
OWNERSHIP_UNRESOLVED = "OWNERSHIP_UNRESOLVED"
CONSUMER_CERTAINTY_UNKNOWN = "CONSUMER_CERTAINTY_UNKNOWN"
# --- criticality
CRITICALITY_UNKNOWN = "CRITICALITY_UNKNOWN"
HARD_FLAG_UNVERIFIED = "HARD_FLAG_UNVERIFIED"
# --- chains / reachability / cut sets
EFFECT_REACHABILITY_UNKNOWN = "EFFECT_REACHABILITY_UNKNOWN"
CHAIN_BROKEN = "CHAIN_BROKEN"
CUT_SET_LIMIT_REACHED = "CUT_SET_LIMIT_REACHED"
# --- witnesses
WITNESS_UNGROUNDED = "WITNESS_UNGROUNDED"
UNKNOWN_OUTCOME_WITNESS = "UNKNOWN_OUTCOME_WITNESS"
# --- negative space / residual / coverage
NEGATIVE_SPACE_UNVERIFIED = "NEGATIVE_SPACE_UNVERIFIED"
DECLARED_UNIVERSE_INCOMPLETE = "DECLARED_UNIVERSE_INCOMPLETE"
RESIDUAL_SURFACE_ESTIMATED = "RESIDUAL_SURFACE_ESTIMATED"
# --- agent readiness (advisory; grants no authority)
AGENT_READINESS_BLOCKED = "AGENT_READINESS_BLOCKED"
# --- boundary invariants (the mission's hard change boundary)
BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"

REASON_CODES = frozenset({
    INVALID_INVENTORY_SCHEMA, NON_DETERMINISTIC_OUTPUT, GENOME_ROOT_MISMATCH,
    PROOF_ENVELOPE_MISMATCH, DETECTOR_DISAGREEMENT, DETECTOR_COMMON_MODE,
    DETECTOR_BLIND_SPOT, UNCLASSIFIED_SURFACE, AMBIGUOUS_IDENTITY_UNRESOLVED,
    DUPLICATE_SURFACE_SUSPECTED, PARALLEL_REGISTRY_DETECTED, EVIDENCE_UNGROUNDED,
    BITEMPORAL_INCONSISTENT, PROVENANCE_BROKEN, CONTRADICTION_PRESERVED,
    DARK_CONSUMER, ORPHAN_PRODUCER, OWNERSHIP_UNRESOLVED,
    CONSUMER_CERTAINTY_UNKNOWN, CRITICALITY_UNKNOWN, HARD_FLAG_UNVERIFIED,
    EFFECT_REACHABILITY_UNKNOWN, CHAIN_BROKEN, CUT_SET_LIMIT_REACHED,
    WITNESS_UNGROUNDED, UNKNOWN_OUTCOME_WITNESS, NEGATIVE_SPACE_UNVERIFIED,
    DECLARED_UNIVERSE_INCOMPLETE, RESIDUAL_SURFACE_ESTIMATED,
    AGENT_READINESS_BLOCKED, BOUNDARY_VIOLATION,
})


# ---------------------------------------------------------------------------
# Finding / Report — the proven cross-mission result shape
# ---------------------------------------------------------------------------
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

    def as_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity,
                "subject": self.subject, "message": self.message,
                "details": self.details}


@dataclass(frozen=True)
class Report:
    findings: tuple = ()

    @property
    def valid(self) -> bool:
        """Valid iff no P0 and no P1 finding (the proven pattern)."""
        return not any(f.severity in (P0, P1) for f in self.findings)

    def by_severity(self, sev: str) -> list:
        return [f for f in self.findings if f.severity == sev]

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "counts": {s: len(self.by_severity(s)) for s in SEVERITIES},
            "findings": [f.as_dict() for f in self.findings],
        }


def report(findings) -> Report:
    return Report(tuple(findings))
