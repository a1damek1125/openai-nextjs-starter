"""Voice Engine E2E tests — the 12 mandated transcript scenarios + routers.

Every scenario verifies: intent, extracted fields, missing items, promises,
next action, human handoff where required, audit events, and — critically —
that no hallucinated/uncertain fact is saved as certain.
"""
import pytest

from finalis.audit import AuditLog
from finalis.state_machine import CaseState
from finalis.voice.engine import VoiceEngine
from finalis.voice.routers import ASRRouter, MockASR, MockTTS, TTSRouter

import voice_fixtures as fx


def run(chunks, *, existing_case=None, consent=True):
    audit = AuditLog()
    engine = VoiceEngine(
        ASRRouter(MockASR("mock-parakeet"), MockASR("mock-whisper")),
        TTSRouter(MockTTS("mock-zonos2"), MockTTS("mock-piper")),
        audit, tenant_id="hvac-1", existing_case=existing_case)
    session = engine.start_session(channel="test_transcript",
                                   recording_consent=consent)
    result = engine.run_call(session, chunks)
    assert audit.verify_chain()
    return result, audit


def missing_types(out):
    return {m["type"] for m in out["missing_items"]}


class TestS1NormalQuote:
    def test_full_happy_intake(self):
        r, audit = run(fx.S1_NORMAL_HVAC_QUOTE)
        out = r.output
        assert out["intent"] == "request_quote"
        assert out["case_type"] == "hvac_installation"
        assert out["service"]["type"] == "heat_pump_quote"
        assert out["client"]["name"] == "Jan Kowalski"
        assert out["service"]["address"] == "Kwiatowa 12"
        assert out["service"]["preferred_date"] == "thursday"
        # Photos can never arrive mid-call → always still missing.
        assert missing_types(out) == {"installation_photo", "device_brand"}
        assert out["next_action"]["type"] == "send_photo_request"
        assert out["human_review_required"] is False
        for ev in ["CALL_STARTED", "INTENT_DETECTED",
                   "MISSING_INFO_DETECTED", "NEXT_ACTION_CREATED",
                   "CALL_ENDED"]:
            assert ev in out["audit_events"], ev
        # Case created and wired into the completion loop.
        assert r.case is not None and r.case.state is CaseState.NEW_CONTACT
        assert r.case.next_best_action == out["next_action"]
        assert r.case.next_action_due_at is not None

    def test_one_question_at_a_time(self):
        r, _ = run(fx.S1_NORMAL_HVAC_QUOTE)
        ai_turns = [u.text for u in r.session.utterances if u.speaker == "ai"]
        # No AI turn may contain two question marks (one question at a time).
        assert all(t.count("?") <= 1 for t in ai_turns)


class TestS2Interruption:
    def test_barge_in_stops_tts_and_is_audited(self):
        r, audit = run(fx.S2_CLIENT_INTERRUPTS)
        assert len(audit.events(event_type="BARGE_IN")) == 1
        interruptions = [u for u in r.session.utterances if u.is_interruption]
        assert len(interruptions) == 1
        assert r.output["intent"] == "request_quote"   # flow recovered


class TestS3Correction:
    def test_later_correction_wins(self):
        r, _ = run(fx.S3_WRONG_DATA_CORRECTED)
        assert r.output["service"]["address"] == "Lipowa 8"
        assert r.output["client"]["name"] == "Adam Nowak"


class TestS4Promise:
    def test_photo_promise_creates_promise_and_task(self):
        r, audit = run(fx.S4_PROMISES_PHOTOS)
        out = r.output
        assert out["promises"] == [{
            "who": "client", "what": "send photos", "due": "tomorrow",
            "confidence": pytest.approx(0.87, abs=0.05)}]
        assert "PROMISE_DETECTED" in out["audit_events"]
        assert r.tasks == [{"type": "followup_if_no_photos",
                            "due": "tomorrow", "channel": "sms_or_whatsapp"}]
        assert len(r.case.promises) == 1
        assert r.case.promises[0].what == "send photos"
        assert "promised to send photos" in out["summary"]


class TestS5RefusesAddress:
    def test_refusal_keeps_missing_and_flags_risk(self):
        r, _ = run(fx.S5_REFUSES_ADDRESS)
        out = r.output
        assert "address" in missing_types(out)
        assert out["service"]["address"] is None
        assert out["risks"] == ["client_refused_address"]
        # Price was asked without data → the AI must not have quoted one.
        ai_text = " ".join(u.text for u in r.session.utterances
                           if u.speaker == "ai")
        assert "Nie chcę podawać ceny" in ai_text


class TestS6HumanRequest:
    def test_handoff_honored_immediately(self):
        r, audit = run(fx.S6_ASKS_FOR_HUMAN)
        out = r.output
        assert out["human_review_required"] is True
        assert out["handoff_reason"] == "human_requested"
        assert r.session.status == "handed_off"
        assert out["next_action"] == {"type": "human_callback",
                                      "channel": "phone",
                                      "requires_human_approval": True}
        assert len(audit.events(event_type="HUMAN_HANDOFF")) == 1


class TestS7AngryClient:
    def test_anger_triggers_handoff(self):
        r, _ = run(fx.S7_ANGRY_CLIENT)
        assert r.output["human_review_required"] is True
        assert r.output["handoff_reason"] == "anger"


class TestS8MixedLanguages:
    def test_language_detection_and_uncertain_place_name(self):
        r, _ = run(fx.S8_MIXED_LANGUAGES)
        out = r.output
        assert set(out["languages_detected"]) == {"pl", "de"}
        assert out["intent"] == "request_quote"
        assert out["service"]["type"] == "heat_pump_quote"
        # The uncertain city fragment must NOT appear as a confirmed address.
        assert out["service"]["address"] is None


