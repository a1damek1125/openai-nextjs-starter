# FINALIS 1000 — Dependency Uncertainties & Value-of-Information (SP0003 D-0003-34/35)
Uncertain dependencies never block canonical readiness; only ACTIVE proven hard dependencies do. VOI is computed only where calibrated; mandatory safety work is never bypassable (INV-0003-18).

## UNC-DURABLE-RUNTIME
- candidate: `durable_runtime_strategy` — status UNDER_RESEARCH, impact HIGH
- VOI: **CALIBRATED** (voi=25.0)
- bypassable: True

## UNC-SAFETY-REGULATORY
- candidate: `regulatory_review` — status IDENTIFIED, impact CRITICAL
- VOI: **MANDATORY_NON_BYPASSABLE**
- bypassable: False

## UNC-UNCALIBRATED-EXAMPLE
- candidate: `provider_latency_assumption` — status IDENTIFIED, impact MEDIUM
- VOI: **VOI_NOT_CALIBRATED**
- bypassable: False
