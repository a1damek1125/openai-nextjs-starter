"""Finalis Semantic Operating Constitution (SP0002).

Deterministic, repository-local semantic tooling: Canonical Concept Registry,
Meaning Contracts, Epistemic Type System, World-Assumption contracts, Semantic
Epochs (bitemporal), Meaning Hashes, Semantic Compatibility Algebra, Semantic
Change Intent, Semantic Impact Cone, Semantic Transaction, Dual-Semantics Shadow
Evaluation, Historical Semantic Replay, Semantic Quarantine, Protocol
Anti-Corruption projections, Agent Semantic Capsules, LGGT Semantic Bridge,
multilingual labels, Proof-Carrying Semantic Change Envelopes, Drift Observatory.

Hard rules (SP0002 invariants):
- Product runtime must never import this package.
- One protected concept = one immutable concept_id (INV-0002-01); one
  authoritative meaning per concept per epoch (INV-0002-02).
- label != identity; schema != meaning; claim != fact; certified != authority.
- External protocol / LLM output cannot become internal semantic authority.
- Stdlib only — RDF/SPARQL/SHACL/OpenAPI/MCP/A2A are projections/adapters, never
  mandatory dependencies or internal authority.
"""
from __future__ import annotations

VALIDATOR_VERSION = "1.0.0"
REGISTRY_SCHEMA_VERSION = "1.0.0"
ENVELOPE_VERSION = "1.0.0"

__all__ = ["VALIDATOR_VERSION", "REGISTRY_SCHEMA_VERSION", "ENVELOPE_VERSION"]
