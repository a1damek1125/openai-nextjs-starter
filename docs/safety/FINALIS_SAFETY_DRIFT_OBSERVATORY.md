# FINALIS Safety Drift Observatory (SP0005 D-0005-79)

Deterministic longitudinal snapshot (`python -m tools.safety drift`), tracking:
hazard count, critical hazards, uncontrolled hazards, proof-obligation failures,
lease invalidations, TOCTOU mismatches, trajectory violations, control-independence
gaps, open defeaters, evidence age, incident count, near-miss count,
regulatory-source changes and safety-test coverage. **Uncalibrated drift metrics
are advisory (`ADVISORY_NOT_A_GATE`), never automatic hard blockers** — but
`P0_OPEN > 0` is always a `SAFETY_GATE_FAIL` (D-0005-78, INV-0005-10). Assurance
debt is a vector, never one averaged safety score.
