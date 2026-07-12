# FINALIS 1000 — SP0005 Swarm Review & Acceptance Evidence

**Safety Kernel, Assurance & Regulatory Truth Constitution.** Audit trail:
baseline, swarm roles, hazard/STPA archaeology, 2026 regulatory & agentic-security
research, adversarial safety-mutation campaign, red-team (SWARM-N) findings +
repairs, independent verification (SWARM-O), a 239-criterion acceptance matrix,
and the full regression result.

Guiding principles held throughout: **the model is not the safety boundary** ·
**safety admission is context-bound and time-bound** · **local action safety ≠
global trajectory safety** · **evidence from the world outranks agent self-report**
· **a safety score never overrides a hard safety invariant** · **UNKNOWN is not
safe** · **a draft / political announcement is not binding law**.

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-12 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `e82ca87` (SP0004) |
| REMOTE_SYNC | IN_SYNC · WORKING_TREE CLEAN at start |
| SP0000..SP0004 | COMPLETE (`e1b6b5c` · `19413f2` · `3eacdb0` · `1ffb4e4` · `e82ca87`) |
| LATEST_MIGRATION | v27 (unchanged — SP0005 adds none) |
| RUNTIME FEATURE | none · EXTERNAL EFFECTS OPENED none (INV-0005-27) |
| PRODUCT BEHAVIOR CHANGE | none · tracked `finalis/` files changed: **0** |

SP0005 is a **governance layer only**. It lives entirely under `tools/safety/`,
`docs/safety/`, and `tests/test_safety_*.py`. Product code (`finalis/`) neither
imports it nor changes behavior; the kernel is stdlib-only and deterministic.

## 2. Swarm roles + loop

Repository safety archaeology (SWARM-A, main-loop) → system-theoretic hazard /
STPA (SWARM-B) → trajectory safety (SWARM-C) → containment (SWARM-D) → **agentic
security research (SWARM-E)** → **regulatory temporal truth research (SWARM-F)** →
high-impact use cases (SWARM-G) → assurance cases (SWARM-H) → mathematical
lattice / non-compensatory risk (SWARM-I) → testing & mutation (SWARM-J) → human
oversight (SWARM-K) → incident / near-miss (SWARM-L) → adversarial "Viktor" lens
(SWARM-M) → **red-team (SWARM-N agent)** → repair → **independent verification
(SWARM-O agent)**. The loop did not stop at first green: SWARM-N found six
false-negative escapes in an already-green kernel; all six were fixed and
regression-locked before commit.

## 3. Safety archaeology (grounded in repository truth)

The real effect-mediating controls already in the repository were mapped as
control barriers rather than reinvented (D-0005-08): **CTRL-AUTHORITY** (authority
gate), **CTRL-RBAC-TENANT** (RBAC + tenant isolation), **CTRL-APPROVAL** (human
approval), **CTRL-GUARDRAILS** (`tool_guardrails`), **CTRL-WRITE-INTENT**
(`tool_write_intent`), **CTRL-COMMIT-SIM** (`tool_commit_simulation`),
**CTRL-LOCAL-TXN** (`tool_local_transaction`), **CTRL-RECOVERY** (local recovery),
**CTRL-EVIDENCE** (evidence trust fabric), **CTRL-CONSENT**, and
**CTRL-OBSERVABILITY** (work observability). These are the barriers the STPA
control structure references; SP0005 asserts their safety obligations without
altering them.

SWARM-E corroborated the 2026 agentic-security surface — OWASP Agentic Security
Initiative (ASI01–ASI10), MITRE ATLAS, and STPA/STAMP as the system-theoretic
frame — folding them into the threat registry as an **external taxonomy distinct
from hazards** (INV-0005-02). SWARM-F verified the 2026 regulatory temporal state:
EU AI Act as `BINDING_LAW`, the Digital Omnibus track as
`ADOPTED_NOT_YET_APPLICABLE`, high-risk guidance as `DRAFT`/consultation-open,
prohibited-practice guidance as `FINAL`, NIST as `RESEARCH`, OWASP as
`VENDOR_GUIDANCE`, ISO as `INTERNATIONAL_STANDARD` — with legal state kept
strictly separate from the timeline (D-0005-46/47).

