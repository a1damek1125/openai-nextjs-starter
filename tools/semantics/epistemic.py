"""Epistemic Type System (SP0002 D-0002-07/08, §11.10).

A STATUS lattice — not a numeric truth ladder. Epistemic status is orthogonal to
confidence / source_reliability / evidence_strength / truth_degree, which are
stored separately and never collapsed into one score (D-0002-08). An LLM output
enters only as CLAIM and can never become ADMITTED_FACT without an admission
process (INV-0002-13).
"""
from __future__ import annotations

from typing import Any

from .model import (EPISTEMIC_TYPES, EPISTEMIC_TRANSITIONS, EPISTEMIC_QUANTITIES,
                    Finding, P0, P1, INVALID_EPISTEMIC_TRANSITION,
                    LLM_CONCEPT_ADMISSION)

# sources that may only enter as CLAIM (never higher) without admission
UNTRUSTED_SOURCES = {"LLM", "MODEL", "EXTERNAL_CONTENT", "PROVIDER", "MCP", "A2A"}


def is_valid_transition(frm: str, to: str) -> bool:
    return to in EPISTEMIC_TRANSITIONS.get(frm, set())


def validate_transition(frm: str, to: str, *, source: str | None = None
                        ) -> list[Finding]:
    out: list[Finding] = []
    if frm not in EPISTEMIC_TYPES or to not in EPISTEMIC_TYPES:
        out.append(Finding(INVALID_EPISTEMIC_TRANSITION, P1, "-",
                           f"unknown epistemic type in {frm}->{to}", {}))
        return out
    # an untrusted source cannot land above CLAIM by itself (INV-0002-13)
    if source and source.upper() in UNTRUSTED_SOURCES and \
            EPISTEMIC_TYPES.index(to) > EPISTEMIC_TYPES.index("CLAIM"):
        out.append(Finding(LLM_CONCEPT_ADMISSION, P0, "-",
                           f"{source} output cannot reach {to} without an admission "
                           f"process (max CLAIM)", {"source": source, "to": to}))
        return out
    if not is_valid_transition(frm, to):
        out.append(Finding(INVALID_EPISTEMIC_TRANSITION, P1, "-",
                           f"epistemic transition {frm}->{to} is not allowed",
                           {"from": frm, "to": to}))
    return out


def rank(status: str) -> int:
    return EPISTEMIC_TYPES.index(status) if status in EPISTEMIC_TYPES else -1


def distinct_from_confidence(record: dict) -> bool:
    """A record must keep epistemic_status separate from any quantity field
    (AC-0002-16/17): status is a categorical field, quantities are separate keys.
    """
    if "epistemic_status" not in record:
        return False
    # status must be a categorical epistemic type, not a number
    if not isinstance(record["epistemic_status"], str):
        return False
    # quantities, if present, are separate numeric fields — never THE status
    for q in EPISTEMIC_QUANTITIES:
        if q in record and record[q] is not None and \
                not isinstance(record[q], (int, float)):
            return False
    return True


def certified_is_not_fact(a: str, b: str) -> bool:
    """CERTIFIED_CONCLUSION and ADMITTED_FACT are distinct statuses, neither a
    numeric-greater version of the other (AC-0002-15)."""
    return {a, b} == {"CERTIFIED_CONCLUSION", "ADMITTED_FACT"} and a != b
