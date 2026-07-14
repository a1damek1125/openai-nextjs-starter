# FINALIS SP0007 — Swarm Review & Acceptance Evidence

**Backward Compatibility, Migration, Versioning & Contract Evolution
Constitution.** Audit trail: roadmap identity preflight, swarm roles, repository
contract archaeology, standards research, the built kernel, the adversarial
mutation campaign, the SWARM-M red-team findings + repairs, SWARM-O independent
verification, a 200-criterion acceptance matrix, and the full regression result.

Guiding distinctions held throughout: **newer ≠ compatible · same schema ≠ same
semantics · SemVer label ≠ compatibility proof · up migration ≠ rollback ·
producer ≠ consumer compatibility · replay passed ≠ all histories safe ·
deprecated ≠ removed · version adapter ≠ semantic authority · proof is evidence,
not authority.**

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-12 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `d6ac046` (SP0006) |
| REMOTE_SYNC | IN_SYNC · WORKING_TREE CLEAN at start |
| SP0000..SP0006 | COMPLETE (`e1b6b5c`·`19413f2`·`3eacdb0`·`1ffb4e4`·`e82ca87`·`610e1e3`·`d6ac046`) |
| LATEST_MIGRATION | v27 (unchanged — SP0007 adds none) |
| TESTS_BEFORE | 6382 collected items |
| PRODUCT BEHAVIOR CHANGE | none · tracked product files changed: **0** |
| LIVE MIGRATION / EXTERNAL EFFECTS | none (INV-0007-47) |

## 2. Roadmap identity

The mandatory preflight found the canonical Program-Twin SP0007 title
**"Compatibility, Migration and Versioning Policy"** is **semantically
equivalent** to this V2 (Backward Compatibility, Migration, Versioning & Contract
Evolution Constitution) — the V2 is the same mission with stronger explicit
requirements. Per §2.1 rule 1: proceed under the repository title, retain the
compatible hardening. `BLOCKED_BY_SP0007_SCOPE_MISMATCH` did **not** apply. The
Evaluation charter remains at **SP0011** (from the SP0006 reassignment);
SP0008–SP0010 are unchanged; SP0007 renumbers nothing and — unlike SP0006 —
modifies **zero** existing tracked files. See `SP0007_ROADMAP_IDENTITY_REPORT.md`.

## 3. Swarm roles + loop

Roadmap identity → **repository contract archaeology (SWARM-A agent)** → contract
surface taxonomy → producer–consumer graph → directional compatibility algebra →
contract difference engine → semantic analysis (SP0002) → historical corpus →
behavioral & replay testing → **6 parallel build agents (SWARM-B..I roles)** →
migration graph / expand-migrate-contract → loss & reversibility → rollback &
forward-fix → deprecation & sunset → fitness functions → **3 parallel test
agents** → **adversarial mutation campaign** → **red-team (SWARM-M agent)** →
repair → **independent verification (SWARM-O agent)**. The loop did not stop at
first green: SWARM-M found 10 false-negative escapes in an already-green kernel;
all 10 were fixed and regression-locked before commit.

## 4. Repository contract archaeology (SWARM-A) — reference, never rebuild

The real surfaces SP0007 governs (never modifies): **405 FastAPI routes**
(dict-shaped bodies — no pydantic/OpenAPI, recorded as compatibility debt), **3
hash-protected event families** (case audit chain, run-ledger canonical envelope
`finalis-run-event-v1`, EMP-A1 idempotent intake), **27 forward-only DB
migrations** (no down migrations exist — schema rollback is constitutionally
UNKNOWN until inverses are built + verified), **4 replay-protected state machines**
(17-state Case FSM, 24-state lifecycle kernel, 12-status run ledger, 23-state
EMP-A1 inbox), **~371 version-pinned proof-envelope identifiers**, 6 governance
CLIs, and 11 provider Protocol seams. Two canonicalization dialects were recorded
as REVIEW_REQUIRED debt, not changed.

## 5. What was built

