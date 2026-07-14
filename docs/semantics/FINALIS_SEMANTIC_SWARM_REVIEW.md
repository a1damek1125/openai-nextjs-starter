# FINALIS 1000 — SP0002 Swarm Review & Acceptance Evidence

**Semantic Operating Constitution.** Audit trail: baseline, swarm roles, loop,
research, semantic collision report, mutation campaign, red-team + repairs,
independent verification, 87-criterion acceptance matrix.

## 1. Baseline (verified)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-11 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `19413f2` (SP0001) |
| SP0000 | COMPLETE (25/25) · SP0001 | baseline VALID (50/50) — precondition §2.2 met |
| LATEST_MIGRATION | v27 (unchanged) |
| CURRENT_RUNTIME_FRONTIER | EMP-A1 |

## 2. Swarm roles + loop

Repository Semantic Archaeology (main-loop) → 2 independent research agents
(academic semantics + standards) → Canonical/Epistemic/Temporal modeling
(main-loop) → tooling → mutation campaign → **SWARM-K red-team** → repair →
**SWARM-L independent verifier**. The loop did not stop at first green.

## 3. Semantic collision report (first deliverable)

`FINALIS_SEMANTIC_COLLISION_REPORT.md`, grounded in grep evidence: `completed`
overloaded ≥9 ways; `capability` triple-overloaded (RBAC/tool/SP0001-architecture);
`claim`/`fact`/`verified` epistemic conflation; `task`(CORE-A2) ≠
`work_item`(EMP-A1); `case`(646) ≠ `run`(402); `employee`/`worker`/`agent`
distinct. Decisions: canonical `completed` family + alias map, epistemic type
system, 6 preserved distinctions, all external vocab via anti-corruption. No code
renamed.

## 4. What was built

`tools/semantics/` (stdlib-only, deterministic): 33-concept Canonical Concept
Registry with Meaning Hashes · Epistemic Type System · World-Assumption contracts
· bitemporal Semantic Epochs · Compatibility Algebra (denotational where
decidable) · relationship graph + impact cone · resolution + Quarantine ·
Semantic Transaction (breaking→new epoch, no partial rollout) · Dual-Semantics
Shadow Evaluation · Historical Replay · Protocol Anti-Corruption projections ·
Agent Semantic Capsule + progressive disclosure · LGGT Bridge · multilingual
PL/EN/DE/ES · Proof-Carrying Semantic Change Envelope · Drift Observatory · CLI.
Baseline registry validates **P0=0, P1=0, P2=0**; deterministic attest. Product
code never imports it.

## 5. Mutation campaign (§20.15)

`tests/test_semantics_mutation.py` — every corruption caught: `completed`=tool-
finished (squatting → FORBIDDEN_ALIAS P0), `fact`=model-guess (LLM→FACT P0),
`employee`=`worker` (FORBIDDEN_ALIAS), `worker`=`agent` (AMBIGUOUS P1), shared
LGGT predicate (collision P0), external field declared canonical (TAKEOVER P0),
breaking-without-epoch (P0), **undecidable-widening evasion (P1)**, partial
rollout (P0), translation-changes-meaning (hash change), quarantine bypass
(no-authority by construction), unknown→quarantine, schema-valid-semantic-invalid.

## 6. Red-team (SWARM-K) findings + repairs

SWARM-K ran 12 empirical attacks. **10/12 fully caught**: duplicate id/key (P0),
forbidden-alias squatting (P0), ambiguity (P1), bad owner/world/relationship (P1),
meaning-hash forgery (P1), quarantine authority-leak (impossible by construction),
external takeover (P0), LLM→fact ceiling (P0), cross/same-epoch LGGT collision
(P0), historical reinterpretation (returns original epoch), `attest` determinism.
No LLM/score can override a P0/P1; product code does not import the tooling. Two
related gaps found and **all repaired + regression-locked** (`tests/test_semantics_redteam.py`):

