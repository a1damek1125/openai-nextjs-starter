# FINALIS Safety Oracle Hierarchy (SP0005 D-0005-61/62/66)

For a hard safety property, prefer the strongest applicable oracle:

1. `ENVIRONMENT_STATE` — file/db/queue/authority/effect-ledger state
2. `ARTIFACT_CRYPTO_EVIDENCE` — artifact / cryptographic evidence
3. `INDEPENDENT_FORMAL_RULE_CHECKER`
4. `CALIBRATED_STATISTICAL`
5. `HUMAN_SPECIALIST`
6. `LLM_JUDGE` (bounded, only if independently validated for the property)
7. `AGENT_SELF_REPORT`

**AGENT_SELF_REPORT** — and an **LLM_JUDGE** that is the acting model or is not
independently validated — can NEVER be the SOLE oracle for a hard safety property
(INV-0005-11, AC-0005-143). Prefer "the outbox shows no message" over "the model
says it did not send" (D-0005-66).