- **Kernel (24 stdlib-only modules, `tools/compatibility/`)**: `canon`, `model`,
  `contracts` (descriptor/version registries + immutability + SemVer-as-
  declaration), `vector` (directional consumer-specific claims + non-averageable
  hard gate + freshness + anti-transitivity), `diff` (field-by-field difference
  engine + breaking classifier), `policies` (unknown-field / reserved-identifier
  / enum / default / nullability / temporal / event-identity / idempotency),
  `counterexample` (minimal-witness reducer), `corpus` (historical fixtures +
  sufficiency + immutability), `replay` (workflow replay + proof interpretability
  + differential + metamorphic), `negotiation` (pinning / fail-closed negotiation
  / downgrade / firewall / adapters / bridges), `migration` (graph + lexicographic
  path selection + progress conservation), `transformer` (loss vector + round-trip
  + tenant safety), `backfill` (checkpointed + lease + barrier), `rollback`
  (Last Safe Rollback Point + forward-fix), `plan` (expand-migrate-contract +
  dual-read/write + shadow), `deprecation` (registry + sunset gate + support
  windows), `fitness` (9 fitness functions + debt + observatory), `intent`
  (change intent + impact cone), `modelcheck` (bounded explorer), `envelope`
  (4 proof envelopes), `validate`, `loader`, `bootstrap`, `cli`, `__main__`,
  `__init__`.
- **Artifacts (`docs/compatibility/`)**: 32 deterministic JSON (13 data + 19
  schema) + 4 Markdown (constitution, research register, roadmap identity report,
  this review), all bit-reproducible from bootstrap.
- **Real Compatibility Twin** validates **P0=0 / P1=0 / P2=0** (10 contract
  descriptors across all 10 surfaces, 10 released+sealed versions, 6 directional
  claims, 10-fixture corpus, 2 migration edges, 1 expand-migrate-contract plan,
  1 deprecation + support window).
- **CLI**: `roadmap-identity`, `inventory`, `validate`, `modelcheck`, `diff`,
  `fitness`, `observatory`, `impact`, `attest` — all emit JSON evidence.
- **Bounded model checking**: 5 models all `HOLDS` — migration-plan state
  machine, checkpoint/restart, dual-write, deprecation/sunset, rollback boundary
  — with counterexamples on violating variants and honest truncation.

## 6. Adversarial mutation campaign (§20.35)

`tests/test_compatibility_mutation.py` injects one compatibility violation and
asserts the kernel kills it — 20 mutants, one per §20.35 row (breaking-labeled-
patch, required-field-added, closed-world-enum-added, field-number-reused,
unknown-field-dropped, security-default-weakened, floating-latest, event-identity
-changed, idempotency-scope-changed, duplicate-batch, undeclared-loss, rollback-
after-boundary, workflow-replay-diverges, default-behavior-change, proof-version-
unreadable, removal-with-active-consumer, released-version-mutated, transitive-
inference, cross-tenant-transformer, security-downgrade). 100% killed.

## 7. Red-team (SWARM-M) findings + repairs

SWARM-M attacked the already-green kernel with ~25 adversarial inputs and found
**10 confirmed escapes** — the same two systemic root causes as prior kernels:
truthy-string coercion of boolean flags, and blacklist / "missing = permissive"
logic. All fixed and pinned in `tests/test_compatibility_redteam.py`.

| ID | Escape (unsafe evolution admitted) | Fix | Lock |
|---|---|---|---|
| **E1** | a hard dimension marked `NOT_APPLICABLE` slipped the hard gate → VERIFIED | hard gate requires **positive** COMPATIBLE proof on every hard dim | `test_e1_*` |
| **E2** | retirement gate bypassed by consumer `migrated:"false"` | `migrated is True` only | `test_e2_*` |
| **E3** | CONTRACT-phase gate bypassed by `migrated:"false"` | `migrated is True` only | `test_e3_*` |
| **E4** | `nullable`/`required:"false"` hid a direction-specific break | strict boolean parse | `test_e4_*` |
| **E5** | reserved field-number reuse via `"7"` vs `7` type confusion | normalize identifiers to strings | `test_e5_*` |
| **E6** | `negotiate` accepted `"latest"` when present in `supported` | reject floating tokens first | `test_e6_*` |
| **E7** | envelope authority via a synonym key (`mandate`/`ratifies`) | structural **allowlist** (hash-only fields) | `test_e7_*` |
| **E8** | `PRODUCTION`/`LIVE`/`RAW` corpus got P1, not the P0 poisoned-corpus | fail-closed: any non-SYNTHETIC/ANONYMIZED is P0 | `test_e8_*` |
| **E9** | open/unknown-world enum addition emitted **no** finding | emit `SEMANTIC_COMPATIBILITY_REQUIRED` for review-bucket enums | `test_e9_*` |
| **E10** | REVERSIBLE edge with an **unverified** inverse validated clean | edge gate requires `inverse_verified is True` | `test_e10_*` |

E1 previously produced a fully `valid` report on a program that waived its
security hard dimension; it now reports REVIEW_REQUIRED. E2/E3 previously let a
`migrated:"false"` consumer pass the cutover/retire gates.

## 8. Independent verification (SWARM-O)

