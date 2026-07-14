"""Finalis AI — minimal executable scaffold.

This package is the smallest executable foundation that proves the blueprint's
core logic (docs/finalis-ai/02-05, 09, 13): the 17-state case lifecycle, the
deterministic scoring layer, autonomy gating, the append-only audit chain, the
completion loop with anti-spam follow-up, and confidence-gated document intake.

It is NOT the production system: no database, no LLMs, no telephony — pure,
deterministic domain logic with a simulated clock, designed so the production
implementation can grow around these contracts without rewriting the tests.
"""

__version__ = "0.1.0"
