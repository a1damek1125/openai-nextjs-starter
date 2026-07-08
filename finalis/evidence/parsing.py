"""Future Document Intelligence Router hooks — interfaces ONLY (V-A).

No OCR runs here. These enums/dataclasses reserve the seams the OCR
Router (Docling-class layout parsers, region-aware VLMs) will fill in a
later mission. Invariants set now: parser output is never a trusted
instruction; every extracted field carries confidence + source region;
low-confidence or conflicting facts require human review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DOCUMENT_PARSER_KINDS = {
    "OCR_NOT_RUN",              # V-A default — nothing executed
    "FAST_TEXT_PARSER",
    "LAYOUT_AWARE_PARSER",
    "REGION_AWARE_VLM_PARSER",
    "HUMAN_REVIEW_REQUIRED",
}


@dataclass
class ParsedField:
    """One extracted fact-candidate. Never an instruction: the value is
    data; routing/consumption happens only through EvidenceFactSet."""
    name: str
    value: str
    confidence: float
    source_region: Optional[str] = None    # page/bbox reference
    parser_kind: str = "OCR_NOT_RUN"


def fields_need_human_review(fields: list[ParsedField], *,
                             min_confidence: float = 0.6) -> bool:
    """Low confidence or conflicting values for the same field name →
    a human decides, not a score."""
    if any(f.confidence < min_confidence for f in fields):
        return True
    by_name: dict[str, set[str]] = {}
    for f in fields:
        by_name.setdefault(f.name, set()).add(f.value)
    return any(len(values) > 1 for values in by_name.values())
