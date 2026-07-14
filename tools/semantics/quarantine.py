"""Semantic Quarantine (SP0002 D-0002-18, §13.3).

Unknown / ambiguous / incompatible / unmapped-external structured meaning must NOT
enter authoritative state — it is quarantined, never silently guessed
(INV-0002-14). A quarantined item creates NO authority (AC-0002-50).
"""
from __future__ import annotations

from typing import Any

QUARANTINE_REASONS = {"UNKNOWN_SEMANTIC", "AMBIGUOUS_SEMANTIC",
                      "INCOMPATIBLE_SEMANTIC", "UNMAPPED_EXTERNAL_SEMANTIC"}
STATES = {"QUARANTINED", "RESOLVED_EXISTING_CONCEPT", "ADMITTED_NEW_CONCEPT",
          "REJECTED"}


def quarantine_item(term: str, reason: str, *, source: str = "unknown",
                    detail: dict | None = None) -> dict[str, Any]:
    assert reason in QUARANTINE_REASONS, reason
    return {
        "term": term,
        "reason": reason,
        "source": source,
        "state": "QUARANTINED",
        "creates_authority": False,       # INVARIANT (AC-0002-50)
        "epistemic_status": None,         # no status until admitted
        "detail": detail or {},
    }


def resolve_item(item: dict, resolution: str, *, concept_key: str | None = None
                 ) -> dict[str, Any]:
    assert resolution in STATES
    out = dict(item)
    out["state"] = resolution
    if resolution == "RESOLVED_EXISTING_CONCEPT":
        out["resolved_to"] = concept_key
    elif resolution == "ADMITTED_NEW_CONCEPT":
        out["admitted_concept"] = concept_key
    out["creates_authority"] = False      # remains true through every transition
    return out


def creates_authority(item: dict) -> bool:
    return bool(item.get("creates_authority", False))