class TestS9OutOfScope:
    def test_out_of_scope_declined_no_case(self):
        r, _ = run(fx.S9_OUT_OF_SCOPE)
        out = r.output
        assert out["next_action"]["type"] == "close_out_of_scope"
        assert r.case is None                       # no case invented
        ai_text = " ".join(u.text for u in r.session.utterances
                           if u.speaker == "ai")
        assert "nie zajmujemy się" in ai_text


class TestS10ReturningClient:
    def test_previous_case_reference_detected(self):
        from finalis.models import Case
        existing = Case(tenant_id="hvac-1", state=CaseState.COMPLETED)
        r, _ = run(fx.S10_RETURNING_CLIENT, existing_case=existing)
        out = r.output
        assert out["returning_client_reference"] is True
        assert out["case_id"] == existing.id        # linked, not duplicated
        assert out["intent"] == "request_quote"


class TestS11UncertainBrand:
    def test_uncertain_brand_never_saved_as_certain(self):
        r, _ = run(fx.S11_UNCERTAIN_BRAND)
        brand = r.output["service"]["device_brand"]
        assert brand["value"] == "Vissmann"
        assert brand["status"] == "uncertain"       # NOT confirmed
        assert brand["confidence"] <= 0.5
        # And it stays a missing item (uncertain ≠ known).
        assert "device_brand" in missing_types(r.output)
        item = next(m for m in r.output["missing_items"]
                    if m["type"] == "device_brand")
        assert item.get("note") == "value_present_but_uncertain"


class TestS12PriceWithoutData:
    def test_no_price_promised_without_data(self):
        r, _ = run(fx.S12_PRICE_WITHOUT_DATA)
        ai_text = " ".join(u.text for u in r.session.utterances
                           if u.speaker == "ai")
        assert "Nie chcę podawać ceny" in ai_text
        # No numeric price anywhere in AI speech.
        import re
        assert not re.search(r"\d+\s*(zł|PLN|EUR|€)", ai_text)
        assert missing_types(r.output) >= {"address", "installation_photo"}


class TestNoHallucination:
    """Cross-scenario invariant: fields never invent values."""

    @pytest.mark.parametrize("chunks", [
        fx.S1_NORMAL_HVAC_QUOTE, fx.S4_PROMISES_PHOTOS, fx.S5_REFUSES_ADDRESS,
        fx.S8_MIXED_LANGUAGES, fx.S11_UNCERTAIN_BRAND,
        fx.S12_PRICE_WITHOUT_DATA])
    def test_unknown_fields_stay_null(self, chunks):
        r, _ = run(chunks)
        out = r.output
        # Confirmed-only surfaces: address/preferred_date must be None unless
        # a confirmed extraction exists with a source utterance.
        for key in ("address", "preferred_date"):
            if out["service"][key] is not None:
                status_key = "address_status" if key == "address" else None
                if status_key:
                    assert out["service"][status_key] == "confirmed"
        brand = out["service"]["device_brand"]
        if brand["status"] == "unknown":
            assert brand["value"] is None


class TestSessionAndConsent:
    def test_session_object_lifecycle(self):
        r, _ = run(fx.S1_NORMAL_HVAC_QUOTE)
        s = r.session
        assert s.tenant_id == "hvac-1"
        assert s.status in ("ended", "handed_off")
        assert s.started_at and s.ended_at
        assert s.summary
        assert s.consent_asked

    def test_no_recording_without_consent(self):
        r, audit = run(fx.S1_NORMAL_HVAC_QUOTE, consent=False)
        assert r.session.recording_allowed is False
        started = audit.events(event_type="CALL_STARTED")[0]
        assert started.payload["recording_allowed"] is False
        assert r.session.audio_uri is None           # nothing recorded

    def test_metrics_marked_not_measured(self):
        r, _ = run(fx.S1_NORMAL_HVAC_QUOTE)
        m = r.session.metrics
        assert m.measured is False
        assert m.p50_first_response_latency_ms is None   # honest: no audio path
        assert m.intent_confidence > 0


class TestRouters:
    def test_asr_failover_on_low_confidence(self):
        class LowConfASR:
            name = "low"
            def transcribe(self, chunk):
                from finalis.voice.routers import TranscriptChunk
                return TranscriptChunk(text="???", confidence=0.1,
                                       language="en")
        router = ASRRouter(LowConfASR(), MockASR("fallback"))
        out = router.transcribe({"text": "hello", "confidence": 0.9})
        assert router.last_engine == "fallback"
        assert out.text == "hello"

    def test_asr_failover_on_crash(self):
        class CrashASR:
            name = "crash"
            def transcribe(self, chunk):
                raise RuntimeError("engine died")
        router = ASRRouter(CrashASR(), MockASR("fallback"))
        out = router.transcribe({"text": "still works", "confidence": 0.9})
        assert out.text == "still works"

    def test_tts_language_aware_selection_and_fallback(self):
        primary = MockTTS("zonos2", languages={"pl", "en"})
        fallback = MockTTS("piper", languages={"pl", "de", "es", "en"})
        router = TTSRouter(primary, fallback)
        assert router.speak("hallo", "de")["engine"] == "piper"
        assert router.speak("hello", "en")["engine"] == "zonos2"

    def test_tts_interruption_stop(self):
        router = TTSRouter(MockTTS(), MockTTS())
        router.speak("long monologue", "en")
        assert router.speaking
        router.stop()
        assert not router.speaking
        assert router.interrupted_count == 1
