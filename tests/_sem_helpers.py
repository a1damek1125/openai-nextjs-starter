"""Shared (non-collected) helpers for Semantic Constitution tests."""
from __future__ import annotations

import copy

from tools.semantics.canon import meaning_hash


def concept(cid, key, *, kind="ENTITY", owner="crm", world="PARTIAL_WORLD",
            definition="def", invariants=None, epistemic=None, rels=None,
            labels=None, aliases=None, forbidden=None, status="ACTIVE",
            projections=None, models=None, with_hash=True):
    c = {
        "concept_id": cid, "canonical_key": key, "concept_kind": kind,
        "owner_capability": owner, "semantic_revision": 1, "status": status,
        "normative_definition": definition, "world_assumption": world,
        "epistemic_rules": epistemic or [], "semantic_invariants": invariants or [],
        "authority_semantics": [], "temporal_semantics": {}, "state_semantics": {},
        "relationships": rels or [], "labels": labels or {},
        "aliases": aliases or [], "deprecated_aliases": [],
        "forbidden_aliases": forbidden or [], "projection_refs": projections or {},
    }
    if models is not None:
        c["models"] = models
    if with_hash:
        c["meaning_hash"] = meaning_hash(c)
    return c


def registry(concepts, *, epoch="epoch-test"):
    return {"schema_version": "1.0.0", "program": "FINALIS_1000", "sp": "SP0002",
            "twin_kind": "SEMANTIC_DOMAIN_TWIN", "active_epoch": epoch,
            "concepts": copy.deepcopy(concepts)}


# owners that exist in the SP0001 twin (used so owner check passes)
REAL_OWNER = "crm"
