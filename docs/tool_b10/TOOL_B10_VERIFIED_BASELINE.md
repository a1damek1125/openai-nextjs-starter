# TOOL-B10 Verified Baseline

Recorded facts of the baseline TOOL-B10 V3 operates over. Git SHAs and counts are observed,
not fabricated.

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-12 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `7d2c44a` |
| REMOTE_HEAD | `7d2c44a` |
| LOCAL_REMOTE_SYNC | equal (local == remote) |
| WORKING_TREE | clean at start |
| MIGRATION_FRONTIER | **v20** (AST/regex-extracted from `finalis/portal/db.py` `MIGRATIONS`) |
| FULL_TEST_COMMAND | `python -m pytest` |
| TESTS_COLLECTED | 230 test files, **2982 `def test_` functions** |
| BROWSER_E2E_STATE | environment-sensitive (excluded from deterministic runs by convention) |
| KNOWN_ENVIRONMENT_INSTABILITIES | live-browser E2E timing under parallel load |
| CORE_A1..A6_COMMITS | present in history (…→ `80ea4d0` CORE-A6) |
| TOOL_B1_COMMIT | `d08c07c` (Zero-Trust Tool Capability Governance Registry) |
| TOOL_B2_COMMIT | `da02379` (Tool Descriptor Assurance Graph) |
| TOOL_B3_COMMIT | `dd24cd8` (Protocol Contract Proof Kernel) |
| TOOL_B4_COMMIT | `7d827ff` (Causal Pre-Action Reference Monitor) |
| TOOL_B5_COMMIT | `7d2c44a` (Proof-Carrying Null Broker) — **HEAD, verified present** |
| TOOL_B5_CLASSIFICATION | deterministic internal broker, NULL_EFFECT_ONLY, executes nothing |

## Existing substrate inventoried (extend, not rebuild)

- **EXISTING_TOOL_MODELS:** `finalis/ai_employee/tool_{registry,contracts,guardrails,quality,broker}.py` (+ `_store.py`) — TOOL-B1..B5.
- **EXISTING_EVIDENCE_MODELS:** `finalis/evidence/{immutability,transparency,requirements,views,gates,policy,derivatives,models,storage,rehydration,scores,scanners,engine,reports}.py`; `finalis/portal/evidence_store.py`; `finalis/lifecycle/evidence.py`.
- **EXISTING_MEMORY_MODELS:** `finalis/crm/memory.py`.
- **EXISTING_TENANT_CONTROLS / AUTHORITY / APPROVAL:** `finalis/portal/{app,db}.py`, `finalis/ai_employee/{authority,approvals,approval_decisions}.py`.
- **EXISTING_CONTEXT / RETRIEVAL / COMPACTION / CACHE / TOKEN-BUDGET code:** none dedicated (context-governance layer is new — no parallel system to conflict with); SWARM-B archaeology confirms the exact reuse points.
- **EXISTING_MIGRATIONS:** frontier v20; TOOL-B10 adds none by default.

## Gates

- `BLOCKED_BY_MISSING_TOOL_B5`: **not triggered** — TOOL-B5 verified present at HEAD.
- `BLOCKED_BY_TOOL_B10_BASELINE`: **not triggered** — no unexplained P0/P1; clean tree, local==remote.
- `BLOCKED_BY_TOOL_B10_SCOPE_MISMATCH`: **not triggered** — no conflicting canonical TOOL-B10 subject (see roadmap identity report §1).

## Change boundary

TOOL-B10 work is confined to `tools/context_governance/`, `docs/tool_b10/`,
`tests/test_context_governance_*.py`. Product runtime under `finalis/` is unchanged;
migration frontier remains v20; no live external effect occurs. The full 2982-test
repository regression is re-run and reported honestly before the final commit; the new
kernel is a self-contained package that no existing product code imports, so it cannot
regress the existing suite.