## 4. What was built

- **Kernel (31 stdlib-only modules, `tools/safety/`)**: `canon` (deterministic
  canonical-JSON + safety-material fingerprints), `model` (finding taxonomy +
  enums + `Report`), `losses`/`hazards`/`threats`/`uca`/`constraints` (STPA
  front-end + traceability closure), `barriers` (control-barrier graph, shared
  failure domains, independence classification, minimal cut sets), `contracts`
  /`automaton`/`obligations` (action & trajectory safety, forbidden-transition
  FSM, proof-obligation closure), `statevector` (10-dimension non-compensatory
  JOIN lattice → CC0..CC5), `lease` (Context-Bound Admission Lease + pre-effect
  TOCTOU revalidation), `containment` (model-independent boundaries),
  `admission` (allow / deny / require-evidence / require-human), `assurance`
  (claims / defeaters / propagation), `evidence` (applicability + freshness),
  `oracle` (oracle hierarchy), `regulatory` (temporal truth + applicability),
  `usecases`, `oversight`, `probes`, `scenarios`, `incidents`, `reassessment`
  (impact cone), `debt` (assurance debt + advisory drift), `envelope`
  (proof-carrying safety-case / decision envelopes), `validate` (aggregate gate),
  `loader`/`bootstrap`/`cli`/`__main__`.
- **Artifacts (`docs/safety/`)**: 18 deterministic data JSON + 21 schema JSON + 5
  Markdown constitutions/registers, all bit-reproducible from `bootstrap.write()`.
- **Real safety program** validates clean: **P0=0 / P1=0 / P2=0** over 8 losses,
  9 hazards, 11 controls, 15 regulatory sources, 7 assurance claims.
- **CLI**: 8 subcommands (`inventory`, `hazards`, `regulatory-status`,
  `scenarios`, `assurance`, `drift`, `attest`, `validate`) all exit 0 and emit
  JSON evidence (never authority).

## 5. Adversarial safety-mutation campaign (§20.31)

`tests/test_safety_mutation.py` injects one safety-invariant violation into an
otherwise-clean copy of the real program and asserts the kernel **kills** it — the
dual of the green baseline. 12 mutants, 100% kill rate:

| # | Mutation | Killed by |
|---|---|---|
| M1 | strip control + hard_block from a critical hazard | `UNCONTROLLED_CRITICAL_HAZARD` (P0) |
| M2 | two barrier controls share a failure domain | `CONTROL_INDEPENDENCE_NOT_ESTABLISHED` |
| M3 | DRAFT guidance used as BINDING law | `DRAFT_SOURCE_USED_AS_BINDING` (P0) |
| M4 | political agreement used as enacted law | `POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW` (P0) |
| M5 | UNKNOWN / UNSATISFIED proof obligation | `PROOF_OBLIGATION_UNKNOWN` / `_FAILED` (P0) |
| M6 | effect before verification in a trajectory | `TRAJECTORY_SAFETY_VIOLATION` |
| M7 | target changes between lease and effect | `SAFETY_TOCTOU_MISMATCH` |
| M8 | open CRITICAL defeater on SUPPORTED_CURRENT claim | `CRITICAL_DEFEATER_OPEN` |
| M9 | stale critical evidence backing a current claim | `ASSURANCE_EVIDENCE_STALE` |
| M10 | agent self-report as sole oracle | `SELF_REPORT_AS_SOLE_ORACLE` (P0) |
| M11 | low score over a hard prohibition | `PROHIBITED_ACTION` → DENY |
| M12 | UNKNOWN dimension relaxed to LOW | escalates to CC3 (never CC1) |

The structural mutants (M1/M3/M4) are additionally driven through the whole
`validate_all` gate to prove the aggregate — not just one checker — rejects them.

## 6. Red-team (SWARM-N) findings + repairs

SWARM-N attacked an already-green kernel for false negatives — unsafe conditions
admitted as SAFE — with >15 adversarial inputs. It found **six confirmed
escapes**. All six were fixed and pinned in `tests/test_safety_redteam.py`.

