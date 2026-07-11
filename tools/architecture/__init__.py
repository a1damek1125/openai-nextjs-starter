"""Finalis 1000 — Architecture Immune System (SP0001).

Deterministic, repository-local architecture tooling: Digital Twin (declared +
observed), diff-aware conformance gate, spec-code drift gate, change impact cone,
drift observatory, semantic duplication candidate detector, agent context spine,
and proof-carrying change envelopes.

Hard rules (SP0001 invariants):
- This package inspects product code; product code MUST NOT import this package
  (INV-0001-09: architecture tooling is never product runtime authority).
- Stdlib only — no mandatory external dependency (OPA/CodeQL/Tree-sitter stay
  behind ScannerAdapter boundaries for future adoption; D-0001-15/16).
- Same repository tree + same manifest => same semantic result (INV-0001-12).
"""
from __future__ import annotations

VALIDATOR_VERSION = "1.0.0"
TWIN_SCHEMA_VERSION = "2.0.0"
ENVELOPE_VERSION = "1.0.0"

__all__ = ["VALIDATOR_VERSION", "TWIN_SCHEMA_VERSION", "ENVELOPE_VERSION"]
