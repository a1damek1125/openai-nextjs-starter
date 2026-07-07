"""Finalis Voice Engine — open core (transcript-level executable scaffold).

Self-hosted, provider-agnostic voice intake: gateway → ASR router → dialogue
manager → understanding extractor → case-graph connector → audit, with human
handoff and an ActionGate seam. Real audio transports (LiveKit/Pipecat, SIP)
and real ASR/TTS engines plug in behind the protocols defined here; the
scaffold ships deterministic mocks so the LOGIC is provable today.
"""

__version__ = "0.1.0"
