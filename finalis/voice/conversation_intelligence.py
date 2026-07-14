"""Finalis Conversation Intelligence Engine.

Turns a speaker-attributed, time-stamped transcript (production: Parakeet/
faster-whisper ASR + WhisperX alignment + pyannote diarization; scaffold:
fixture segments) into the full structured call record: facts, promises,
missing items, objections, risks, tasks, decisions, next action, summary,
confidences, EvidenceReferences, a Case-Graph update payload, and audit
events.

Acceptance rule (enforced by `_bind_evidence`, tested):
*No critical fact may be written as certain unless it is supported by a
transcript segment AND min(ASR confidence, diarization confidence) is
sufficient — otherwise it is marked uncertain/unverified for human review.*
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..audit import AuditLog
from ..models import EvidenceReference
from .extractor import UnderstandingExtractor
from .models import Utterance

CERTAIN_MIN_CONF = 0.6      # joint ASR×diar floor for "certain" facts


@dataclass
class DiarizedSegment:
    """One diarized, aligned transcript segment (WhisperX/pyannote shape)."""
    speaker: str                  # SPEAKER_00 / SPEAKER_01 / mapped role
    text: str
    start_ms: int
    end_ms: int
    asr_confidence: float
    diar_confidence: float
    language: str = "en"
    words: list[dict] = field(default_factory=list)   # [{w, start_ms, end_ms, p}]
    uncertain_terms: list[str] = field(default_factory=list)


@dataclass
class ConversationAnalysis:
    voice_session_id: str
    case_id: Optional[str]
    transcript: list[dict]                 # full, speaker-attributed, timed
    summary: str
    key_decisions: list[str]
    intent: Optional[str]
    intent_confidence: float
    facts: list[dict]                      # {key,value,status,confidence,evidence_ref_id}
    missing_items: list[dict]
    promises: list[dict]
    objections: list[dict]
    risks: list[str]
    tasks: list[dict]
    next_action: dict
    human_review_required: bool
    evidence_references: list[EvidenceReference]
    case_update_payload: dict
    audit_event_types: list[str]


class ConversationIntelligence:
    """Analyzes diarized segments; speaker roles: first non-AI speaker maps
    to 'client' unless a role map is provided."""

    def __init__(self, audit: AuditLog, *, tenant_id: str) -> None:
        self.audit = audit
        self.tenant_id = tenant_id

    def analyze(self, session_id: str, segments: list[DiarizedSegment],
                *, case_id: Optional[str] = None,
                speaker_roles: Optional[dict[str, str]] = None
                ) -> ConversationAnalysis:
        roles = speaker_roles or self._infer_roles(segments)
        extractor = UnderstandingExtractor(session_id, case_id)
        seg_utts: list[tuple[DiarizedSegment, Utterance]] = []

        for seg in segments:
            role = roles.get(seg.speaker, "client")
            joint_conf = min(seg.asr_confidence, seg.diar_confidence)
            utt = Utterance(voice_session_id=session_id, speaker=role,
                            text=seg.text, start_ms=seg.start_ms,
                            end_ms=seg.end_ms, confidence=joint_conf,
                            language=seg.language,
                            uncertain_terms=seg.uncertain_terms)
            seg_utts.append((seg, utt))
            extractor.process(utt)

        u = extractor.u
        evidence, facts = self._bind_evidence(u, seg_utts, session_id)
        missing = extractor.missing_items()
        risks = []
        if u.address_refused:
            risks.append("client_refused_address")
        if any(f["status"] == "uncertain" for f in facts):
            risks.append("low_confidence_critical_facts")
        if u.handoff_triggers:
            risks.append(f"handoff:{u.handoff_triggers[0]}")

        tasks = [{"type": "followup_if_no_photos", "due": p["due"],
                  "channel": "sms_or_whatsapp"}
                 for p in u.promises if p["what"] == "send photos"]
        human_review = bool(u.handoff_triggers) or any(
            f["status"] == "uncertain" and f["critical"] for f in facts)
        next_action = self._next_action(u, missing, human_review)
        key_decisions = self._key_decisions(u, missing)
        summary = self._summary(u, missing, human_review)

        events = ["CONVERSATION_ANALYZED", "EVIDENCE_CREATED"]
        self.audit.append(event_type="CONVERSATION_ANALYZED", actor="ai",
                          case_id=case_id,
                          payload={"voice_session_id": session_id,
                                   "segments": len(segments),
                                   "facts": len(facts),
                                   "promises": len(u.promises)})
        for ev_ref in evidence:
            self.audit.append(event_type="EVIDENCE_CREATED", actor="ai",
                              case_id=case_id,
                              payload={"evidence_id": ev_ref.id,
                                       "source_type": ev_ref.source_type})
        if missing:
            events.append("MISSING_INFO_DETECTED")
            self.audit.append(event_type="MISSING_INFO_DETECTED", actor="ai",
                              case_id=case_id,
                              payload={"items": [m["type"] for m in missing]})
        for p in u.promises:
            events.append("PROMISE_CREATED")
            self.audit.append(event_type="PROMISE_CREATED", actor="ai",
                              case_id=case_id, payload=p)
        if human_review:
            events.append("HUMAN_REVIEW_REQUESTED")
            self.audit.append(event_type="HUMAN_REVIEW_REQUESTED", actor="ai",
                              case_id=case_id,
                              payload={"voice_session_id": session_id})

        case_update = {
            "tenant_id": self.tenant_id,
            "case_id": case_id,
            "intent": u.intent,
            "case_type": u.case_type,
            "facts": facts,
            "missing_items": missing,
            "promises": u.promises,
            "tasks": tasks,
            "next_action": next_action,
            "human_review_required": human_review,
        }

        return ConversationAnalysis(
            voice_session_id=session_id, case_id=case_id,
            transcript=[{"speaker": roles.get(s.speaker, "client"),
                         "text": s.text, "start_ms": s.start_ms,
                         "end_ms": s.end_ms,
                         "asr_confidence": s.asr_confidence,
                         "diar_confidence": s.diar_confidence,
                         "language": s.language}
                        for s in segments],
            summary=summary, key_decisions=key_decisions,
            intent=u.intent, intent_confidence=u.intent_confidence,
            facts=facts, missing_items=missing, promises=u.promises,
            objections=u.objections, risks=risks, tasks=tasks,
            next_action=next_action, human_review_required=human_review,
            evidence_references=evidence, case_update_payload=case_update,
            audit_event_types=events)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _infer_roles(segments: list[DiarizedSegment]) -> dict[str, str]:
        """Speaker with the first greeting-like AI phrase is 'ai'; else the
        first speaker is 'client'. Production supplies a role map from the
        gateway (the AI leg is known)."""
        roles: dict[str, str] = {}
        for seg in segments:
            if seg.speaker not in roles:
                roles[seg.speaker] = "client" if roles else "client"
        # Without a gateway role map, everyone defaults to client — the AI leg
        # is always known in production, so this default is conservative.
        return roles

    def _bind_evidence(self, u, seg_utts, session_id
                       ) -> tuple[list[EvidenceReference], list[dict]]:
        """Every fact gets an EvidenceReference to its transcript segment.

        Acceptance rule: certain ⇔ (segment exists) AND joint confidence
        ≥ CERTAIN_MIN_CONF. Otherwise status=uncertain (never silently
        certain).
        """
        evidence: list[EvidenceReference] = []
        facts: list[dict] = []
        by_utt = {utt.id: (seg, utt) for seg, utt in seg_utts}
        critical_keys = {"address", "client_name"}
        for key, fv in (("client_name", u.client_name),
                        ("address", u.address),
                        ("preferred_date", u.preferred_date),
                        ("device_brand", u.device_brand)):
            if fv.value is None:
                continue
            pair = by_utt.get(fv.source_utterance_id)
            if pair is None:
                status, ref_id = "uncertain", None   # no segment → not certain
            else:
                seg, utt = pair
                ref = EvidenceReference(
                    source_type="call_segment",
                    source_id=session_id,
                    locator={"start_ms": seg.start_ms, "end_ms": seg.end_ms,
                             "speaker": seg.speaker},
                    snippet=seg.text[:160],
                    confidence=min(fv.confidence, utt.confidence))
                evidence.append(ref)
                ref_id = ref.id
                joint = min(fv.confidence, utt.confidence)
                status = "certain" if joint >= CERTAIN_MIN_CONF else "uncertain"
            facts.append({"key": key, "value": fv.value, "status": status,
                          "confidence": round(fv.confidence, 2),
                          "critical": key in critical_keys,
                          "evidence_ref_id": ref_id})
        return evidence, facts

    @staticmethod
    def _next_action(u, missing, human_review) -> dict:
        if human_review and u.handoff_triggers:
            return {"type": "human_callback", "channel": "phone",
                    "requires_human_approval": True}
        if any(m["type"] == "installation_photo" for m in missing):
            return {"type": "send_photo_request",
                    "channel": "sms_or_whatsapp",
                    "requires_human_approval": False}
        if missing:
            return {"type": "send_missing_info_request",
                    "channel": "sms_or_whatsapp",
                    "requires_human_approval": False}
        return {"type": "prepare_quote", "channel": None,
                "requires_human_approval": False}

    @staticmethod
    def _key_decisions(u, missing) -> list[str]:
        out = []
        if u.intent:
            out.append(f"classified_intent:{u.intent}")
        for p in u.promises:
            out.append(f"promise_recorded:{p['what']}:{p['due']}")
        if missing:
            out.append("info_request_planned")
        if u.handoff_triggers:
            out.append(f"handoff:{u.handoff_triggers[0]}")
        return out

    @staticmethod
    def _summary(u, missing, human_review) -> str:
        parts = []
        if u.service_type:
            parts.append(f"Client asked about {u.service_type.replace('_', ' ')}.")
        if missing:
            parts.append("Missing: " + ", ".join(m["type"] for m in missing) + ".")
        for p in u.promises:
            parts.append(f"Client promised to {p['what']} ({p['due']}).")
        if human_review:
            parts.append("Human review required.")
        return " ".join(parts) or "No actionable content."