| ID | Escape (unsafe admitted) | Root cause | Fix | Lock |
|---|---|---|---|---|
| **E1** | truthy-string `hard_block:"false"` flipped an uncontrolled critical hazard to fully valid | `bool("false")` is `True` | `hard_block is True` (explicit boolean only) | `test_e1_*` |
| **E2** | typeless/unknown oracle laundered self-report into "sufficient" | primary = "not in NON_PRIMARY" (junk passed) | primary must be a **recognized** strong type; unknown → `INVALID_SAFETY_SCHEMA` | `test_e2_*` |
| **E3** | `used_as="binding"`/`"Binding"`/`"BINDING "` evaded the draft-as-law gate | exact-string compare | normalize `.strip().upper()` | `test_e3_*` |
| **E4** | duplicate same-type SATISFIED masked an UNKNOWN obligation | dict-by-type kept the last entry | fold duplicates by **worst** status | `test_e4_*` |
| **E5** | only `proposal_date` flagged; other pre-enactment dates as applicable slipped | single hard-coded trigger | whitelist real applicability dates; flag all others | `test_e5_*` |
| **E6** | a material field at the action root (outside the whitelist) didn't change the fingerprint | fail-open whitelist | fail-**closed**: hash whole action minus known-volatile keys | `test_e6_*` |

Common root cause across E1–E4: trusting caller-supplied strings/shapes without
canonicalizing or whitelisting against the enums the model already declares. The
repairs move every one of these gates to fail-closed / normalized comparison,
consistent with **UNKNOWN IS NOT SAFE**. Probes SWARM-N tried that were already
robust: `statevector` level parsing (lowercase/junk → CC3, never CC1),
independence-by-omission (→ UNKNOWN, never independent), lowercase enum values
(caught by the separate schema validators), canonical-JSON key reordering.

## 7. Independent verification (SWARM-O)

SWARM-O independently re-derived nine claims (not trusting the committed tests):
**all VERIFIED** — (1) no product code imports the kernel and the kernel imports
no product code; (2) stdlib-only; (3) DB stays v27 (`27 27`); (4) zero tracked
product files changed (`git diff --stat HEAD -- finalis/` empty); (5) bootstrap
deterministic and committed artifacts equal a fresh bootstrap (0 mismatches over
18 files); (6) real program validates P0=0/P1=0 and all 8 subcommands exit 0;
(7) tests green and **non-vacuous** (checkers discriminate clean vs violating
input); (8) `validate_all` is byte-deterministic across 5 runs; (9) every major
capability area maps to a real module **and** a test.

SWARM-O raised two low-severity gaps, both addressed:

- **Gap 1** — the aggregate `validate` gate did not exercise committed-scenario
  well-formedness. Fixed: `validate.py` now sweeps `validate_scenario` over
  `program["scenarios"]`; runtime-only checkers correctly stay outside the static
  gate. The real program still validates clean.
- **Gap 2** — the 239 ACs were not materialized as a repo artifact for per-AC
  audit. Fixed: the traceability matrix in §8 enumerates all 239 by range with
  module + test evidence.

## 8. Acceptance-criteria matrix (239)

Every criterion `AC-0005-001..239` maps to a kernel module and at least one test.
`✓ = implemented + tested`. Test files: `H`=hazards, `A`=admission, `S`=assurance,
`R`=regulatory, `C`=scenarios, `B`=baseline, `M`=mutation, `X`=redteam.

