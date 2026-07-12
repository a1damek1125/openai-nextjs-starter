"""Meaningful Human Oversight + Human Review Packet (SP0005 D-0005-53/54/55/56/57,
INV-0005-21).

Human approval is not automatically meaningful oversight (INV-0005-21): oversight
requires sufficient information, real reject authority, time to intervene, relevant
competence, an effective stop capability, independence where needed and manageable
load (D-0005-53). A review packet missing any required material field is
HUMAN_REVIEW_PACKET_INCOMPLETE (D-0005-55, AC-0005-127). Human approval is
context-bound and participates in the admission lease (D-0005-56).
"""
from __future__ import annotations

from .model import (Finding, P1, OVERSIGHT_DIMENSIONS, REVIEW_PACKET_FIELDS,
                    HUMAN_OVERSIGHT_INSUFFICIENT, HUMAN_REVIEW_PACKET_INCOMPLETE)

# dimensions that MUST be true for oversight to be meaningful
REQUIRED_OVERSIGHT = ("sufficient_information", "reject_authority",
                      "time_to_intervene", "relevant_competence",
                      "stop_capability")


def evaluate_oversight(oversight: dict) -> list[Finding]:
    out: list[Finding] = []
    oid = oversight.get("oversight_id", "-")
    for dim in REQUIRED_OVERSIGHT:
        if not oversight.get(dim):
            out.append(Finding(HUMAN_OVERSIGHT_INSUFFICIENT, P1, oid,
                               f"human oversight lacks {dim} — approval would not "
                               "be meaningful (INV-0005-21)", {}))
    return out


def validate_review_packet(packet: dict) -> list[Finding]:
    out: list[Finding] = []
    pid = packet.get("packet_id", "-")
    for f in REVIEW_PACKET_FIELDS:
        if packet.get(f) in (None, "", []):
            out.append(Finding(HUMAN_REVIEW_PACKET_INCOMPLETE, P1, pid,
                               f"review packet missing required field {f!r} "
                               "(AC-0005-127)", {}))
    # a packet that hides material uncertainty is incomplete
    if packet.get("hides_uncertainty"):
        out.append(Finding(HUMAN_REVIEW_PACKET_INCOMPLETE, P1, pid,
                           "review packet hides material uncertainty", {}))
    return out
