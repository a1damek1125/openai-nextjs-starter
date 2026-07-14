"""Voice data model — VoiceSession, Utterance, VoiceExtraction, VoiceMetric.

Promise / MissingItem / AuditEvent are reused from the core scaffold
(finalis.models / finalis.audit) so voice feeds the same Case Graph.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Utterance:
    voice_session_id: str
    speaker: str                  # client | ai
    text: str
    start_ms: int = 0
    end_ms: int = 0
    confidence: float = 1.0       # ASR confidence [0,1]
    language: str = "en"
    is_interruption: bool = False
    uncertain_terms: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)


@dataclass
class VoiceExtraction:
    voice_session_id: str
    case_id: Optional[str]
    extraction_type: str          # intent | field | promise | missing | objection
    payload: dict[str, Any]
    confidence: float
    source_utterance_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)


@dataclass
class VoiceMetric:
    voice_session_id: str
    p50_first_response_latency_ms: Optional[float] = None   # None = not measured
    p95_first_response_latency_ms: Optional[float] = None
    asr_latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    tts_latency_ms: Optional[float] = None
    barge_in_success: Optional[bool] = None
    intent_confidence: float = 0.0
    extraction_confidence: float = 0.0
    measured: bool = False        # transcript-only MVP: latencies NOT measured


@dataclass
class VoiceSession:
    tenant_id: str
    channel: str                  # webrtc | sip | test_transcript
    case_id: Optional[str] = None
    language: str = "en"
    status: str = "created"       # created | active | ended | handed_off
    recording_allowed: bool = False
    consent_asked: bool = False
    audio_uri: Optional[str] = None
    transcript_uri: Optional[str] = None
    summary: Optional[str] = None
    human_handoff_requested: bool = False
    handoff_reason: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    utterances: list[Utterance] = field(default_factory=list)
    extractions: list[VoiceExtraction] = field(default_factory=list)
    metrics: VoiceMetric = None  # type: ignore[assignment]
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.metrics is None:
            self.metrics = VoiceMetric(voice_session_id=self.id)
