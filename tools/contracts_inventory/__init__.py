"""FINALIS Canonical Contract Surface Inventory (SP0008).

A deterministic, evidence-grounded, machine-queryable map of the contract
surfaces ACTUALLY implemented in the repository — real repository records, not
schemas or mocks. It populates the SP0007 Contract Registry (never a parallel
one), seals a Merkle Contract Genome, and reports its own unknowns and blind
spots honestly. Governance/analysis tooling only: it opens no external effect,
changes no product runtime, and is never imported by product code.
"""
from __future__ import annotations

__all__ = [
    "canon", "model", "discover", "detectors", "normalize", "criticality",
    "evidence", "chains", "ownership", "witnesses", "residual", "probes",
    "readiness", "genome", "negative_space", "surfaces", "envelope",
    "modelcheck", "closure", "bootstrap",
]
