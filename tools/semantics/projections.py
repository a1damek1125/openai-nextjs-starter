"""Projection Compiler + Protocol Anti-Corruption Layer (SP0002 D-0002-19/20).

Canonical Meaning Contract -> deterministic projection contracts (JSON Schema /
OpenAPI / AsyncAPI / event / type / LGGT / capsule). External protocols (MCP /
A2A / OpenAPI / provider) map INBOUND through explicit adapters: external concept
-> mapping contract -> Finalis canonical concept. No direct semantic takeover
(INV-0002-09). Every standard is a PROJECTION or INTEROP ADAPTER, never authority.
"""
from __future__ import annotations

from typing import Any

from .model import Finding, P0, P2, UNMAPPED_PROJECTION, EXTERNAL_SEMANTIC_TAKEOVER

PROJECTION_TARGETS = ["json_schema", "openapi", "asyncapi", "event", "types",
                      "lggt", "capsule"]
# external protocols that are projections/adapters only — never internal authority
EXTERNAL_PROTOCOLS = {"mcp", "a2a", "openapi", "asyncapi", "cloudevents",
                      "provider", "jsonld", "skos", "shacl", "prov"}


def projection_contract(concept: dict, target: str) -> dict[str, Any]:
    """A deterministic projection contract descriptor (not a full generator)."""
    return {
        "target": target,
        "concept_id": concept["concept_id"],
        "canonical_key": concept["canonical_key"],
        "direction": "OUTBOUND_PROJECTION",
        "authority": "PROJECTION_NOT_AUTHORITY",
        "source_of_truth": "FINALIS_SEMANTIC_CONSTITUTION",
    }


def map_external(external_term: str, mapping: dict, protocol: str) -> dict[str, Any]:
    """Map an external protocol term to a canonical concept via an adapter.

    mapping: {external_term: canonical_key}. Unmapped -> quarantine, never a
    silent takeover. An external field declared 'canonical' is a takeover attempt.
    """
    protocol = protocol.lower()
    canonical = mapping.get(external_term)
    if canonical is None:
        return {"status": "UNMAPPED_EXTERNAL_SEMANTIC", "external": external_term,
                "protocol": protocol, "quarantine": True}
    return {"status": "MAPPED", "external": external_term,
            "canonical_key": canonical, "protocol": protocol,
            "direction": "INBOUND_ADAPTER", "authority": "EXTERNAL_NOT_AUTHORITY"}


def validate_projections(registry: dict) -> list[Finding]:
    """Concepts may declare projection_refs; targets must be known (advisory)."""
    out: list[Finding] = []
    for c in registry.get("concepts", []):
        for target in c.get("projection_refs", {}):
            if target not in PROJECTION_TARGETS:
                out.append(Finding(UNMAPPED_PROJECTION, P2, c["canonical_key"],
                                   f"unknown projection target {target}",
                                   {"target": target}))
    return out


def detect_takeover(external_map_entry: dict) -> list[Finding]:
    """An adapter entry that marks an external field as authoritative/canonical is
    an EXTERNAL_SEMANTIC_TAKEOVER (P0)."""
    out: list[Finding] = []
    if external_map_entry.get("authority") in ("CANONICAL", "INTERNAL_AUTHORITY") \
            or external_map_entry.get("canonical") is True:
        out.append(Finding(EXTERNAL_SEMANTIC_TAKEOVER, P0,
                           external_map_entry.get("external", "-"),
                           "external protocol field declared canonical/authority",
                           external_map_entry))
    return out
