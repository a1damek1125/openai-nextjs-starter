# AUDIT-REPORT-1 — Next SP Recommendation

Branch `claude/finalis-ai-casewoker-blueprint-f1huse` · HEAD `d95be03`.

## Verified fact: TOOL-B8 is ALREADY implemented
The mission brief anticipated "if B8 is not implemented, recommend TOOL-B8 v5." **Repository evidence shows B8 v5 IS implemented and tested:** `finalis/ai_employee/tool_commit_simulation.py` (1,814 LOC), `tool_commit_simulation_store.py`, migration **v23**, 34 test files / **444 tests** passing, committed `d95be03`, pushed. Therefore B8 is **not** the next SP.

## Recommended next SP: **TOOL-B9**

**TOOL-B9 — Controlled Internal Commit Runtime for Local Reversible State**
with Effector-Exclusive Gate, Commit Attestation, Emergency Abort, Local-Only Write Scope, and No External Providers.

### Why B9 is correct (evidence)
The B1→B8 ladder is monotonic authority-narrowing and ends at **simulation-only** pre-B9 assurance. B8 already emits the exact contracts B9 must honor:
- **Non-Delegable Artifact Seal** — B8 artifacts must never become authority.
- **B9 Input-Contract Negative Capability** — B9 must reject 7 B8 artifact types as authority and **recompute 10 factors** (approval freshness, state witness, consent, legal policy, customer impact, conflict oracle, revalidation debt, no-commit precheck, local write scope, emergency abort).
- **B9 Revalidation Contract** — B9 pre-authorizes nothing.

B9 is the first layer that may perform a **real (but strictly local, reversible)** write, gated by all of the above.

### B9 scope guardrails (do / don't)
**DO:**
1. Consume a B8 assurance envelope **as evidence only**; independently recompute every one of the 10 B9 factors.
2. Enforce an **effector-exclusive gate** (single-writer, local reversible state only).
3. Emit a **commit attestation** + hash-chained commit log; keep it reversible.
4. Provide **emergency abort / kill-switch** with rollback.
5. Confine to **local write scope**; ship a B9 fault-injection harness + release gate proving no external effect escapes.

**DON'T (defer to later SPs):**
- No external providers, MCP, or LLM runtime.
- No real payment / CRM-external / evidence-external mutation / message send / export.
- No production auth/persistence/deployment work inside B9.

## Emergency fixes required before B9
**None.** The audit found no critical blocker. The repo is internally consistent, 4601 tests green, no forbidden route, no authority-leak path.

## Non-blocking hardening that can run in parallel (separate SPs, not before B9)
1. Auth hardening (JWT/OIDC/SSO/MFA/secret-manager/login-rate-limit).
2. Persistence migration (SQLite→Postgres, local FS→object store) behind existing seams.
3. Evidence external anchoring + report signing (RFC 3161 / Sigstore-Rekor / KMS).
4. Decompose `app.py` (10,083 LOC) and `ui.py` (3,691 LOC) after B9 stabilizes.

## What should NOT be built yet
Real external providers, real payment/CRM/evidence mutation, MCP/LLM runtime, and production infrastructure — **until B9's local reversible commit gate exists and is proven fail-closed.**

## One-line recommendation
**Proceed to TOOL-B9 (Controlled Internal Commit Runtime, local reversible, no external providers). Repo is safe to continue; no emergency fix needed.**
