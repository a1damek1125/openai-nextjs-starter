# AUDIT-TRACE-1 — SP Status Matrix

Machine-readable twin: `AUDIT_TRACE_1_SP_STATUS.json`.

Status ∈ {IMPLEMENTED_AND_TESTED, IMPLEMENTED_PARTIALLY, IMPLEMENTED_NOT_WIRED,
IMPLEMENTED_NOT_TESTED, SCAFFOLD_ONLY, MOCK_ONLY, DOC_ONLY, SUPERSEDED,
NOT_FOUND}. Production ∈ {PRODUCTION_READY, NOT_PRODUCTION_READY, UNKNOWN}.

> Every SP below is `NOT_PRODUCTION_READY` for one shared reason: **the system
> has zero real external-effect surface**. `grep -rn 'import requests|import
> httpx|import smtplib|import boto3|urllib.request|http.client' finalis/`
> (excluding tests) returns **0**. All "providers" are in-process mocks. This is
> by design for the governance layers and a scoping decision for the product
> layers — it is not a bug, but it is the single largest gap to production.

| SP | Status | Prod | Anchor evidence |
|---|---|---|---|
| DOCS-BLUEPRINT (docs 1–45) | DOC_ONLY | UNKNOWN | `1a57c7f`; `docs/finalis-ai/*` |
| SCAFFOLD-1 (state machine/scoring/autonomy) | IMPLEMENTED_AND_TESTED | NOT_READY | `8071a54`; claims 102 tests |
| VOICE-ENGINE | IMPLEMENTED_AND_TESTED | NOT_READY | `a8e15a7`; `finalis/voice/*` (1106 L); 26 tests. ASR/TTS = mock seams |
| CASE-GRAPH | IMPLEMENTED_AND_TESTED | NOT_READY | `47cb24e` |
| CONVERSATION-INTELLIGENCE | IMPLEMENTED_AND_TESTED | NOT_READY | `8379db9`; 11 tests |
| ACTION-COMM-ENGINE | IMPLEMENTED_AND_TESTED | NOT_READY | `9b8cb1a`; `finalis/actions/adapters.py`. **Send = NovuMock/ChatwootMock (MOCK_ONLY boundary)** |
| COMMAND-CENTER | IMPLEMENTED_AND_TESTED | NOT_READY | `618a7a3`; 19 tests |
| FULL-PRODUCT-E2E | IMPLEMENTED_AND_TESTED | NOT_READY | `96707d0` |
| PORTAL-CORE | IMPLEMENTED_AND_TESTED | NOT_READY | `61c0ea7`; migration v1; SQLite dev shell |
| UNIVERSAL-LIFECYCLE | IMPLEMENTED_AND_TESTED | NOT_READY | `f869bf9`; `finalis/lifecycle/*` (929 L); 63 tests |
| TELEPHONY | IMPLEMENTED_AND_TESTED | NOT_READY | `7d017e5`; v2; 49 tests. **dial() = mock provider** |
| ADMIN-RBAC | IMPLEMENTED_AND_TESTED | NOT_READY | `6804d92`; `finalis/admin/*`; 21 tests. IAM = seams |
| SCHEDULING | IMPLEMENTED_AND_TESTED | NOT_READY | `3a334de`/`4e663fc`; v4; 29 tests. **calendar/video = mock** |
| AGENT-RUNTIME-GOV | IMPLEMENTED_AND_TESTED | NOT_READY | `a96c025`; `finalis/governance/*`; 18 tests |
| PORTAL-WIRING | IMPLEMENTED_AND_TESTED | NOT_READY | `9c6a951`..`7f3a1be`; provider honesty labels introduced |
| QUOTE-CPQ | IMPLEMENTED_AND_TESTED | NOT_READY | `19d7019`..`3a5c145`; v3; 76 tests. **payment/PDF/e-sign = mock** |
| EVIDENCE-TRUST-FABRIC | IMPLEMENTED_AND_TESTED | NOT_READY | `0c8e4a7`..`fe142f9`; v5/v6/v8; 269 tests |
| RELATIONSHIP-CRM | IMPLEMENTED_AND_TESTED | NOT_READY | `8f9ef28`..`c13d6bc`; v7; 63 tests. **external sync = mock** |
| CONSOLIDATE-1 | IMPLEMENTED_AND_TESTED | NOT_READY | `65c67f5`; integration baseline guard |
| CORE-A1 identity/authority | IMPLEMENTED_AND_TESTED | NOT_READY | `905a298`; v9 |
| CORE-A2 intake/task contract | IMPLEMENTED_AND_TESTED | NOT_READY | `bf10d9a`; v10 |
| CORE-A3 run ledger/replay | IMPLEMENTED_AND_TESTED | NOT_READY | `00e0452`; v11 |
| CORE-A4 approval gate/grants | IMPLEMENTED_AND_TESTED | NOT_READY | `0590e80`; v12–v13 |
| CORE-A5 lifecycle kernel | IMPLEMENTED_AND_TESTED | NOT_READY | `f613489`; v14 |
| CORE-A6 artifacts/claim graph | IMPLEMENTED_AND_TESTED | NOT_READY | `80ea4d0`; v15 |
| TOOL-B1 tool registry/firewall | IMPLEMENTED_AND_TESTED | NOT_READY | `d08c07c`; v16; 1215 L |
| TOOL-B2 descriptor assurance | IMPLEMENTED_AND_TESTED | NOT_READY | `da02379`; v17; 1657 L |
| TOOL-B3 contract proof kernel | IMPLEMENTED_AND_TESTED | NOT_READY | `dd24cd8`; v18; 1715 L. Targets = `*_LIKE` shapes |
| TOOL-B4 reference monitor | IMPLEMENTED_AND_TESTED | NOT_READY | `7d827ff`; v19; 1628 L |
| TOOL-B5 null broker | IMPLEMENTED_AND_TESTED | NOT_READY | `7d2c44a`; v20; 1823 L |
| TOOL-B6 read-path microkernel | IMPLEMENTED_AND_TESTED | NOT_READY | `48d15f7`; v21; 2208 L |
| TOOL-B7 write-intent draft | IMPLEMENTED_AND_TESTED | NOT_READY | `d28b6f7`; v22; 2361 L. Draft only |
| TOOL-B8 pre-B9 assurance | IMPLEMENTED_AND_TESTED | NOT_READY | `d95be03`; v23; 1814 L. B9 firewall sealed |
| TOOL-B9 transaction twin/PoE | IMPLEMENTED_AND_TESTED | NOT_READY | `5493e60`; v24; 1627 L. Inert outbox |
| TOOL-B9.1 recovery runtime | IMPLEMENTED_AND_TESTED | NOT_READY | `c35d827`; v25; 1746 L; ~230 tests |
| TOOL-B9.2 work observatory | IMPLEMENTED_AND_TESTED | NOT_READY | `c05681f`; v26; 1658 L. Read-only; PoWO authorizes nothing |
| **EMP-A1 work inbox (HEAD SP)** | IMPLEMENTED_AND_TESTED | NOT_READY | `6e342e2`..`135de7b`; v27; 1343 L; 14 test files. Admission only |
| AUDIT-REPORT-1 | DOC_ONLY | UNKNOWN | `4e39dd8`; `docs/audits/*` |
| ROADMAP-LOCK-1 | DOC_ONLY | UNKNOWN | `19a3a0b`; `docs/roadmap/*`; next_coding_sp=EMP-A2 |
| EMP-A2 (handoff consumer) | NOT_FOUND | UNKNOWN | Named as next SP; no module/route/migration/test |
| EMP-A3..A5 | NOT_FOUND | UNKNOWN | Roadmap chain only |
| TOOL-B10 external adapter boundary | NOT_FOUND | UNKNOWN | Re-scoped in roadmap; no real outbound primitive exists |

## Status counts
- IMPLEMENTED_AND_TESTED: **35**
- DOC_ONLY: **3** (DOCS-BLUEPRINT, AUDIT-REPORT-1, ROADMAP-LOCK-1)
- NOT_FOUND: **4** (EMP-A2, EMP-A3..A5, TOOL-B10)
- MOCK_ONLY / IMPLEMENTED_NOT_WIRED: 0 as a *whole-SP* status, but **7 SPs carry
  a MOCK_ONLY external boundary** (ACTION-COMM, TELEPHONY, SCHEDULING, QUOTE-CPQ,
  RELATIONSHIP-CRM external sync, VOICE ASR/TTS, plus the entire TOOL/EMP layer's
  deliberately inert outbox). These are recorded in each row's notes, not fixed.
- SUPERSEDED: 0 whole SPs; 2 *claims* superseded (migration v25→v27, test count).
- SCAFFOLD_ONLY / IMPLEMENTED_NOT_TESTED / IMPLEMENTED_PARTIALLY: **0** found.

Every IMPLEMENTED_AND_TESTED row is simultaneously NOT_PRODUCTION_READY because
no SP owns a real external effect.
