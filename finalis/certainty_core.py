"""LGGT / Finalis Certainty Core — Phase-1 placeholder (docs/finalis-ai/32).

MVP ships the SEAM, not the runtime: every gated decision passes through a
`CertaintyCoreAdapter`. The `NullAdapter` stamps decisions with a heuristic-
mode certificate carrying an `audit_id`, so all decision data is stored in an
LGGT-compatible shape from day one. Phase 2 swaps in the real runtime behind
the same interface.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Fact:
    """LGGT-compatible fact record (FactBuilder output)."""
    key: str
    value: Any
    evidence_ref_id: str | None
    confidence: float


@dataclass
class Certificate:
    """LGGTCertificate placeholder schema (doc 32)."""
    decision_ref: str
    facts: list[Fact]
    policy_version: str
    verdict: str            # certified | heuristic | abstained
    confidence: float
    audit_id: str
    proof_blob: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class CertaintyCoreAdapter(Protocol):
    def certify(self, decision_ref: str, facts: list[Fact],
                policy_version: str) -> Certificate: ...


def build_facts(fields) -> list[Fact]:
    """FactBuilder: normalize ExtractedFields into LGGT-compatible facts."""
    return [Fact(key=f.field_key, value=f.field_value,
                 evidence_ref_id=getattr(f, "id", None),
                 confidence=f.confidence) for f in fields]


class NullAdapter:
    """Phase-1: pass-through that stamps `mode=heuristic` + audit_id."""

    def __init__(self, audit) -> None:
        self.audit = audit

    def certify(self, decision_ref: str, facts: list[Fact],
                policy_version: str) -> Certificate:
        conf = min((f.confidence for f in facts), default=1.0)
        ev = self.audit.append(event_type="certainty.stamped", actor="system",
                               payload={"decision_ref": decision_ref,
                                        "mode": "heuristic",
                                        "n_facts": len(facts)})
        return Certificate(decision_ref=decision_ref, facts=facts,
                           policy_version=policy_version,
                           verdict="heuristic", confidence=conf,
                           audit_id=ev.id)
