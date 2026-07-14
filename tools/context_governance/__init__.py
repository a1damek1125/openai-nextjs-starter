"""FINALIS Sovereign Context Governance Vault — reference kernel (TOOL-B10 V3).

A deterministic, standard-library-only kernel that transforms heterogeneous
information into point-in-time, least-privilege, proof-carrying Context Capsules
that INFORM but NEVER AUTHORIZE work. Nothing here opens a live external effect,
executes a tool, mutates a product database, or emits secret material; the product
runtime under ``finalis/`` never imports it.

Public surface:
  canon        deterministic canonical JSON / SHA-256 / Merkle forest
  model        closed vocabulary, four-valued lattice, Finding/Report
  entitlement  entitlement graph, snapshot, lease, TOCTOU, cache
  evidence     evidence-first store, paraconsistent claims, taint, air-gap
  requirements requirement hypergraph, minimal bases, selection, statistics
  compile      compaction, branch/merge, views, privacy, ABI, receipts
  capsule      capsule + BOM + certificate + independent checker + replay
  governance   build_capsule end-to-end orchestrator
  boundary     live-effect firewall
  validate     invariant self-check
"""
from __future__ import annotations

CLASSIFICATION = "FINALIS_SOVEREIGN_CONTEXT_GOVERNANCE_V3"
KERNEL_ID = "TOOL-B10"
KERNEL_VERSION = "3.0.0"

from . import (canon, model, entitlement, evidence, requirements, compile,
               capsule, governance, boundary, validate)  # noqa: E402,F401

__all__ = ["canon", "model", "entitlement", "evidence", "requirements",
           "compile", "capsule", "governance", "boundary", "validate",
           "CLASSIFICATION", "KERNEL_ID", "KERNEL_VERSION"]
