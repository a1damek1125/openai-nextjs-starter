# SP0010 — Architecture Assurance Closure: Swarm Review

Honest build-and-review record for SP0010. Documents how the architecture-
assurance-closure kernel was built, the scope decision, what independent swarm
agents found, every confirmed false-negative escape and its fix, and the
limitations recorded rather than hidden.

## 1. What was built

A deterministic, repository-local **Architecture Assurance Closure control
system** under `tools/architecture_closure/` (28 modules, 24-command CLI) plus
materialized artifacts under `docs/architecture_closure/`. It determines whether
SP0000–SP0009 compose into one coherent, non-circular, evidence-grounded,
replaceable and auditable architecture, then seals ONE verified snapshot and
hands SP0011 an admission package — assigning NO score.

Materialized closure twin (`docs/architecture_closure/FINALIS_ARCHITECTURE_
CLOSURE_TWIN.json`):

| Property | Value |
|---|---|
| Constitutional interfaces | 10 (SP0000–SP0009) |
| Assurance hyperedges | 16 (conjunctive) |
| Critical claims | 39, all `SUPPORTED_ONLY` |
| Critical BOTH / NEITHER | 0 / 0 |
| Unsupported assurance cycles | 0 |
| Global invariants HOLD | 13 / 13 |
| Paired-world hyperproperties PASS | 4 / 4 (bounded models) |
| Counterfactual controls | 6 NECESSARY_NOT_SUFFICIENT (grounded on disk) |
| Constitutional blockers | 0 |
| Production gaps | 6 (non-blocking, owned, with next actions) |
| 3-phase verifier ceremony | sealed_ok across 3 distinct constructions |
| Findings | **P0 = 0, P1 = 0, P2 = 32** |
| Closure state | `CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS` |
| Genome global root | `ee167b18786153be…` |
| Program Seal hash | `7185652a9497741b…` |
| SP0011 admission | `ADMITTED_PENDING_EXECUTION` (no score) |
| Determinism | closure rebuilds byte-identical |

## 2. Scope decision (transparent, non-silent)

The program-registry node labels SP0010 **"Global Brand Naming Sprint"** — a
stale placeholder with no outputs or completion evidence, inconsistent with the
constitutional program. Three converging authorities establish **"Architecture
Program Final Gate"** as the canonical SP0010 scope: (a) the SP-AUTHOR-0000
mission's explicit canonical title and full 260-AC architecture-closure spec;
(b) the SP0000–SP0009 arc is entirely constitutional architecture, making the
final gate its coherent closure; (c) the SP0011 successor is "Evaluation and
1000/1000 Score Charter", exactly the mission's declared successor. Following the
SP0006 precedent (user-authorized non-silent reassignment), SP0010 proceeded
under the canonical scope; the naming activity is recorded as an
`ACCEPTED_FUTURE_ENHANCEMENT` and the program registry was **not** edited.

## 3. Swarm process

- **SWARM-A/C (constitutional archaeology)** mapped all 10 predecessor
  constitutions, their assumptions/guarantees/invariants, the committed twin
  roots (Contract Genome `7269f08c`, Release twin `916dd687`, Semantic registry
  `d91f97a6`), the real product controls (require_permission 375×, tenant_id
  2837×, current_user 400×), the frozen SP0009 verifier files, and the honest
  production gaps.
- **SWARM-DOCS** wrote the constitution, roadmap-identity report, architecture
  description package and research register, verified against the twin.
- **SWARM-P (red-team)** found **7 real false-negative escapes** (1 critical
  P0, 3 P1, 3 P2). All fixed and regression-locked (§4).
- **SWARM-Q (independent verifier)** re-checked every material claim (§5).

## 4. Confirmed false-negative escapes and fixes

Each is pinned by a lock in `tests/test_architecture_closure_mutation.py`.

