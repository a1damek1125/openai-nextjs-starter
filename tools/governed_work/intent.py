"""Candidate Intent Envelope (SP0006 §9.1/10.1, D-0006-01).

A message, document, model interpretation, memory, or external event may create a
CANDIDATE_INTENT. It may NEVER create authority, approval, legal basis, consent,
or a capability lease (D-0006-01, INV-0006-01/04/05/06). Candidate intent is an
untrusted proposal until deterministic work admission.
"""
from __future__ import annotations

from .model import (Finding, P1, INVALID_WORK_SCHEMA, INTERPRETATION_SOURCES)
from .canon import core_hash

REQUIRED_FIELDS = ("candidate_intent_id", "tenant_id", "requester_id",
                   "source_surface")


def validate_candidate_intent(ci: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = ci.get("candidate_intent_id", "-")
    for f in REQUIRED_FIELDS:
        if not ci.get(f):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                               f"candidate intent missing {f}", {}))
    # a candidate intent is untrusted by construction — it must not carry
    # authority/approval/consent fields
    for forbidden in ("authority", "approval", "granted_capability", "consent",
                      "legal_basis"):
        if ci.get(forbidden):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                               f"candidate intent must not carry {forbidden!r} "
                               "(D-0006-01: intent is not authority)", {}))
    src = ci.get("interpretation_source", "LLM")
    if src not in INTERPRETATION_SOURCES:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                           f"unknown interpretation_source {src!r}", {}))
    return out


def new_candidate_intent(ci: dict) -> dict:
    """Return a normalized candidate intent stamped UNTRUSTED_PROPOSAL with a
    content hash. Never marks it trusted or authorized."""
    out = dict(ci)
    out.setdefault("interpretation_source", "LLM")
    out["status"] = "UNTRUSTED_PROPOSAL"
    out["raw_content_hash"] = out.get("raw_content_hash") or core_hash(
        {k: ci.get(k) for k in ("proposed_goal", "proposed_scope",
                                "proposed_constraints", "proposed_outcomes")})
    return out


def carries_authority(ci: dict) -> bool:
    """True if the candidate intent illegitimately claims authority/consent."""
    return any(ci.get(k) for k in ("authority", "approval", "granted_capability",
                                   "consent", "legal_basis"))
