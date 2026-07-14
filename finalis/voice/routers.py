"""ASR Router and TTS Router — provider-agnostic with primary + fallback.

Real engines (Parakeet/Canary/faster-whisper; ZONOS2/Qwen3-TTS/Piper) implement
the protocols; the scaffold ships deterministic mocks. The ROUTING logic
(fallback on failure/low confidence, language-aware selection, interruption
stop) is real and tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

SUPPORTED_LANGUAGES = {"pl", "de", "es", "en"}


@dataclass
class TranscriptChunk:
    text: str
    confidence: float
    language: str
    start_ms: int = 0
    end_ms: int = 0
    uncertain_terms: list[str] = field(default_factory=list)


class ASRService(Protocol):
    name: str
    def transcribe(self, audio_chunk: dict) -> TranscriptChunk: ...


class TTSService(Protocol):
    name: str
    languages: set[str]
    def synthesize(self, text: str, language: str,
                   voice_profile: str) -> dict: ...


class ASRRouter:
    """Primary → fallback ASR with confidence-based failover."""

    def __init__(self, primary: ASRService, fallback: ASRService,
                 *, failover_confidence: float = 0.4) -> None:
        self.primary = primary
        self.fallback = fallback
        self.failover_confidence = failover_confidence
        self.last_engine: Optional[str] = None

    def transcribe(self, audio_chunk: dict) -> TranscriptChunk:
        try:
            chunk = self.primary.transcribe(audio_chunk)
            engine = self.primary.name
        except Exception:
            chunk, engine = None, ""
        if chunk is None or chunk.confidence < self.failover_confidence:
            fb = self.fallback.transcribe(audio_chunk)
            # Keep whichever is more confident; never silently drop signal.
            if chunk is None or fb.confidence > chunk.confidence:
                chunk, engine = fb, self.fallback.name
        self.last_engine = engine
        if chunk.language not in SUPPORTED_LANGUAGES:
            chunk.language = "en"
        return chunk


class TTSRouter:
    """Language-aware TTS selection with fallback and interruption stop."""

    def __init__(self, primary: TTSService, fallback: TTSService) -> None:
        self.primary = primary
        self.fallback = fallback
        self.speaking = False
        self.interrupted_count = 0

    def pick(self, language: str) -> TTSService:
        if language in self.primary.languages:
            return self.primary
        return self.fallback

    def speak(self, text: str, language: str,
              voice_profile: str = "default") -> dict:
        engine = self.pick(language)
        try:
            out = engine.synthesize(text, language, voice_profile)
        except Exception:
            out = self.fallback.synthesize(text, language, voice_profile)
        self.speaking = True
        return out

    def stop(self) -> None:
        """Barge-in: immediately stop speaking and flush queued audio."""
        if self.speaking:
            self.interrupted_count += 1
        self.speaking = False


# --- Deterministic mocks (fixture-driven) -----------------------------------
class MockASR:
    """Fixture ASR: 'audio' chunks already carry text/conf/lang annotations."""

    def __init__(self, name: str = "mock-parakeet") -> None:
        self.name = name

    def transcribe(self, audio_chunk: dict) -> TranscriptChunk:
        return TranscriptChunk(
            text=audio_chunk["text"],
            confidence=audio_chunk.get("confidence", 0.95),
            language=audio_chunk.get("language", "en"),
            start_ms=audio_chunk.get("start_ms", 0),
            end_ms=audio_chunk.get("end_ms", 0),
            uncertain_terms=audio_chunk.get("uncertain_terms", []),
        )


class MockTTS:
    def __init__(self, name: str = "mock-zonos2",
                 languages: set[str] | None = None) -> None:
        self.name = name
        self.languages = languages or set(SUPPORTED_LANGUAGES)
        self.spoken: list[str] = []

    def synthesize(self, text: str, language: str,
                   voice_profile: str) -> dict:
        self.spoken.append(text)
        return {"engine": self.name, "language": language, "chars": len(text)}