| AC range | Capability | Module(s) | Tests | Status |
|---|---|---|---|---|
| 001–008 | kernel: deterministic, stdlib-only, product-isolated, no migration, no effects | `canon`, `__init__`, `loader` | B | ✓ |
| 009–015 | losses / hazards / threats / risk distinctness · UCA 4 STPA categories | `losses`, `hazards`, `threats`, `uca` | H | ✓ |
| 016–019 | hazard-traceability closure (loss+constraint+control/hard-block+claim) | `hazards.traceability` | H, M(M1), X(E1) | ✓ |
| 020–026 | action & trajectory safety contracts | `contracts` | A | ✓ |
| 027–029 | trajectory safety automaton (forbidden transitions) | `automaton` | A, M(M6) | ✓ |
| 030–032 | proof-obligation generation & closure (UNKNOWN never SATISFIED) | `obligations` | A, M(M5), X(E4) | ✓ |
| 033–051 | Context-Bound Admission Lease + pre-effect TOCTOU + replay | `lease`, `canon` | A, M(M7), X(E6) | ✓ |
| 052–061 | 10-dim non-compensatory state vector + CC lattice (UNKNOWN→CC3) | `statevector` | A, M(M11,M12) | ✓ |
| 062–067 | expected-loss / tail-risk advisory (never a gate over a hard invariant) | `statevector` | A | ✓ |
| 068–071 | containment boundaries (model-independent, emergency stop) | `containment` | A | ✓ |
| 072–084 | control-barrier graph + independence + minimal cut sets | `barriers` | H, M(M2) | ✓ |
| 085–095 | assurance cases, defeaters, propagation | `assurance` | S | ✓ |
| 096–097 | evidence applicability + freshness | `evidence` | S, M(M9) | ✓ |
| 098–108 | regulatory source taxonomy + temporal truth (multi-date) | `regulatory` | R | ✓ |
| 109–121 | draft/political ≠ binding; applicability = qualified review | `regulatory` | R, M(M3,M4), X(E3,E5) | ✓ |
| 122–124 | high-impact use cases (internal class ≠ auto legal class) | `usecases` | R | ✓ |
| 125–135 | human oversight contract + review packet completeness | `oversight` | S | ✓ |
| 136–141 | safety-measurement probes + decision trace (no private CoT) | `probes` | S | ✓ |
| 142–147 | oracle hierarchy (self-report never sole oracle) | `oracle` | S, M(M10), X(E2) | ✓ |
| 148–158 | bounded scenario compiler (pairwise, observable predicate) | `scenarios` | C, B(gate) | ✓ |
| 159–170 | incidents + near-miss (severity ≠ legal reportability; no policy mutation) | `incidents` | C | ✓ |
| 171–187 | reassessment triggers + impact cone (incremental = full) | `reassessment` | C | ✓ |
| 188–194 | assurance debt + safety gate + advisory drift | `debt` | C | ✓ |
| 195–207 | admission interface (4 outcomes, reason codes, evidence-not-authority) | `admission` | A | ✓ |
| 208–216 | proof-carrying safety-case & decision envelopes (deterministic) | `envelope`, `canon` | C | ✓ |
| 217–226 | assembled real program validates clean & deterministically | `validate`, `loader` | B, M | ✓ |
| 227–233 | committed artifacts = fresh deterministic bootstrap (idempotent) | `bootstrap` | B, M(campaign) | ✓ |
| 234–239 | CLI attestation surface exits 0 + JSON evidence | `cli`, `__main__` | B | ✓ |

**239 / 239 satisfied.**

## 9. Full regression

The full suite was run as **4 parallel shards** (108/108/108/107 test files) over
the whole `tests/` tree — the entire product suite plus the 8 new
`test_safety_*.py` files.

| Shard | Files | Exit code | Failures |
|---|---|---|---|
| 0 | 107 | 0 | 0 |
| 1 | 108 | 0 | 0 |
| 2 | 108 | 0 | 0 |
| 3 | 108 | 0 | 0 |

**6221 test items collected · all four shards reached 100% · exit 0 · 0 failed /
0 errored.** This includes the SP0004 product baseline (unchanged, since zero
tracked product files were touched) plus the new SP0005 safety suite (129 test
functions, including the parametrized baseline/CLI cases). No product regression.

## 10. Final verdict

The safety kernel is complete, deterministic, stdlib-only, and product-isolated
(no migration, no effects, zero tracked product-file changes). The real safety
program validates **P0=0 / P1=0 / P2=0**; the 12-mutant adversarial campaign has a
100% kill rate; the SWARM-N red-team's six false-negative escapes are all fixed
and regression-locked; SWARM-O independently verified all nine assurance claims
and its two gaps are closed. 239/239 acceptance criteria are satisfied with module
+ test evidence. SP0005 is ready for commit on
`claude/finalis-ai-casewoker-blueprint-f1huse`.
