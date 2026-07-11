# FINALIS 1000 — Program Criticality Report (SP0003)
Generated deterministically from the canonical program by `tools.program_graph`. Three DISTINCT modes (D-0003-18).
## Structural criticality (unit weights, no durations)
- Structural critical depth: **15** nodes
- Deepest nodes: `GENERAL_AVAILABILITY`

## Estimate-based CPM (explicit estimates only; UNKNOWN never fabricated)
- Project duration (est.): **29.0**
- Critical nodes (20): `ADAPTER-1, FIRST_REAL_EFFECT_READY, GATE-2, GATE-3, GATE-4, GENERAL_AVAILABILITY, INFRA-1, MESSAGING_PILOT_READY, PILOT-1, PILOT-2, PILOT-3, PILOT-4, PRODUCTION_CANDIDATE, SAAS-1, TOOL-B10, TOOL-B11, TOOL-B12, TOOL-B13, TOOL-B8, TOOL-B9`
- Display critical path: `TOOL-B8 -> TOOL-B9 -> ADAPTER-1 -> FIRST_REAL_EFFECT_READY`

## Monte Carlo criticality (advisory; reproducible)
- Samples: 1000, seed: 1000, model version: 1
- Completion p50: 44.233129 (min 30.074479, max 63.610902)
- Criticality concentration (entropy): 2.890372

Top criticality index:
- `ADAPTER-1`: 1.0
- `GATE-2`: 1.0
- `GATE-3`: 1.0
- `GATE-4`: 1.0
- `GENERAL_AVAILABILITY`: 1.0
- `INFRA-1`: 1.0
- `PILOT-1`: 1.0
- `PILOT-2`: 1.0
- `PILOT-3`: 1.0
- `PILOT-4`: 1.0
- `PRODUCTION_CANDIDATE`: 1.0
- `SAAS-1`: 1.0
