"""Safe derivative framework (V-E, Gap 2).

No OCR runs here; risky formats are never deeply parsed. The framework
decides what an agent may see — a lattice from DENY_RAW up to
HUMAN_RAW_VIEW_ONLY — and produces deterministic, honestly-labeled
manifests. Binary and active-content files never become agent-visible
raw content: they cap at METADATA_ONLY unless a real derivative exists.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .policy import DERIVATIVE_POLICY_VERSION

# --- access lattice (ordered; higher index = more content revealed) -----------
ACCESS_LATTICE = ["DENY_RAW", "METADATA_ONLY", "SAFE_FACTS_ONLY",
                  "REDACTED_DERIVATIVE", "FLATTENED_DERIVATIVE",
                  "HUMAN_RAW_VIEW_ONLY"]

DERIVATIVE_KINDS = {
    "METADATA_ONLY", "SAFE_TEXT_FACTS_ONLY", "SAFE_PREVIEW_PLACEHOLDER",
    "THUMBNAIL_PLACEHOLDER", "REDACTED_PLACEHOLDER", "FLATTENED_PLACEHOLDER",
    "BINARY_DERIVATIVE_NOT_AVAILABLE", "ACTIVE_CONTENT_REQUIRES_CDR",
    "OCR_REQUIRED_NOT_RUN",
}

# Text-ish types can yield real safe-fact derivatives locally; everything
# else is a placeholder until a real renderer/CDR is connected.
_TEXT_EXTENSIONS = {"txt", "csv", "eml"}
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "heic"}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class EvidenceDerivativeManifest:
    source_evidence_id: str
    derivative_kind: str
    policy_decision: str                 # ACCESS_LATTICE entry
    generated_at: str
    confidence: float = 0.0
    is_placeholder: bool = True
    active_content_removed: bool = False
    limitations: list = field(default_factory=list)
    safe_text: str = ""                  # facts only — never raw content
    manifest_hash: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def compute_hash(self) -> str:
        body = json.dumps({
            "src": self.source_evidence_id, "kind": self.derivative_kind,
            "policy": self.policy_decision, "at": self.generated_at,
            "placeholder": self.is_placeholder,
            "active_removed": self.active_content_removed,
            "safe_text": self.safe_text,
        }, sort_keys=True)
        return hashlib.sha256(body.encode()).hexdigest()


@dataclass
class EvidenceSafePreviewDecision:
    max_access: str                      # ACCESS_LATTICE cap
    kind: str
    reasons: list = field(default_factory=list)


class ActiveContentRiskClassifier:
    """Deterministic active-content flag from extension/mime, no parsing."""
    ACTIVE_EXTENSIONS = {"pdf", "docx", "xlsx", "html", "htm", "svg",
                         "pptx", "docm", "xlsm"}

    def is_active(self, *, extension: str, detected_mime: Optional[str]
                  ) -> bool:
        if extension.lower() in self.ACTIVE_EXTENSIONS:
            return True
        m = (detected_mime or "").lower()
        return any(t in m for t in ("html", "svg", "pdf",
                                    "officedocument"))


def plan_safe_preview(*, extension: str, active_content: bool,
                      has_hard_blocker: bool, has_safe_text: bool
                      ) -> EvidenceSafePreviewDecision:
    """Server-authoritative lattice cap for what an agent may see."""
    ext = (extension or "").lower()
    if has_hard_blocker:
        return EvidenceSafePreviewDecision(
            "DENY_RAW", "METADATA_ONLY",
            ["hard blocker present — no agent content beyond metadata"])
    if active_content:
        return EvidenceSafePreviewDecision(
            "METADATA_ONLY", "ACTIVE_CONTENT_REQUIRES_CDR",
            ["active-content file: needs CDR or a safe derivative or "
             "human review before any agent content"])
    if ext in _TEXT_EXTENSIONS and has_safe_text:
        return EvidenceSafePreviewDecision(
            "SAFE_FACTS_ONLY", "SAFE_TEXT_FACTS_ONLY",
            ["text file: extracted facts only (instructions suppressed)"])
    if ext in _IMAGE_EXTENSIONS:
        return EvidenceSafePreviewDecision(
            "METADATA_ONLY", "THUMBNAIL_PLACEHOLDER",
            ["image: thumbnail generation is SCAFFOLDED_ONLY — metadata "
             "only for now"])
    # Any other binary without a safe derivative → metadata only.
    return EvidenceSafePreviewDecision(
        "METADATA_ONLY", "BINARY_DERIVATIVE_NOT_AVAILABLE",
        ["binary file without a safe derivative — metadata only"])


def safe_derivative_score(*, has_hard_blocker: bool, type_confidence: float,
                          active_content_removed_confidence: float,
                          extraction_confidence: float,
                          integrity_confidence: float,
                          human_verification_confidence: float) -> float:
    """Explanatory only — cannot unlock actions; hard blocker forces 0."""
    if has_hard_blocker:
        return 0.0
    return _clamp(0.30 * _clamp(type_confidence)
                  + 0.25 * _clamp(active_content_removed_confidence)
                  + 0.20 * _clamp(extraction_confidence)
                  + 0.15 * _clamp(integrity_confidence)
                  + 0.10 * _clamp(human_verification_confidence))


def generate_manifest(ev, *, now_iso: str, has_hard_blocker: bool = False
                      ) -> EvidenceDerivativeManifest:
    """Build a deterministic derivative manifest for one evidence object.
    Only text files yield real safe-fact text; the rest are honest
    placeholders. Never returns raw binary or instruction text."""
    plan = plan_safe_preview(
        extension=ev.meta.extension, active_content=ev.meta.active_content,
        has_hard_blocker=has_hard_blocker,
        has_safe_text=any(d.kind == "safe_text" for d in ev.derivatives))
    safe_text = ""
    is_placeholder = True
    active_removed = False
    if plan.kind == "SAFE_TEXT_FACTS_ONLY":
        safe_text = next((d.text for d in ev.derivatives
                          if d.kind == "safe_text"), "")
        is_placeholder = False
    limitations = list(plan.reasons)
    if ev.meta.active_content:
        limitations.append("ACTIVE_CONTENT_REQUIRES_CDR (SCAFFOLDED_ONLY)")
    if plan.kind in ("THUMBNAIL_PLACEHOLDER", "SAFE_PREVIEW_PLACEHOLDER",
                     "BINARY_DERIVATIVE_NOT_AVAILABLE"):
        limitations.append("SCAFFOLDED_ONLY — real renderer not connected")
    m = EvidenceDerivativeManifest(
        source_evidence_id=ev.id, derivative_kind=plan.kind,
        policy_decision=plan.max_access, generated_at=now_iso,
        confidence=safe_derivative_score(
            has_hard_blocker=has_hard_blocker,
            type_confidence=1.0 if ev.meta.detected_mime else 0.5,
            active_content_removed_confidence=0.0
            if ev.meta.active_content else 1.0,
            extraction_confidence=0.8 if safe_text else 0.2,
            integrity_confidence=1.0 if ev.integrity
            and ev.integrity.valid else 0.0,
            human_verification_confidence=1.0 if ev.human_verified
            else 0.0),
        is_placeholder=is_placeholder,
        active_content_removed=active_removed,
        limitations=limitations, safe_text=safe_text)
    m.manifest_hash = m.compute_hash()
    return m