| Finding | Sev | Repair | Test |
|---|---|---|---|
| **B1** `models` (the denotational compatibility input) excluded from the Meaning Hash → a model-set widening is invisible to the hash and the transaction gate | P1 latent (P0 once `models` used) | Added `"models"` to `canon.SEMANTIC_CORE_FIELDS`; a models widening now changes the hash and is caught as WIDENING → BREAKING (P0) | `test_models_widening_changes_meaning_hash`, `test_models_widening_detected_as_breaking_in_transaction` |
| **B4** an undecidable (NL-only) meaning change mislabeled `EDITORIAL`/`NARROWING` could skip the new-epoch requirement silently | P1 | Undecidable changes are **never fully silent**: undeclared → P1 `BREAKING_CHANGE_WITHOUT_EPOCH`; declared non-breaking → always a P2 `SEMANTIC_REVIEW_REQUIRED` (unverifiable self-claim surfaced for shadow/human review, AC-0002-39) | `test_undecidable_change_declared_editorial_still_surfaces_p2`, `test_undecidable_change_undeclared_is_p1` |
| **B2** `detect_epoch_downgrade` failed OPEN on an unknown current epoch | P2 | Now fails **closed** (unknown epoch → suspicious → True) | `test_epoch_downgrade_fails_closed_on_unknown_current` |
| **B3** downgrade verdict input-order-dependent on equal timestamps | P2 | Deterministic total order `(valid_from, recorded_at, semantic_epoch_id)` | `test_epoch_downgrade_deterministic_on_equal_timestamps` |

Also cleaned the shadowed duplicate `main` in the CLI. Post-repair: registry
validates P0=0/P1=0; **116 semantics tests pass**; no P0/P1 gap remains.

## 7. Acceptance-criteria matrix (87)

Independently verified by **SWARM-L** (did not author the tooling). Gate
reproductions: `validate` → P0=0/P1=0/P2=0 (33 concepts); `attest` ×2 → identical
`45c4965e…`; `pytest tests/test_semantics_*.py` → **116 passed**; `grep
tools.semantics finalis/` → empty; product change-surface empty; migration v27;
all 33 stored `meaning_hash` recomputed → 0 mismatches. **All 4 red-team repairs
(B1/B2/B3/B4) independently confirmed to hold.**

**Result: 87 / 87 PASS** (SWARM-L verified 86/87; AC-0002-80 = full suite,
confirmed green in §8 below). Summary by group:

