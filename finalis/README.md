# Finalis scaffold — how to run

The smallest executable foundation proving the blueprint's core logic
(state machine, scoring, autonomy gating, audit chain, completion loop,
confidence-gated documents, OCR router, WebScout policy, LGGT seam).

## Test command (CI)

```bash
pip install pytest
python3 -m pytest tests/ -q
```

Expected: **102+ passed**. No network, no database, no API keys required —
pure deterministic domain logic with a simulated clock.

## What this is / is not

- **Is**: the executable contract for docs/finalis-ai/03 (state machine),
  05 (all 12 scoring models), 09 (completion loop + anti-spam), 13 (autonomy
  L1–L5 + always-HITL actions), 04 (audit hash chain, core entities),
  07/47 (confidence gate + OCR router with the acceptance rule), 08 (WebScout
  hard restrictions), 32 (CertaintyCoreAdapter Phase-1 NullAdapter).
- **Is not**: a runnable product. No persistence, no LLMs, no telephony,
  no real OCR engines, no UI. Engine/channel adapters are fixture-driven mocks
  behind the same interfaces the production system will implement
  (see docs/finalis-ai/35 for the sprint backlog).

## Layout

```
finalis/            domain logic (pure Python, no deps)
tests/              pytest suites incl. the 20-step E2E MVP flow
docs/finalis-ai/    the full blueprint + audit (00-47)
  state-machine.finalis.json   machine-readable lifecycle (validated by tests)
  openapi.finalis.yaml         API design artifact
```
