# ROADMAP-LOCK-1 — Production Gaps

> What separates the current **local, simulation-only, proof-carrying** system (code HEAD `d95be03`) from a **production Finalis AI Employee OS**. Sourced from AUDIT-REPORT-1 evidence. Each gap maps to the SP(s) that close it.

Legend: **IMPLEMENTED** (real local, tested) · **MOCKED** (local mock, tested) · **SCAFFOLDED** (declared placeholder) · **MISSING** (absent) · **BLOCKED_CREDENTIALS** · **BLOCKED_PROVIDER**.

---

## 1. What is already IMPLEMENTED (do not rebuild — extend)
- Full governance ladder CORE-A1..A6 + TOOL-B1..B8 (proof-carrying, non-executing).
- CRM, CPQ, Scheduling engine, Case Graph/Completion/Dashboard, Voice/CI logic, Telephony call-control logic.
- Evidence cryptography: SHA-256 chains, Merkle + RFC 6962/9162 consistency proofs, content-addressed replayable reports.
- RBAC (9 roles/45 perms, deny-by-default), server-side tenant isolation, agent-runtime governance.
- 4601 non-browser tests, 0 failed.

## 2. What is MOCKED (swap in place via existing seams — Blocks J,K,L,M,I,Q)
| Mock | Owner seam | Closed by |
|---|---|---|
| Telephony provider | `telephony` `TelephonyProvider` | ADAPTER-1 → VOICE-PROD-1 → PILOT-4 |
| Email/SMS (Novu), handoff (Chatwoot), workflow (Temporal) | `actions/adapters.py` | ADAPTER-1 → CHAT-* → PILOT-1/2/3 |
| Calendar, video meeting | `scheduling` providers | ADAPTER-1 → PILOT-3 |
| PDF, invoice handoff | `quotes/providers.py` | ADAPTER-1 (docs/invoicing pilot) |
| ASR/TTS | `voice/routers.py` | ADAPTER-1 → VOICE-PROD-1 |
| WebScout fetch, OCR engines | `webscout.py`, `ocr_router.py` | WORKBENCH-1 / EVID-PROD-1 |
| Malware scanner | `evidence/scanners.py` | ADAPTER-1 → EVID-PROD-1 |
| Persistence (SQLite + local FS) | `portal/db.py`, `evidence/storage.py` | INFRA-1, INFRA-2 |

## 3. What is SCAFFOLDED (declared placeholders — close in order)
| Scaffold | Where | Closed by |
|---|---|---|
| Real write/commit runtime | (arrives) | **TOOL-B9** |
| E-signature provider (raises NotImplementedError) | `quotes/providers.py` | ADAPTER-1 pilot |
| Native WORM (capabilities all-false) | `evidence/immutability.py`,`storage.py` | INFRA-2 |
| External CRM sync adapters (opt-in/off) | `crm/adapters.py` | ADAPTER-1 (gated) |
| LGGT certainty core (NullAdapter) | `certainty_core.py` | future SP (not scheduled pre-prod) |
| IAM adapter seams | `admin` | SAAS-1 |

## 4. What is MISSING (must be built — mapped to SPs)
| Missing capability | Closed by |
|---|---|
| Real local reversible commit | TOOL-B9 |
| Commit recovery / duplicate prevention / metrics | TOOL-B10 |
| Employee work inbox / work graph / outcome contracts / autonomy engine | TOOL-B11/B12/B13 |
| Evaluation lab (golden/injection/artifact-authority/cross-tenant) | EVAL-1 |
| Governed workbench (sandbox/recorder/reviewable) | WORKBENCH-1 |
| Mobile API + PWA + native + push-approval + offline draft | MOBILE-1/2 |
| Provider boundary + credential capability model | ADAPTER-1 |
| Slack/Teams conversation contract + approval cards | CHAT-1/2 |
| Production evidence lifecycle + secure upload + signing/anchoring prep | EVID-PROD-1 |
| Production auth/IAM/SSO/MFA, billing, onboarding, compliance center | SAAS-1 |
| Postgres, object store/WORM, observability, deployment runbook | INFRA-1..4 |
| app.py/ui.py decomposition + kernel/test dedup | REFACTOR-1..3 |
| Production readiness / red-team / beta / prod-candidate gates | GATE-1..4 |

## 5. BLOCKED_BY_CREDENTIALS
LLM/provider API keys · MCP/OAuth/payment/CRM/email/telephony credentials · KMS/signing credentials · external timestamp/notary credentials. → unblocked incrementally by **ADAPTER-1** (credential capability model) + **SAAS-1** (secret manager) + per-provider **PILOT-***.

## 6. BLOCKED_BY_EXTERNAL_PROVIDER
LLM providers · MCP servers · Slack/Teams/email/calendar/video/payment/CRM/telephony providers · AV/CDR scanner · OCR/ASR/TTS providers · S3 Object-Lock WORM · Sigstore/Rekor/SCITT/RFC-3161 anchoring · KMS. → gated behind **ADAPTER-1** boundary; wired one at a time in **PILOT-*/INFRA-2/EVID-PROD-1**.

## 7. Why NOT production-ready (exact reasons + owner SP)
1. SQLite + local FS persistence → **INFRA-1/INFRA-2**.
2. Every external effect is a mock → **ADAPTER-1 + PILOT-***.
3. Evidence transparency log unanchored; `STRICT_RFC8785_JCS = NOT_IMPLEMENTED`; no report signing → **EVID-PROD-1 + INFRA-2 + KMS**.
4. Dev-grade auth (static secret, no SSO/MFA/rate-limit) → **SAAS-1**.
5. No observability/deployment/secrets/rollback → **INFRA-3/INFRA-4**.
6. Governance line is simulation by design (`commit_executable_now` always false) → **TOOL-B9** introduces the first (local, reversible) commit.
7. Maintainability risk (app.py/ui.py monoliths, kernel/test dup) → **REFACTOR-1..3**.

## 8. Gap-closure order (dependency-respecting)
```
TOOL-B9 → B10 → B11 → B12 → B13 → EVAL-1
                                   → ADAPTER-1 → {EVID-PROD-1, CHAT-1→CHAT-2, VOICE-PROD-1, PACK-*}
INFRA-1 → INFRA-2 → INFRA-3 → INFRA-4
SAAS-1 (needs INFRA-1 + ADAPTER-1)
PILOT-1..4 (needs ADAPTER-1 + CHAT/VOICE + SAAS-1 + EVAL-1 green)
REFACTOR-1..3 (post-B13, behavior-preserving)
GATE-1..4 (terminal)
```

## 9. Production-ready when (exit criteria)
`production_ready = true` **only after** GATE-4 passes, which requires: TOOL-B9..B13 done · ADAPTER-1 + credential model · EVID-PROD-1 + INFRA-2 anchoring/signing · SAAS-1 production auth · INFRA-1..4 · at least one real surface pilot (CHAT/PILOT) green in limited beta · EVAL-1 + GATE-2 red-team green · full suite green throughout. Until then the honest status remains **NOT_PRODUCTION_READY**.
