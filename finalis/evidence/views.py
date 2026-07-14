"""Evidence Dual-View + Causal Action Guard (V-A modern addendum).

DualView-inspired, own implementation: humans may open the original;
agents get a structurally different view that CANNOT carry raw untrusted
text (there is no field for it). The causality guard verifies that
critical actions are driven by user intent + Finalis rules — never by
document instructions — and no trust score can override that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import (EvidenceFactSet, EvidenceObject, EvidenceSymbol,
                     ExtractedFacts)


# --- dual views -----------------------------------------------------------------
@dataclass
class HumanEvidenceView:
    """For people: may reference the original document."""
    evidence_id: str
    original_filename: str
    original_reference: str              # storage key (gated download later)
    state: str
    sensitivity: str
    can_open_original: bool = True


@dataclass
class AgentEvidenceView:
    """For AI: metadata, symbols, safe/redacted derivatives, facts and
    confidence. Deliberately has NO raw-text field — raw untrusted
    content is structurally impossible to hand to an agent."""
    evidence_id: str
    evidence_type: str
    state: str
    metadata: dict
    symbols: list[EvidenceSymbol] = field(default_factory=list)
    safe_derivative_text: str = ""
    facts: Optional[ExtractedFacts] = None
    confidence: float = 0.0
    untrusted: bool = True


def human_view(ev: EvidenceObject) -> HumanEvidenceView:
    return HumanEvidenceView(
        evidence_id=ev.id, original_filename=ev.meta.original_filename,
        original_reference=ev.storage.key if ev.storage else "",
        state=ev.state, sensitivity=ev.sensitivity)


def agent_view(ev: EvidenceObject) -> AgentEvidenceView:
    """The agent-facing projection. Untrusted stays untrusted: storage
    inside Finalis never launders external content into trust."""
    safe = next((d.text for d in ev.derivatives
                 if d.kind in ("safe_text", "redacted_text")), "")
    trusted = all(s.trusted for s in ev.symbols) if ev.symbols else False
    return AgentEvidenceView(
        evidence_id=ev.id, evidence_type=ev.evidence_type, state=ev.state,
        metadata={"filename": ev.meta.original_filename,
                  "mime": ev.meta.detected_mime or ev.meta.declared_mime,
                  "size_bytes": ev.meta.size_bytes,
                  "sha256": ev.integrity.digest if ev.integrity else None,
                  "source": ev.source.kind},
        symbols=list(ev.symbols),
        safe_derivative_text=safe,
        confidence=max(0.0, 1.0 - ev.injection_risk),
        untrusted=not trusted)


def mark_symbol_human_verified(symbol: EvidenceSymbol, *,
                               purpose: str, verified_by: str
                               ) -> EvidenceSymbol:
    """The ONLY path from untrusted to (narrowly) trusted: an explicit
    human verification for one named factual purpose."""
    symbol.trusted = True
    symbol.human_verified_for = f"{purpose} (by {verified_by})"
    return symbol


# --- causal action guard --------------------------------------------------------
CRITICAL_CAUSAL_ACTIONS = {"QUOTE_SEND", "QUOTE_ACCEPT",
                           "PAYMENT_MARK_PAID", "FULFILLMENT_COMPLETED",
                           "WON_COMPLETED", "CHANGE_ORDER_APPROVAL",
                           "MESSAGE_SEND"}


@dataclass
class EvidenceActionCausalityCheck:
    action_type: str
    user_intent_reference: Optional[str]
    evidence_fact_ids: list[str] = field(default_factory=list)
    untrusted_instruction_detected: bool = False
    would_action_survive_without_untrusted_text: bool = True
    decision: str = "BLOCK"              # ALLOW | BLOCK | HUMAN_REVIEW
    reasons: list[str] = field(default_factory=list)


def causality_check(*, action_type: str,
                    user_intent_reference: Optional[str],
                    fact_set: Optional[EvidenceFactSet] = None,
                    untrusted_instruction_detected: bool = False,
                    would_action_survive_without_untrusted_text: bool = True,
                    trust_score: float = 0.0
                    ) -> EvidenceActionCausalityCheck:
    """Documents supply facts, never commands. No trust score parameter
    can flip a causality block — it exists only to prove that it can't."""
    check = EvidenceActionCausalityCheck(
        action_type=action_type,
        user_intent_reference=user_intent_reference,
        evidence_fact_ids=fact_set.symbol_ids if fact_set else [],
        untrusted_instruction_detected=untrusted_instruction_detected,
        would_action_survive_without_untrusted_text=(
            would_action_survive_without_untrusted_text))
    if action_type not in CRITICAL_CAUSAL_ACTIONS:
        check.decision = "ALLOW"
        check.reasons = ["not a causally-guarded action"]
        return check
    if untrusted_instruction_detected \
            and not would_action_survive_without_untrusted_text:
        check.decision = "BLOCK"
        check.reasons = [
            "action is causally driven by untrusted document text — "
            "documents provide facts, never commands "
            f"(trust score {trust_score} cannot override this)"]
        return check
    if not user_intent_reference:
        check.decision = "HUMAN_REVIEW"
        check.reasons = ["no user intent on record — critical actions "
                         "come from users and Finalis rules, not from "
                         "documents"]
        return check
    if untrusted_instruction_detected:
        check.decision = "HUMAN_REVIEW"
        check.reasons = ["untrusted instructions were present; the action "
                         "stands on user intent alone, but a human "
                         "confirms that"]
        return check
    check.decision = "ALLOW"
    check.reasons = ["driven by user intent + admissible facts"]
    return check
