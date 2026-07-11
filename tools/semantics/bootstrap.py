"""Offline seeding: render the Canonical Concept Registry + genesis epoch JSON.

Runs OUTSIDE any gate path. Computes each concept's Meaning Hash and the genesis
Semantic Epoch. Emits registry, epoch, multilingual labels, relationships,
projections and the LGGT bridge as machine-readable artifacts under docs/semantics/.

    python -m tools.semantics.bootstrap [--write]
"""
from __future__ import annotations

import json
import os
import sys

from . import REGISTRY_SCHEMA_VERSION
from .canon import meaning_hash
from .concepts import CONCEPTS
from .epochs import registry_hash

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "semantics")
GENESIS_EPOCH = "epoch-0001-genesis"


def build_registry() -> dict:
    concepts = []
    for c in CONCEPTS:
        cc = dict(c)
        cc["meaning_hash"] = meaning_hash(cc)
        concepts.append(cc)
    concepts.sort(key=lambda c: c["concept_id"])
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "program": "FINALIS_1000",
        "sp": "SP0002",
        "twin_kind": "SEMANTIC_DOMAIN_TWIN",
        "active_epoch": GENESIS_EPOCH,
        "concepts": concepts,
    }


def build_epoch(registry: dict) -> dict:
    return {
        "semantic_epoch_id": GENESIS_EPOCH,
        "parent_epoch_id": None,
        "registry_hash": registry_hash(registry),
        "valid_from": "2026-07-11T00:00:00Z",
        "valid_until": None,
        "recorded_at": "2026-07-11T00:00:00Z",
        "status": "ACTIVE",
    }


def build_labels(registry: dict) -> dict:
    return {"schema_version": "1.0.0", "languages": ["en", "pl", "de", "es"],
            "labels": {c["canonical_key"]: c.get("labels", {})
                       for c in registry["concepts"]}}


def build_relationships(registry: dict) -> dict:
    edges = []
    for c in registry["concepts"]:
        for rel in c.get("relationships", []):
            edges.append({"from": c["canonical_key"], "type": rel["type"],
                          "to": rel["target"]})
    return {"schema_version": "1.0.0", "relationships": sorted(
        edges, key=lambda e: (e["from"], e["type"], e["to"]))}


def build_projections(registry: dict) -> dict:
    return {"schema_version": "1.0.0",
            "note": "Every standard is a PROJECTION or interop ADAPTER, never "
                    "internal semantic authority (INV-0002-09).",
            "projection_targets": ["json_schema", "openapi", "asyncapi", "event",
                                   "types", "lggt", "capsule"],
            "external_adapters": {
                "mcp": "INTEROPERABILITY_ADAPTER (ratified 2025-11-25)",
                "a2a": "INTEROPERABILITY_ADAPTER (Agent Card projection)",
                "openapi": "PROJECTION (OAS 3.2.0)", "overlay": "PROJECTION (1.1.0)",
                "asyncapi": "PROJECTION (3.0.0)", "cloudevents": "INTEROPERABILITY_ADAPTER (1.0.2)",
                "json_schema": "STRUCTURAL_ADAPTER (2020-12; schema-valid != semantic-valid)",
                "skos": "OPTIONAL_PROJECTION", "prov": "OPTIONAL_PROJECTION",
                "jsonld": "OPTIONAL_PROJECTION", "shacl12": "EXPERIMENTAL_ADAPTER_BOUNDARY (Working Draft)",
                "bcp47": "IDENTITY_PRIMITIVE (label != meaning)",
                "rfc3339": "TIME_INSTANT", "rfc9557": "TIME_ZONED_LOCAL"},
            "concept_projections": {c["canonical_key"]: c.get("projection_refs", {})
                                    for c in registry["concepts"]}}


def build_lggt_bridge(registry: dict) -> dict:
    # explicit, versioned predicate-family mappings for formalizable concepts.
    mappings = []
    families = {
        "lifecycle.completion": "completed",
        "outcome.business_outcome": "business_outcome_achieved",
        "evidence.fact": "admitted_fact",
        "evidence.claim": "asserted_claim",
        "work.owned_work": "owned_work",
        "approval.approval": "approval_granted",
    }
    by_key = {c["canonical_key"]: c for c in registry["concepts"]}
    for key, fam in families.items():
        c = by_key.get(key)
        if not c:
            continue
        mappings.append({
            "concept_id": c["concept_id"], "canonical_key": key,
            "semantic_epoch_id": GENESIS_EPOCH, "predicate_family": fam,
            "argument_types": ["subject_id:string", "tenant_id:string"],
            "world_assumption": c["world_assumption"],
            "source_admission": "requires ADMITTED_FACT or CERTIFIED_CONCLUSION",
            "rule_pack_version": "lggt-rule-pack-unbound-v0"})
    return {"schema_version": "1.0.0",
            "note": "Explicit versioned bridge; does not modify LGGT (INV-0002-15).",
            "mappings": mappings}


def _write(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str]) -> int:
    reg = build_registry()
    artifacts = {
        "FINALIS_CANONICAL_CONCEPT_REGISTRY.json": reg,
        "FINALIS_SEMANTIC_EPOCHS.json": {"epochs": [build_epoch(reg)]},
        "FINALIS_MULTILINGUAL_LABELS.json": build_labels(reg),
        "FINALIS_SEMANTIC_RELATIONSHIPS.json": build_relationships(reg),
        "FINALIS_SEMANTIC_PROJECTIONS.json": build_projections(reg),
        "FINALIS_LGGT_SEMANTIC_BRIDGE.json": build_lggt_bridge(reg),
    }
    if "--write" in argv:
        for name, obj in artifacts.items():
            _write(os.path.join(DOCS, name), obj)
        print(f"wrote {len(artifacts)} artifacts; {len(reg['concepts'])} concepts; "
              f"registry_hash={registry_hash(reg)[:16]}")
    else:
        print(json.dumps(reg, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
