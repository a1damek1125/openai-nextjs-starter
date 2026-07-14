"""Finalis Voice Engine — session orchestrator.

Wires: gateway (session lifecycle + consent + tenant) → ASR router →
dialogue manager (one question at a time, barge-in, handoff) → understanding
extractor → case-graph connector → audit → ActionGate (rule-based Phase-1).

Transcript-driven: a "call" is a sequence of fixture audio-chunk dicts. The
production audio path (LiveKit/Pipecat) replaces the input iterator only —
everything downstream of the ASR router stays identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..audit import AuditLog
from ..autonomy import gate
from ..certainty_core import Fact, NullAdapter
from ..models import Case, MissingItem, Promise
from ..state_machine import CaseState
from .extractor import UnderstandingExtractor
from .models import Utterance, VoiceSession
from .routers import ASRRouter, TTSRouter

DUE_TO_HOURS = {"today": 8, "tomorrow": 24, "this_week": 96, "unspecified": 48}

# Dialogue policy: what the AI asks for, one at a time, in priority order.
QUESTION_ORDER = ["address", "installation_photo", "preferred_date",
                  "device_brand"]
QUESTIONS = {
    "address": "Żeby przygotować wycenę, potrzebuję jeszcze adresu inwestycji.",
    "installation_photo": "Najlepiej, jeśli po rozmowie wyśle Pan zdjęcie "
                          "obecnej instalacji i tabliczki znamionowej.",
    "preferred_date": "Kiedy najbardziej pasowałby Panu termin?",
    "device_brand": "Jakiej marki jest obecne urządzenie? Jeśli nie ma "
                    "pewności, wystarczy zdjęcie tabliczki znamionowej.",
}
HANDOFF_LINE = "W tej sprawie najlepiej przekażę rozmowę człowiekowi."
OUT_OF_SCOPE_LINE = ("Niestety nie zajmujemy się tym zakresem usług. "
                     "Mogę przekazać kontakt do właściwej firmy.")
NO_PRICE_LINE = ("Nie chcę podawać ceny w ciemno — do rzetelnej wyceny "
                 "potrzebuję jeszcze kilku informacji.")


@dataclass
class VoiceEngineResult:
    session: VoiceSession
    output: dict[str, Any]
    case: Optional[Case] = None
    tasks: list[dict] = field(default_factory=list)


class VoiceEngine:
    def __init__(self, asr: ASRRouter, tts: TTSRouter,
                 audit: AuditLog, *, tenant_id: str,
                 existing_case: Optional[Case] = None) -> None:
        self.asr = asr
        self.tts = tts
        self.audit = audit
        self.tenant_id = tenant_id
        self.case = existing_case

    # -- session lifecycle -----------------------------------------------------
    def start_session(self, *, channel: str, language: str = "pl",
                      recording_consent: bool = False) -> VoiceSession:
        s = VoiceSession(tenant_id=self.tenant_id, channel=channel,
                         language=language,
                         case_id=self.case.id if self.case else None,
                         recording_allowed=recording_consent,
                         consent_asked=True,
                         started_at=datetime.utcnow().isoformat())
        s.status = "active"
        self.audit.append(event_type="CALL_STARTED", actor="system",
                          case_id=s.case_id,
                          payload={"voice_session_id": s.id,
                                   "channel": channel,
                                   "recording_allowed": s.recording_allowed})
        greeting = ("Dzień dobry, tu asystent firmy. W czym mogę pomóc?")
        self._say(s, greeting)
        return s

    def _say(self, s: VoiceSession, text: str) -> None:
        self.tts.speak(text, s.language)
        s.utterances.append(Utterance(voice_session_id=s.id, speaker="ai",
                                      text=text, language=s.language))

    # -- main loop over fixture audio chunks ------------------------------------
    def run_call(self, s: VoiceSession, audio_chunks: list[dict]
                 ) -> VoiceEngineResult:
        extractor = UnderstandingExtractor(s.id, s.case_id)
        asked: list[str] = []

        for chunk in audio_chunks:
            # Barge-in: client speaks while TTS is active → stop immediately.
            if chunk.get("barge_in") and self.tts.speaking:
                self.tts.stop()
                self.audit.append(event_type="BARGE_IN", actor="client",
                                  case_id=s.case_id,
                                  payload={"voice_session_id": s.id})
            tc = self.asr.transcribe(chunk)
            utt = Utterance(voice_session_id=s.id, speaker="client",
                            text=tc.text, confidence=tc.confidence,
                            language=tc.language,
                            is_interruption=bool(chunk.get("barge_in")),
                            uncertain_terms=tc.uncertain_terms,
                            start_ms=tc.start_ms, end_ms=tc.end_ms)
            s.utterances.append(utt)
            extractor.process(utt)
            self.tts.speaking = False  # end of AI turn either way

            u = extractor.u
            # Hard stops first: handoff and out-of-scope end the AI's script.
            if u.handoff_triggers:
                self._handoff(s, u.handoff_triggers[0])
                break
            if u.out_of_scope and not u.service_type:
                self._say(s, OUT_OF_SCOPE_LINE)
                break
            if u.price_asked_without_data and extractor.missing_items():
                self._say(s, NO_PRICE_LINE)
                u.price_asked_without_data = False   # answered once
            # One question at a time, only for still-missing items.
            missing_types = {m["type"] for m in extractor.missing_items()}
            next_q = next((q for q in QUESTION_ORDER
                           if q in missing_types and q not in asked), None)
            if next_q:
                self._say(s, QUESTIONS[next_q])
                asked.append(next_q)

        return self._end_session(s, extractor)

    def _handoff(self, s: VoiceSession, reason: str) -> None:
        s.human_handoff_requested = True
        s.handoff_reason = reason
        s.status = "handed_off"
        self._say(s, HANDOFF_LINE)
        self.audit.append(event_type="HUMAN_HANDOFF", actor="ai",
                          case_id=s.case_id,
                          payload={"voice_session_id": s.id, "reason": reason})

    # -- session end: case update + required JSON output -------------------------
    def _end_session(self, s: VoiceSession,
                     extractor: UnderstandingExtractor) -> VoiceEngineResult:
        u = extractor.u
        if u.intent:
            self.audit.append(event_type="INTENT_DETECTED", actor="ai",
                              case_id=s.case_id,
                              payload={"voice_session_id": s.id,
                                       "intent": u.intent,
                                       "confidence": u.intent_confidence})

        # Case create/update (Case Graph connector).
        tasks: list[dict] = []
        if self.case is None and u.intent and not u.out_of_scope:
            self.case = Case(tenant_id=self.tenant_id, autonomy_level=3,
                             state=CaseState.NEW_CONTACT)
            s.case_id = self.case.id
            self.audit.append(event_type="case.created", actor="ai",
                              case_id=self.case.id,
                              payload={"source": "voice",
                                       "voice_session_id": s.id})
        case = self.case

        missing = extractor.missing_items()
        if missing:
            self.audit.append(event_type="MISSING_INFO_DETECTED", actor="ai",
                              case_id=s.case_id,
                              payload={"items": [m["type"] for m in missing]})
        if case is not None:
            for m in missing:
                case.missing_items.append(MissingItem(
                    field_key=m["type"], label=m["type"],
                    weight=0.9 if m["severity"] == "high" else 0.5,
                    blocks_quote=(m["blocks"] == "quote_preparation")))
            for p in u.promises:
                from datetime import timedelta
                case.promises.append(Promise(
                    promisor=p["who"], what=p["what"],
                    due_at=datetime.utcnow()
                    + timedelta(hours=DUE_TO_HOURS[p["due"]]),
                    importance=0.7, dependency_impact=0.8))
                self.audit.append(event_type="PROMISE_DETECTED", actor="ai",
                                  case_id=case.id, payload=p)
                if p["what"] == "send photos":
                    tasks.append({"type": "followup_if_no_photos",
                                  "due": p["due"],
                                  "channel": "sms_or_whatsapp"})

        # Next action via rule-based ActionGate (autonomy) — Phase-1 LGGT seam.
        next_action = self._next_action(s, u, missing, case)

        # Summary (template MVP; LLM later) — only asserts known facts.
        s.summary = self._summary(u, missing)
        s.status = s.status if s.status == "handed_off" else "ended"
        s.ended_at = datetime.utcnow().isoformat()
        self.audit.append(event_type="CALL_ENDED", actor="system",
                          case_id=s.case_id,
                          payload={"voice_session_id": s.id,
                                   "status": s.status})

        # Certainty seam: stamp the session output.
        certainty = NullAdapter(self.audit)
        facts = [Fact(key=k, value=fv.value, evidence_ref_id=None,
                      confidence=fv.confidence)
                 for k, fv in (("client_name", u.client_name),
                               ("address", u.address),
                               ("preferred_date", u.preferred_date),
                               ("device_brand", u.device_brand))]
        cert = certainty.certify(f"voice_session:{s.id}", facts,
                                 policy_version="hvac-playbook-v1")

        output = self._build_output(s, u, missing, next_action, cert.audit_id)
        s.metrics.intent_confidence = u.intent_confidence
        s.metrics.extraction_confidence = min(
            (f.confidence for f in facts if f.value is not None), default=0.0)
        return VoiceEngineResult(session=s, output=output, case=case,
                                 tasks=tasks)

    def _next_action(self, s: VoiceSession, u, missing, case) -> dict:
        if s.human_handoff_requested:
            action = {"type": "human_callback", "channel": "phone",
                      "requires_human_approval": True}
        elif u.out_of_scope and not u.service_type:
            action = {"type": "close_out_of_scope", "channel": None,
                      "requires_human_approval": False}
        elif any(m["type"] == "installation_photo" for m in missing):
            action = {"type": "send_photo_request",
                      "channel": "sms_or_whatsapp",
                      "requires_human_approval": False}
            if case is not None:
                g = gate(case, "send_missing_info_request")
                action["requires_human_approval"] = not g.allowed
        elif missing:
            action = {"type": "send_missing_info_request",
                      "channel": "sms_or_whatsapp",
                      "requires_human_approval": False}
        else:
            action = {"type": "prepare_quote", "channel": None,
                      "requires_human_approval": False}
        self.audit.append(event_type="NEXT_ACTION_CREATED", actor="ai",
                          case_id=s.case_id, payload=action)
        if case is not None:
            case.next_best_action = action
            from datetime import timedelta
            case.next_action_due_at = datetime.utcnow() + timedelta(hours=4)
        return action

    @staticmethod
    def _summary(u, missing) -> str:
        parts = []
        if u.service_type:
            parts.append(f"Client requested {u.service_type.replace('_', ' ')}.")
        elif u.intent:
            parts.append(f"Client intent: {u.intent}.")
        if missing:
            parts.append("Missing: "
                         + ", ".join(m["type"] for m in missing) + ".")
        for p in u.promises:
            parts.append(f"Client promised to {p['what']} ({p['due']}).")
        if u.handoff_triggers:
            parts.append(f"Handed off to human ({u.handoff_triggers[0]}).")
        return " ".join(parts) or "No actionable request detected."

    def _build_output(self, s: VoiceSession, u, missing, next_action,
                      audit_id: str) -> dict:
        return {
            "voice_session_id": s.id,
            "tenant_id": s.tenant_id,
            "case_id": s.case_id,
            "language": u.language,
            "languages_detected": sorted(u.languages_detected),
            "intent": u.intent,
            "case_type": u.case_type,
            "client": {
                "name": u.client_name.value,
                "name_status": u.client_name.status,
                "phone": None,          # from channel metadata in production
                "preferred_channel": "phone",
            },
            "service": {
                "type": u.service_type,
                "urgency": u.urgency,
                "address": u.address.value if u.address.status == "confirmed"
                           else None,
                "address_status": u.address.status,
                "preferred_date": u.preferred_date.value
                                  if u.preferred_date.status == "confirmed"
                                  else None,
                "device_brand": u.device_brand.as_dict(),
            },
            "missing_items": missing,
            "promises": u.promises,
            "objections": u.objections,
            "risks": (["client_refused_address"] if u.address_refused else []),
            "next_action": next_action,
            "human_review_required": s.human_handoff_requested,
            "handoff_reason": s.handoff_reason,
            "returning_client_reference": u.returning_client_reference,
            "summary": s.summary,
            "certainty_audit_id": audit_id,
            "audit_events": [e.event_type for e in self.audit.events()
                             if (e.payload or {}).get("voice_session_id")
                             == s.id or e.case_id == s.case_id],
        }
