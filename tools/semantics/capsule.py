"""Agent Semantic Capsule + Progressive Disclosure (SP0002 D-0002-21/22, §11.11).

Bounded, focused semantic context for an agent/worker — relevant concept IDs,
definitions, critical distinctions, forbidden confusions, world assumptions,
epistemic rules, relationships, source refs. Derived from the registry, never LLM
summarization alone (INV: repository truth). Progressive disclosure (levels 0-3)
never omits hard critical invariants (AC-0002-59).
"""
from __future__ import annotations

from typing import Any

# invariants that MUST appear in every capsule regardless of disclosure level.
CRITICAL_SEMANTIC_INVARIANTS = [
    "INV-0002-05 CLAIM != FACT.",
    "INV-0002-06 CERTIFIED CONCLUSION != EXTERNAL-WORLD TRUTH.",
    "INV-0002-07 CERTIFIED CONCLUSION != EXECUTION AUTHORITY.",
    "INV-0002-08 TRANSLATION CANNOT REDEFINE SEMANTICS.",
    "INV-0002-09 EXTERNAL PROTOCOL != INTERNAL SEMANTIC AUTHORITY.",
    "INV-0002-13 LLM OUTPUT CANNOT CREATE AUTHORITATIVE CONCEPT BY ITSELF.",
    "INV-0002-14 UNKNOWN OR AMBIGUOUS SEMANTIC -> QUARANTINE.",
]


def _by_key(registry: dict) -> dict[str, dict]:
    return {c["canonical_key"]: c for c in registry.get("concepts", [])}


def generate(registry: dict, target_keys: list[str], *,
             epoch_id: str | None = None, level: int = 3,
             lang: str = "en") -> dict[str, Any]:
    by_key = _by_key(registry)
    unknown = sorted(set(target_keys) - set(by_key))
    concepts_out = []
    forbidden_confusions: set[str] = set()
    for k in target_keys:
        c = by_key.get(k)
        if c is None:
            continue
        node: dict[str, Any] = {
            "concept_id": c["concept_id"],
            "canonical_key": c["canonical_key"],
            "definition": c["normative_definition"],
            "label": c.get("labels", {}).get(lang, c["canonical_key"]),
        }
        if level >= 1:
            node["semantic_invariants"] = c.get("semantic_invariants", [])
            node["world_assumption"] = c["world_assumption"]
            node["forbidden_aliases"] = c.get("forbidden_aliases", [])
            node["epistemic_rules"] = c.get("epistemic_rules", [])
        if level >= 2:
            node["relationships"] = c.get("relationships", [])
        if level >= 3:
            node["authority_semantics"] = c.get("authority_semantics", [])
            node["source"] = c["owner_capability"]
        concepts_out.append(node)
        forbidden_confusions.update(c.get("forbidden_aliases", []))

    return {
        "semantic_epoch_id": epoch_id,
        "disclosure_level": level,
        "language": lang,
        "concepts": concepts_out,
        "forbidden_confusions": sorted(forbidden_confusions),
        # hard critical invariants — ALWAYS included, never removable (AC-0002-59)
        "critical_invariants": list(CRITICAL_SEMANTIC_INVARIANTS),
        "unknown_concepts": unknown,
    }
