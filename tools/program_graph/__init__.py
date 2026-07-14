"""Finalis Program Dependency & Uncertainty Constitution (SP0003).

Deterministic, stdlib-only program-control intelligence over the Finalis 1000
development roadmap: a typed AND/OR/threshold prerequisite hypergraph, scenario
compilation, separate gate/conflict/rework/risk/evidence/temporal layers,
structural + estimate-based + Monte-Carlo criticality, dominators, minimum
cut-set resilience, value-of-information, closed-loop replanning, a Program
Digital Twin, a proof-carrying plan envelope and a drift observatory.

Program-planning tooling ONLY. Product runtime must never import this package
(AC-0003-97) — it changes no product behaviour and adds no database migration.
"""
from __future__ import annotations

from .model import Finding, Report, P0, P1, P2
from .validate import validate_program
from .registry import validate_registry, registry_hash, load_program
from .loader import load_program_bundle
from .envelope import build_envelope
from .twin import build_twin
from .drift import snapshot_vector

__all__ = [
    "Finding", "Report", "P0", "P1", "P2",
    "validate_program", "validate_registry", "registry_hash", "load_program",
    "load_program_bundle", "build_envelope", "build_twin", "snapshot_vector",
]
