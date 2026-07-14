"""Finalis Continuous Technology Sovereignty Constitution (SP0004).

Deterministic, stdlib-only technology governance: technology inventory,
strategic-IP boundaries, technology dependency graph with common-mode detection,
append-only Technology Decision Records, evidence freshness, hard-constraint /
Pareto / sensitivity / reversibility / lock-in decision analysis, capability
contracts + conformance + differential testing, shadow substitution, exit
readiness + drills, continuous technology fitness functions, protocol/deprecation
watch, survivability, supply-chain strategy, and proof-carrying decision +
substitution envelopes.

Technology-governance tooling ONLY. Product runtime must never import this
package (AC-0004-149) — it changes no product behaviour and adds no migration.
"""
from __future__ import annotations

from .model import Finding, Report, P0, P1, P2
from .validate import validate_all
from .loader import load_program
from .envelope import decision_envelope, substitution_envelope
from .observatory import snapshot

__all__ = ["Finding", "Report", "P0", "P1", "P2", "validate_all",
           "load_program", "decision_envelope", "substitution_envelope",
           "snapshot"]