| Group | ACs | Verdict | Representative evidence |
|---|---|---|---|
| Preconditions + baseline | 01-03 | PASS | `test_sp0000_and_sp0001_precondition`, `test_real_registry_valid`, `test_registry_deterministic` |
| Collision report + terms | 04-05 | PASS | `FINALIS_SEMANTIC_COLLISION_REPORT.md` (`completed`≥9, `capability`×3, claim/fact/verified) |
| Registry / identity / epoch | 06-12 | PASS | dup id/key P0, owner P1, meaning-hash stored, bitemporal `interpret_under` |
| Epistemic distinctions | 13-17 | PASS | claim≠fact, LLM→fact P0, certified≠fact, confidence≠status, valid promotions |
| World assumptions | 18-21 | PASS | open=unknown, closed=false, partial=needs-scope, presence=true |
| Meaning hash | 22-24 | PASS | deterministic; normative→changes; label/alias→stable |
| Relationships / alias / ambiguity | 25-27 | PASS | typed + target-exists; alias resolve; 48 forbidden aliases |
| Seven concept distinctions | 28-34 | PASS | task≠owned_work, case≠run, action/effect/outcome/completion, claim≠fact, evidence≠artifact, tool/skill/capability, employee/worker/agent |
| Compatibility algebra | 35-39 | PASS | equivalent/narrowing/widening(breaking)/incompatible; unknown→REVIEW_REQUIRED (never falsely certified) |
| Change intent / transaction | 40-43 | PASS | intent validate; breaking→new epoch; partial rollout P0 |
| Shadow + replay | 44-46 | PASS | expected vs unexpected divergence; replay reproduce/documented/unexplained |
| Quarantine | 47-50 | PASS | unknown/ambiguous quarantined; no authority through any transition |
| Projections / anti-corruption | 51-55,75 | PASS | OpenAPI/MCP/A2A = projections; unmapped→quarantine; canonical-field→TAKEOVER P0 |
| Twin separation | 56-57 | PASS | `SEMANTIC_DOMAIN_TWIN` distinct from architecture `DECLARED` twin |
| Capsule + progressive disclosure | 58-59 | PASS | critical invariants always included even at level 0; unrelated excluded |
| Multilingual | 60-66 | PASS | PL/EN/DE/ES; BCP47; translation conflict; translation preserves hash |
| LGGT bridge | 67-69 | PASS | explicit mapping; predicate collision P0; epoch binding |
| Proof envelope | 70-72 | PASS | deterministic; tracks registry/validity; evidence-not-authority |
| Drift observatory | 73-74 | PASS | deterministic; advisory not a gate |
| LLM/external cannot create concepts | 76-77 | PASS | LLM→fact blocked; schema-valid-semantic-invalid rejected |
| No product change / migration | 78-79 | PASS | tooling not imported; v27 unchanged |
| Full suite / mutation / swarm / verify | 80-83 | PASS | §8; mutation 14/14; this document; SWARM-L |
| P0=0 / P1=0 / URLs / honesty | 84-87 | PASS | validate counts; research register 25 URLs + honesty section |

## 8. Full regression

`python3 -m pytest tests/ --ignore=tests/test_browser_e2e.py` on the final tree,
run as 4 balanced parallel shards (410 test files, browser e2e excluded):

| Shard | Exit | Passed | Failed | Errors |
|---|---|---|---|---|
| 0 | 0 | 1407 | 0 | 0 |
| 1 | 0 | 1633 | 0 | 0 |
| 2 | 0 | 1366 | 0 | 0 |
| 3 | 0 | 1453 | 0 | 0 |
| **Total** | **0** | **5859** | **0** | **0** |

**5859 passed, 0 failed, 0 errors — all shards exit 0.** This total includes the
116 new SP0002 semantics tests. Zero tracked product files were modified by
SP0002 (only new untracked additions under `docs/semantics/`, `tools/semantics/`,
and `tests/test_semantics_*`), so the pre-existing product suite is byte-identical
to the SP0001 green baseline and provably cannot regress; the run confirms it
empirically.

## 9. Final verdict

**SP0002 — FINALIS SEMANTIC OPERATING CONSTITUTION: ACCEPTED.**

All 87 acceptance criteria (AC-0002-01 … 87) have evidence. Gate satisfied:

- Baseline registry validates **P0 = 0, P1 = 0, P2 = 0** across 33 canonical concepts.
- `attest` is deterministic (`45c4965e…` reproduced across runs); envelope is
  classified `EVIDENCE_NOT_AUTHORITY`.
- **116** semantics tests pass; the **full regression suite is green (5859 passed,
  0 failed, 0 errors)** — AC-0002-80.
- Product code never imports `tools.semantics`; latest DB migration remains **v27**
  (unchanged); **zero** product runtime files were modified (AC-0002-78/79).
- Mutation campaign 14/14 corruptions caught; SWARM-K red-team ran 12 attacks,
  4 gaps (B1–B4) found, all **repaired and regression-locked**; SWARM-L
  independently re-verified the criteria and the four repairs.

No P0 or P1 remains open. The Semantic Domain Twin is authoritative for meaning;
all external standards (MCP / A2A / OpenAPI / SHACL / LGGT) enter only as
projections through anti-corruption, never as internal authority. "One concept,
one authoritative meaning per semantic epoch" holds.