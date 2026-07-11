"""Typed model + constants for the Semantic Constitution.

Epistemic types, world assumptions, relationship types, compatibility classes,
concept/epoch lifecycles, quarantine states, and the Finding type. Hard gates
stay Boolean (P0/P1); advisory signals (P2) never override them (INV-0002-04).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- severities -------------------------------------------------------------
P0, P1, P2 = "P0", "P1", "P2"

# --- epistemic type system (D-0002-07) — a STATUS lattice, not a truth ladder
EPISTEMIC_TYPES = [
    "SIGNAL", "OBSERVATION", "CLAIM", "CORROBORATED_CLAIM",
    "ADMITTED_FACT", "DERIVED_CONCLUSION", "CERTIFIED_CONCLUSION",
]
# allowed promotions (D-0002-07 / §11.10). LLM output enters only as CLAIM.
EPISTEMIC_TRANSITIONS = {
    "SIGNAL": {"OBSERVATION"},
    "OBSERVATION": {"CLAIM"},
    "CLAIM": {"CORROBORATED_CLAIM"},
    "CORROBORATED_CLAIM": {"ADMITTED_FACT"},
    "ADMITTED_FACT": {"DERIVED_CONCLUSION"},
    "DERIVED_CONCLUSION": {"CERTIFIED_CONCLUSION"},
    "CERTIFIED_CONCLUSION": set(),
}
# epistemic status is orthogonal to these quantities (D-0002-08, never collapse)
EPISTEMIC_QUANTITIES = ["confidence", "source_reliability", "evidence_strength",
                        "truth_degree"]

# --- world assumptions (D-0002-09) -----------------------------------------
WORLD_ASSUMPTIONS = {"OPEN_WORLD", "CLOSED_WORLD", "PARTIAL_WORLD"}

# --- concept kinds ----------------------------------------------------------
CONCEPT_KINDS = {"ENTITY", "EVENT", "STATE", "RELATION", "PREDICATE",
                 "QUANTITY", "ROLE", "ARTIFACT", "STATUS"}

# --- typed semantic relationships (D-0002-11) — no free-form edges ----------
RELATIONSHIP_TYPES = {"IS_A", "PART_OF", "SPECIALIZES", "SUPERSEDES",
                      "CONTRADICTS", "REQUIRES", "PRODUCES", "SATISFIES",
                      "PRECEDES", "PROJECTS_TO"}

# --- compatibility algebra (D-0002-12) -------------------------------------
COMPATIBILITY_CLASSES = {"EQUIVALENT", "NARROWING", "WIDENING",
                         "BACKWARD_COMPATIBLE", "FORWARD_COMPATIBLE",
                         "CONDITIONALLY_COMPATIBLE", "INCOMPATIBLE", "UNKNOWN",
                         "REVIEW_REQUIRED"}
BREAKING_COMPATIBILITY = {"WIDENING", "INCOMPATIBLE"}

# --- lifecycles -------------------------------------------------------------
CONCEPT_STATES = {"PROPOSED", "REVIEWED", "ACTIVE", "DEPRECATED", "RETIRED",
                  "REJECTED"}
EPOCH_STATES = {"DRAFT", "VALIDATING", "SHADOW", "REPLAYED", "APPROVED",
                "ACTIVE", "SUPERSEDED", "REJECTED"}
QUARANTINE_STATES = {"QUARANTINED", "RESOLVED_EXISTING_CONCEPT",
                     "ADMITTED_NEW_CONCEPT", "REJECTED"}

# --- finding / failure kinds (SP0002 §18) ----------------------------------
UNKNOWN_CONCEPT = "UNKNOWN_CONCEPT"
AMBIGUOUS_CONCEPT = "AMBIGUOUS_CONCEPT"
DUPLICATE_CONCEPT_ID = "DUPLICATE_CONCEPT_ID"
DUPLICATE_CANONICAL_KEY = "DUPLICATE_CANONICAL_KEY"
UNKNOWN_OWNER = "UNKNOWN_OWNER"
INVALID_RELATIONSHIP = "INVALID_RELATIONSHIP"
INVALID_EPISTEMIC_TRANSITION = "INVALID_EPISTEMIC_TRANSITION"
MEANING_HASH_MISMATCH = "MEANING_HASH_MISMATCH"
SEMANTIC_EPOCH_MISMATCH = "SEMANTIC_EPOCH_MISMATCH"
BREAKING_CHANGE_WITHOUT_EPOCH = "BREAKING_CHANGE_WITHOUT_EPOCH"
PARTIAL_SEMANTIC_TRANSACTION = "PARTIAL_SEMANTIC_TRANSACTION"
UNMAPPED_PROJECTION = "UNMAPPED_PROJECTION"
LGGT_MAPPING_COLLISION = "LGGT_MAPPING_COLLISION"
TRANSLATION_SEMANTIC_CONFLICT = "TRANSLATION_SEMANTIC_CONFLICT"
HISTORICAL_REPLAY_DIVERGENCE = "HISTORICAL_REPLAY_DIVERGENCE"
SEMANTIC_QUARANTINE_REQUIRED = "SEMANTIC_QUARANTINE_REQUIRED"
FORBIDDEN_ALIAS = "FORBIDDEN_ALIAS"
EXTERNAL_SEMANTIC_TAKEOVER = "EXTERNAL_SEMANTIC_TAKEOVER"
LLM_CONCEPT_ADMISSION = "LLM_CONCEPT_ADMISSION"
INVALID_LANGUAGE_TAG = "INVALID_LANGUAGE_TAG"
INVALID_WORLD_ASSUMPTION = "INVALID_WORLD_ASSUMPTION"


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    concept: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "concept": self.concept, "message": self.message,
                "detail": self.detail}


class Report:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    def counts(self) -> dict[str, int]:
        c = {P0: 0, P1: 0, P2: 0}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c

    @property
    def valid(self) -> bool:
        c = self.counts()
        return c[P0] == 0 and c[P1] == 0

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "metrics": self.metrics}
