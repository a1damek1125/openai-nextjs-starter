"""Conversation Intelligence Engine tests — diarized analysis with the
evidence acceptance rule: no critical fact certain without a supporting
segment + sufficient joint ASR×diarization confidence."""
from finalis.audit import AuditLog
from finalis.voice.conversation_intelligence import (
    CERTAIN_MIN_CONF, ConversationIntelligence, DiarizedSegment)


def seg(speaker, text, start, end, asr=0.95, diar=0.95, lang="en",
        uncertain=None):
    return DiarizedSegment(speaker=speaker, text=text, start_ms=start,
                           end_ms=end, asr_confidence=asr,
                           diar_confidence=diar, language=lang,
                           uncertain_terms=uncertain or [])


CALL = [
    seg("SPEAKER_00", "Hi, I'd like a quote for a heat pump installation.",
        0, 3200),
    seg("SPEAKER_00", "My name is Jan Kowalski, the house is at "
        "ul. Kwiatowa 12 in Poznań.", 3400, 8100),
    seg("SPEAKER_00", "I'll send you the photos tomorrow.", 8300, 10900),
]


def analyze(segments, **kw):
    audit = AuditLog()
    ci = ConversationIntelligence(audit, tenant_id="hvac-1")
    return ci.analyze("vs-1", segments, **kw), audit


class TestFullAnalysis:
    def test_transcript_speaker_attributed_and_timed(self):
        a, _ = analyze(CALL)
        assert len(a.transcript) == 3
        t0 = a.transcript[0]
        assert t0["speaker"] == "client"
        assert (t0["start_ms"], t0["end_ms"]) == (0, 3200)
        assert t0["asr_confidence"] == 0.95
        assert t0["diar_confidence"] == 0.95

    def test_structured_outputs_complete(self):
        a, _ = analyze(CALL)
        assert a.intent == "request_quote"
        assert a.intent_confidence > 0.8
        fact_keys = {f["key"] for f in a.facts}
        assert {"client_name", "address"} <= fact_keys
        assert {m["type"] for m in a.missing_items} >= {"installation_photo"}
        assert a.promises[0]["what"] == "send photos"
        assert a.promises[0]["due"] == "tomorrow"
        assert a.tasks == [{"type": "followup_if_no_photos", "due": "tomorrow",
                            "channel": "sms_or_whatsapp"}]
        assert a.next_action["type"] == "send_photo_request"
        assert a.human_review_required is False
        assert "promised to send photos" in a.summary
        assert any(d.startswith("promise_recorded") for d in a.key_decisions)

    def test_every_fact_is_evidence_bound(self):
        a, _ = analyze(CALL)
        for f in a.facts:
            if f["status"] == "certain":
                assert f["evidence_ref_id"] is not None
                ref = next(e for e in a.evidence_references
                           if e.id == f["evidence_ref_id"])
                assert ref.source_type == "call_segment"
                assert "start_ms" in ref.locator and "end_ms" in ref.locator
                assert ref.snippet

    def test_case_update_payload_shape(self):
        a, _ = analyze(CALL, case_id="case-9")
        p = a.case_update_payload
        assert p["tenant_id"] == "hvac-1" and p["case_id"] == "case-9"
        assert p["intent"] == "request_quote"
        assert p["promises"] and p["missing_items"] and p["next_action"]

    def test_audit_events_written(self):
        a, audit = analyze(CALL)
        for ev in ["CONVERSATION_ANALYZED", "EVIDENCE_CREATED",
                   "MISSING_INFO_DETECTED", "PROMISE_CREATED"]:
            assert audit.events(event_type=ev), ev
        assert audit.verify_chain()


class TestAcceptanceRule:
    """No critical fact certain without segment support + joint confidence."""

    def test_low_diarization_confidence_downgrades_fact(self):
        # Same words, but the diarizer is unsure who spoke → joint conf low.
        segments = [
            seg("SPEAKER_00", "I need a heat pump quote.", 0, 2000),
            seg("SPEAKER_00", "The house is at ul. Kwiatowa 12.",
                2100, 5000, asr=0.95, diar=0.4),
        ]
        a, _ = analyze(segments)
        addr = next(f for f in a.facts if f["key"] == "address")
        assert addr["status"] == "uncertain"        # NOT certain
        assert a.human_review_required is True      # critical + uncertain
        assert "low_confidence_critical_facts" in a.risks

    def test_low_asr_confidence_downgrades_fact(self):
        segments = [
            seg("SPEAKER_00", "I need a heat pump quote.", 0, 2000),
            seg("SPEAKER_00", "My name is Jan Kowalski.", 2100, 4000,
                asr=0.45, diar=0.95),
        ]
        a, _ = analyze(segments)
        name = next(f for f in a.facts if f["key"] == "client_name")
        assert name["status"] == "uncertain"

    def test_joint_confidence_threshold_is_min_not_mean(self):
        # asr .9, diar .55 → min .55 < 0.6 → uncertain (mean would be .725).
        segments = [
            seg("SPEAKER_00", "Quote please, it's at ul. Polna 5.",
                0, 3000, asr=0.9, diar=0.55),
        ]
        a, _ = analyze(segments)
        addr = next((f for f in a.facts if f["key"] == "address"), None)
        assert addr is not None
        assert addr["status"] == "uncertain"
        assert CERTAIN_MIN_CONF == 0.6

    def test_noncritical_uncertain_fact_does_not_force_review(self):
        segments = [
            seg("SPEAKER_00", "I need a boiler service quote.", 0, 2500),
            seg("SPEAKER_00", "I think it's a Vissmann or something.",
                2600, 5000, asr=0.6, diar=0.9, uncertain=["Vissmann"]),
        ]
        a, _ = analyze(segments)
        brand = next(f for f in a.facts if f["key"] == "device_brand")
        assert brand["status"] == "uncertain"
        assert brand["critical"] is False
        assert a.human_review_required is False     # non-critical only


class TestHandoffAndRisks:
    def test_handoff_produces_review_and_risk(self):
        segments = CALL + [seg("SPEAKER_00",
                               "Actually I want to talk to a human.",
                               11000, 13000)]
        a, audit = analyze(segments)
        assert a.human_review_required is True
        assert a.next_action == {"type": "human_callback", "channel": "phone",
                                 "requires_human_approval": True}
        assert any(r.startswith("handoff:") for r in a.risks)
        assert audit.events(event_type="HUMAN_REVIEW_REQUESTED")

    def test_multilingual_segments_processed(self):
        segments = [
            seg("SPEAKER_00", "Dzień dobry, potrzebuję wyceny pompy ciepła.",
                0, 3000, lang="pl"),
            seg("SPEAKER_00", "Wyślę zdjęcia jutro.", 3100, 5000, lang="pl"),
        ]
        a, _ = analyze(segments)
        assert a.intent == "request_quote"
        assert a.promises and a.promises[0]["due"] == "tomorrow"