SWARM-O independently re-derived 9 claims (not trusting the committed tests) and
**verified all of them**: roadmap identity (SP0007 = Compatibility, Evaluation at
SP0011, no renumbering), product isolation, stdlib-only, no DB migration (v27) and
**zero modified tracked files** (`git diff --stat HEAD` empty — SP0007 touched
nothing already tracked), deterministic bootstrap (32 byte-identical artifacts;
committed == fresh), real program validates P0=0/P1=0 with all 5 models HOLDS,
tests green and **non-vacuous** (constructed clean/violating gate inputs), and
determinism. Coverage: every major capability area maps to a real (non-stub)
module **and** a test — no gap found.

## 9. Acceptance-criteria matrix (200)

Every criterion `AC-0007-001..200` maps to a kernel module and at least one test.
Test files: `B`=baseline, `C`=contracts, `R`=replay, `G`=migration, `M`=mutation,
`X`=redteam.

| AC range | Capability | Module(s) | Tests |
|---|---|---|---|
| 001–020 | roadmap identity + baseline (stdlib-only, isolated, no migration, deterministic) | `canon`,`loader`,`bootstrap` | B |
| 021–040 | contract surface taxonomy, descriptor/version registries, immutability, Twin | `model`,`contracts` | B, C, M |
| 041–070 | producer–consumer graph, compatibility vector + hard gate, directional claims, freshness | `consumers`,`vector` | C, X |
| 071–090 | contract difference engine + breaking classifier, evolution policies | `diff`,`policies`,`counterexample` | C, M, X |
| 091–110 | historical corpus, workflow replay, proof interpretability, differential | `corpus`,`replay` | R, M, X |
| 111–125 | version pinning/negotiation, downgrade protection, firewall, adapters, bridges | `negotiation` | R, M, X |
| 126–145 | migration graph, edges, path selection, loss vector, round-trip, tenant safety | `migration`,`transformer` | G, M, X |
| 146–170 | expand-migrate-contract, dual-read/write, shadow, backfill, lease, barrier, rollback boundary | `plan`,`backfill`,`rollback` | G, M, X |
| 171–190 | deprecation, sunset gate, support windows, fitness functions, debt, change intent, impact cone | `deprecation`,`fitness`,`intent` | G, M |
| 191–196 | proof envelopes (deterministic, evidence-not-authority) + bounded model checking | `envelope`,`modelcheck` | M, X |
| 197–200 | mutation campaign, full regression green, no test weakening, P0=0∧P1=0, complete at 200/200 | (all) | M + full suite |

**200 / 200 satisfied.**

## 10. Full regression

The full suite ran as **4 parallel shards** (111/112/112/111 test files) over the
whole `tests/` tree — the entire product suite plus the 6 new
`test_compatibility_*.py` files — **6559 collected test items**.

| Shard | Files | Result |
|---|---|---|
| 0 | 111 | exit 0 · 0 failures |
| 1 | 112 | exit 0 · 0 failures |
| 2 | 112 | 1 pre-existing browser-e2e flake (see below) · rest clean |
| 3 | 111 | exit 0 · 0 failures |

**Every logic/product test passes.** The single failure was
`tests/test_browser_e2e.py::test_evidence_prompt_injection_flow_in_browser` (a
live Chromium+server pricing-render assertion, `'450 EUR'`), which:
- **passes when run in isolation** (confirmed);
- is a `pytest.importorskip("playwright")` live-browser test that is timing/
  server-state dependent and flaky under parallel load;
- has **zero references to `tools.compatibility`** and cannot be affected by
  SP0007, which changed **zero tracked files** (`git diff --stat HEAD` empty);
- re-running shard 2 **excluding that one browser file → exit 0, fully clean**.

The flake is a pre-existing environmental browser-e2e condition, independent of
SP0007. No product regression; no test weakened. The new SP0007 suite is **177
tests green** (baseline 21, contracts 39, replay 34, migration 40, mutation 29,
redteam 14).

## 11. Final verdict

The Compatibility Constitution is complete, deterministic, stdlib-only, and
product-isolated (no migration, no live cutover, no product behavior change; SP0007
modified zero existing tracked files). The real Compatibility Twin validates
**P0=0 / P1=0 / P2=0**; the 20-mutant campaign kills 100%; the SWARM-M red-team's
10 false-negative escapes are all fixed and regression-locked; SWARM-O
independently verified all claims with no gaps; all 5 bounded models HOLD.
200/200 acceptance criteria are satisfied with module + test evidence. SP0007 is
ready for commit on `claude/finalis-ai-casewoker-blueprint-f1huse`.
