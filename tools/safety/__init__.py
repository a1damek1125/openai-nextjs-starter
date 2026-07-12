"""Finalis Safety Kernel, Assurance & Regulatory Truth Constitution (SP0005).

Deterministic, stdlib-only safety governance: loss taxonomy, hazard registry with
traceability closure, threat registry, unsafe control actions (STPA), safety
constraints, control barrier graph + independence + minimal cut-sets, action &
trajectory safety contracts, trajectory automata, proof obligations, dynamic
safety state vector + non-compensatory control-class lattice, context-bound
safety admission leases + TOCTOU revalidation, independent containment, assurance
cases + coverage closure + defeater propagation, evidence freshness, regulatory
temporal truth + applicability, high-impact use cases, meaningful human oversight,
safety oracle hierarchy, bounded scenario compiler, incidents/near-misses,
reassessment + impact cone, assurance debt + drift, and proof-carrying safety-case
& safety-decision envelopes.

Safety-governance tooling ONLY. Product runtime must never import it
(AC-0005-231); it opens NO external effect (INV-0005-27) and adds no migration.
"""
from __future__ import annotations

from .model import Finding, Report, P0, P1, P2
from .validate import validate_all
from .loader import load_program
from .envelope import safety_case_envelope, safety_decision_envelope
from .debt import assurance_debt, drift_snapshot

__all__ = ["Finding", "Report", "P0", "P1", "P2", "validate_all", "load_program",
           "safety_case_envelope", "safety_decision_envelope", "assurance_debt",
           "drift_snapshot"]
