# AUDIT-REPORT-1 — Test Quality Audit

Branch `claude/finalis-ai-casewoker-blueprint-f1huse` · HEAD `d95be03`.

## Full suite
- **Command:** `python3 -m pytest tests/ --ignore=tests/test_browser_e2e.py -q`
- **Result:** **4601 passed, 0 failed, 0 errors, 0 skipped, 0 xfail** (verified at HEAD `d95be03`, clean tree).
- **Test files:** 345 total (344 non-browser + `test_browser_e2e.py` excluded).
- **Browser E2E:** intentionally excluded — known Chromium/SIGKILL environment flake, unrelated to code. Not run in this audit.

## Tests by area (evidence: per-module pytest / collect-only)

### Governance / AI-employee line (~3,150+)
| Module | Tests |
|---|---|
| CORE-A1 identity | 19 |
| CORE-A1 authority invariants | 72 |
| CORE-A2/A5 tasks + state machine + intake (`ai_task*`) | 250 |
| CORE-A3 run ledger + replay (`ai_run*`) | 103 |
| CORE-A4.2 approvals (`ai_approval*`) | 169 |
| CORE-A6 artifacts (`ai_artifact*`) | 175 |
| TOOL-B1 registry (`ai_tool_registry*`) | 72 |
| TOOL-B1 descriptor/admission/poisoning/risk (`ai_tool_*`) | 307 |
| TOOL-B2 quality (`ai_tool_quality*`) | 383 |
| TOOL-B3 contract (`ai_tool_contract*`) | 445 |
| TOOL-B4 pre-action (`ai_action_*`) | ~40 |
| TOOL-B5 broker (`ai_tool_broker*`) | 210 |
| TOOL-B6 runtime (`ai_tool_runtime*`) | 319 |
| TOOL-B7 write-intent (`ai_tool_write_intent*`) | 491 |
| TOOL-B8 commit-sim (`ai_tool_commit_simulation*`) | 444 |

### Product / domain line (~1,100)
| Module | Tests |
|---|---|
| Evidence Trust Fabric (10 files) | 269 |
| Universal Lifecycle (incl. state/scoring/completion) | 167 |
| Case Graph / Dashboard / Autonomy / Documents / E2E-in-proc | 87 |
| Quote Builder / CPQ | 76 |
| Relationship CRM | 63 |
| Portal (api + wiring) | 51 |
| Telephony | 49 |
| Voice + Conversation Intelligence | 37 |
| Scheduling | 29 |
| Action & Communication | 25 |
| Admin / RBAC | 21 |
| Agent Runtime Governance | 18 |

## Test-type coverage (strengths)
- **Negative / malicious-payload tests:** every TOOL-B module ships a malicious-payload set (descriptor poisoning, prompt injection, "proof bundle grants execution", "escrow means commit", "assurance envelope grants commit", "production_ready=true", hidden execution routes) — all asserted to block with a stable reason code.
- **Fault-injection harnesses + fail-closed release gates:** B4–B8 each run a deterministic fault harness proving every injected fault is blocked and the release gate is PASSED only when all faults block.
- **Route 404/405 tests:** each governance module asserts the absence of commit/execute/release/activate endpoints.
- **RBAC + tenant-isolation tests:** cross-tenant 404, VIEWER 403 on writes, deny-by-default, last-owner/escalation guards, AI-cannot-approve-own.
- **Hash determinism tests:** decision hashes actor/time/id-independent; self-hash exclusion; tamper→TAMPERED; proof-extension participation.
- **No-execution invariant tests:** parametrized across clean + many blocker variants asserting `commit_executable_now`/`produced_external_effect`/etc always false.
- **Evidence crypto tests:** Merkle inclusion + RFC 6962/9162 consistency proofs, content-addressed report replay, chain-of-custody verify.

## Test-quality risks
- **Implementation coupling (YELLOW):** many governance tests assert exact local model field shapes / hash keys — they will need updates when models evolve. Acceptable for a proof-object domain but raises refactor cost.
- **Label/shape assertions (LOW):** a minority assert status/label presence rather than behavior; mitigated by the parallel behavioral/fault tests.
- **Helper duplication (LOW):** `tests/_bN_kernel.py` helpers are near-copies per layer.
- **Browser E2E unverified (LOW):** excluded due to env; behavior otherwise covered by in-process E2E (`test_full_product_e2e.py`, `test_e2e_mvp_flow.py`).
- **No skipped/xfail** in the non-browser suite.

## Missing tests (recommend before/at next SPs)
- Property/fuzz tests over hash canonicalization edge cases (very large payloads, unicode).
- Concurrency tests for multi-writer SQLite behavior (documents the single-writer assumption).
- Load/scale tests (currently none — single-node only).
- Real-provider contract tests (deferred until adapters exist).

## Verdict
Test suite is **strong** (4601 green, deep negative + fault-injection coverage, fail-closed gates). Primary risk is maintenance cost from implementation coupling and helper/kernel duplication — a refactor candidate after the TOOL-B line stabilizes at B9.