| # | Sev | Escape | Fix | Lock |
|---|---|---|---|---|
| P0-1 | P0 | **The seal and `validate` were decoupled from the finding set.** `closure_state` checked only 4 counters; blocking gaps of type `GLOBAL_INVARIANT_GAP`/`CROSS_TWIN_CONTRADICTION` were computed but unused; many P0 kinds (FROZEN_VERIFIER_MODIFIED, verifier disagreement, provider-account leak, SP0011 fabrication) mapped to no gap; `validate` never read the twin's findings. A seal could be CLOSED over live P0s. | `closure_state` is now fail-closed on the FULL P0/P1 count; the seal counts ALL blocking-gap types; `validate_closure` folds the twin's own hard findings. | R1, R1b |
| P1-2 | P1 | **Phase C was common-mode with Phase B** — both called `global_root(class_roots)`, so the "independent" root was byte-equal by construction and the diversity was nominal (label strings). | Phase C now aggregates via a Merkle TREE (distinct algorithm), publishes its own witness, verifies class-root completeness (catches root omission), and diversity requires ≥2 distinct constructions. | R2, R2b |
| P1-3 | P1 | **Frozen-verifier / baseline checks were self-referential** — both sides recomputed live, so a modified verifier moved both equally and never tripped. | The frozen SP0009 verifier identity is now a hardcoded committed constant; the ceremony compares the live recompute against it. | R3 |
| P1-4 | P1 | **An in-cycle member could self-anchor an unsupported cycle** (the anchor test allowed any member `in anchored`, not only an EXTERNAL anchor). | Require the anchor to enter from OUTSIDE the SCC. | R4 |
| P2-5 | P2 | **Independence counted trust-domain label strings, not producers** — two atoms from the same generator were reported INDEPENDENT. | Quotient by producer; same producer = common-mode, disclosed as a P2 assurance-debt diagnostic (not falsely claimed as quorum, not a hard blocker). | R5 |
| P2-6 | P2 | **Counterfactual necessity was trivially true** (present/removed hardcoded) and `exercised` hardcoded. | Ground present/removed on the control's file+symbol actually existing on disk; an ungrounded control is INEFFECTIVE. | R6 |
| P2-7 | P2 | **Invariant control refs checked file existence only**, ignoring the named symbol. | Verify the named symbol appears in the file (deleting `require_permission` while keeping `app.py` no longer passes). | R7 |

**Classes with no escape found** (independently confirmed): dangling assumption
(blocks), conjunctive hyperedge activation, refutation propagation, BOTH/NEITHER
strictness (strict `is True`, truthy strings rejected), noninterference is
genuinely relational two-world, SP0011 fabrication detection, and determinism
(no set/dict-order leak into any root or the closure digest).

## 5. Honest limitations (recorded, not hidden)

- **Architecture closure ≠ production readiness.** The product remains
  `NOT_PRODUCTION_READY`; production qualification is `BLOCKED_PENDING_SP0011`.
  The Program Seal grants **no** production authority.
- **Noninterference is bounded-model evidence, not universal proof.** The
  paired-world hyperproperties run over bounded deterministic reference models
  grounded in the real controls; the bound is disclosed (D-0010-41).
- **Guarantee support is largely single-producer (common-mode).** Each
  constitution's guarantee is grounded primarily in its own kernel; this is
  disclosed honestly as a P2 assurance-debt / single-point-of-assurance
  diagnostic rather than falsely claimed as independent quorum.
- **6 standing production gaps** remain visible: SQLite/local-FS persistence,
  no CI/lockfile/build-backend, all external effects are mocks, the browser E2E
  file is environment-sensitive, SP0011 evaluation is pending, and auth is
  dev-grade with unanchored evidence.
- **No 1000/1000 score.** SP0010 produces admission evidence only; SP0011 must
  still prove reliability.

## 6. Change boundary — verified clean

Zero product runtime change, zero product migration (frontier stays v27,
AST-checked), zero external effect (fail-closed import allowlist), never imported
by product code (`finalis/` byte-untouched). `boundary.check_boundary` returns
empty on the shipped tree.

## 7. Test status

`tests/test_architecture_closure_core.py` (32), `..._mutation.py` (32
constitutional mutants + 9 red-team regression locks), and `..._properties.py`
(10 property/metamorphic/scale) all pass. The closure is deterministic and
re-validates against a fresh build.
