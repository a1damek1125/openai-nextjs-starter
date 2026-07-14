"""Concept Resolution (SP0002 §11.1/§11.2).

Resolution priority: concept_id -> canonical_key -> active exact alias ->
namespace-qualified label -> unqualified label (candidate generation) -> QUARANTINE.
Only a deterministic UNIQUE resolution may enter authoritative state; ambiguity
or unknown => quarantine, never a guess (INV-0002-14).
"""
from __future__ import annotations

from typing import Any


class Resolver:
    def __init__(self, registry: dict) -> None:
        self.by_id: dict[str, dict] = {}
        self.by_key: dict[str, dict] = {}
        self.by_alias: dict[str, list[str]] = {}
        self.by_label: dict[str, list[str]] = {}
        self.by_tail: dict[str, list[str]] = {}
        for c in registry.get("concepts", []):
            if c.get("status") in ("RETIRED", "REJECTED"):
                continue
            self.by_id[c["concept_id"]] = c
            self.by_key[c["canonical_key"]] = c
            for a in c.get("aliases", []):
                self.by_alias.setdefault(a, []).append(c["canonical_key"])
            for tag, lab in c.get("labels", {}).items():
                self.by_label.setdefault(f"{tag}:{lab.lower()}", []).append(
                    c["canonical_key"])
                self.by_label.setdefault(lab.lower(), []).append(c["canonical_key"])
            self.by_tail.setdefault(c["canonical_key"].split(".")[-1], []).append(
                c["canonical_key"])

    def resolve(self, term: str, *, lang: str | None = None) -> dict[str, Any]:
        # 1. concept_id
        if term in self.by_id:
            return {"status": "RESOLVED", "concept_id": term,
                    "canonical_key": self.by_id[term]["canonical_key"],
                    "via": "concept_id"}
        # 2. canonical_key
        if term in self.by_key:
            return {"status": "RESOLVED",
                    "concept_id": self.by_key[term]["concept_id"],
                    "canonical_key": term, "via": "canonical_key"}
        # 3. active exact alias
        if term in self.by_alias and len(set(self.by_alias[term])) == 1:
            key = self.by_alias[term][0]
            return {"status": "RESOLVED",
                    "concept_id": self.by_key[key]["concept_id"],
                    "canonical_key": key, "via": "alias"}
        # 4. namespace-qualified label (lang:label)
        if lang:
            lk = f"{lang}:{term.lower()}"
            if lk in self.by_label and len(set(self.by_label[lk])) == 1:
                key = self.by_label[lk][0]
                return {"status": "RESOLVED",
                        "concept_id": self.by_key[key]["concept_id"],
                        "canonical_key": key, "via": "label"}
        # 5. unqualified candidates (label or key tail)
        cands = sorted(set(self.by_label.get(term.lower(), [])
                           + self.by_tail.get(term, [])
                           + self.by_alias.get(term, [])))
        if len(cands) == 1:
            return {"status": "RESOLVED",
                    "concept_id": self.by_key[cands[0]]["concept_id"],
                    "canonical_key": cands[0], "via": "unqualified"}
        if len(cands) > 1:
            return {"status": "AMBIGUOUS", "candidates": cands,
                    "quarantine": "AMBIGUOUS_SEMANTIC"}
        # 6. quarantine
        return {"status": "UNKNOWN", "quarantine": "UNKNOWN_SEMANTIC",
                "term": term}
