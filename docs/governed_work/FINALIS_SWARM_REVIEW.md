# FINALIS SP0006 — Swarm Review & Acceptance Evidence

**Governed Work, Delegated Autonomy & Outcome Accountability Constitution.**
Audit trail: roadmap identity preflight + authorized reassignment, swarm roles,
repository archaeology, standards research, the built kernel, the adversarial
mutation campaign, the SWARM-M red-team findings + repairs, SWARM-N independent
verification, a 200-criterion acceptance matrix, and the full regression result.

Guiding principles held throughout: **intent is not authority · goal is not
action · plan is not authority · context is not consent · memory cannot create
authority · delegation cannot amplify authority · capability rights are
contextual, expiring, revocable leases · approval binds the exact action ·
artifact is not outcome · claimed is not verified · proof is evidence, not
authority.**

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-12 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `610e1e3` (SP0005) |
| REMOTE_SYNC | IN_SYNC · WORKING_TREE CLEAN at start |
| SP0000..SP0005 | COMPLETE (`e1b6b5c`·`19413f2`·`3eacdb0`·`1ffb4e4`·`e82ca87`·`610e1e3`) |
| LATEST_MIGRATION | v27 (unchanged — SP0006 adds none) |
| PRODUCT BEHAVIOR CHANGE | none · tracked `finalis/` files changed: **0** |
| EXTERNAL EFFECTS OPENED | none (INV-0006-47) |

## 2. Roadmap identity preflight + authorized reassignment

The mandatory preflight found a **material scope mismatch**: the SP0003 Program
Twin recorded **SP0006 = "Evaluation and 1000/1000 Score Charter"**, while this
mission is the **Governed Work Constitution**. Per §2.1 the preflight stopped
before touching tracked files and escalated. The user authorized an explicit,
non-silent reassignment: **SP0006 → Governed Work**, and the **Evaluation charter
moved to the next verified-free slot, SP0011** (SP0007–SP0010 unchanged).

The `BLOCKED_BY_ROADMAP_REASSIGNMENT_CONFLICT` gate did **not** trigger: the only
SP0007–SP0010 dependency on SP0006 was SP0009 (release-train DoD) → SP0006, which
was **safely redirected to SP0011** with zero dangling references. Applied
traceably to `tools/program_graph/bootstrap.py` (Twin source of truth,
regenerated), `docs/program/*` (registry + hypergraph + drift), and 4
`docs/architecture/*` files. Result: **111 program_graph + 103 architecture tests
green**, `program_graph validate` P0=0/P1=0, zero Evaluation-at-SP0006 references
remaining. Full detail in `SP0006_ROADMAP_IDENTITY_REPORT.md`.

## 3. Swarm roles + loop

Roadmap identity → **repository governed-work archaeology (SWARM-A agent)** →
existing-module map → work-order model → admission → delegation/leases →
budgets/risk → approvals → goal/path integrity → recurrence/cancellation/outcome →
formal model checking → **4 parallel build agents (SWARM-B..I)** → integration →
**4 parallel test agents** → **adversarial mutation campaign** → **red-team
(SWARM-M agent)** → repair → **independent verification (SWARM-N agent)** → gap
closure → full regression. The loop did not stop at first green: SWARM-M found 11
false-negative escapes in an already-green kernel; all 11 were fixed and
regression-locked before commit.

## 4. Repository archaeology (SWARM-A) — reference, never rebuild

SP0006 maps to (and never rebuilds) the real repository fabric: EMP-A1 R-FSAFEQ
Governed Work Admission (`employee_work_inbox.py`), the TOOL-B9.2 Governed Work
Lineage Observatory (`tool_work_observability.py`), the authority reference
monitor + RBAC + tenant isolation + approval decisions (`authority.py`,
`approvals.py`, `approval_decisions.py`), the TOOL-B9 write-path family
(write-intent / commit-simulation / local-transaction / recovery), the run ledger,
evidence chain-of-custody, and CRM consent. It **interoperates with** SP0005
safety admission and SP0003 plan/VoI artifacts without replacing them.

## 5. What was built

- **Kernel (29 stdlib-only modules, `tools/governed_work/`)**: `canon`
  (dual semantic/instance hashing + fingerprints), `model`, `intent`, `workorder`
  (deterministic compiler), `ambiguity` (ambiguity/conflict + minimum
  clarification), `statemachine` (fail-closed FSM), `admission` (conjunctive
  gate), `identity`, `lease` (attenuation partial order + revocation),
  `delegation` (DAG + depth/fanout + non-amplification), `budget` (reservation
  ledger + conservation), `risk` (non-compensatory control floor + optional
  loss/CVaR), `approval` (topology + context-bound token + no-self-approval +
  quorum), `drift` (hard + soft goal drift), `purpose` (purpose/scope binding +
  hidden-work + least-authority), `recurrence`, `cancellation` (barrier +
  quarantine + unknown-outcome), `outcome` (contract + verification + defeaters +
  partial + supersession), `accountability` (conservation), `envelope` (4 proof
  envelopes), `modelcheck` (bounded explorer), `plan` (SP0003 binding),
  `projections` (GNAP/OAuth/zcap/UCAN anti-corruption), `validate`, `loader`,
  `bootstrap`, `cli`, `__main__`, `__init__`.
- **Artifacts (`docs/governed_work/`)**: 26 deterministic JSON (14 data + 12
  schema) + 5 Markdown (constitution, formal invariants, research register,
  roadmap identity report, this review), all bit-reproducible from bootstrap.
- **Real program** validates **P0=0 / P1=0 / P2=0** (1 work order → 3 execution
  identities → 3 attenuated leases → 2 delegation edges → budget ledger →
  approval token → outcome contract → recurring contract → accountability chain).
- **CLI**: `roadmap-identity`, `inventory`, `validate`, `modelcheck`, `attest`,
  `compile`, `admit`, `impact` — all emit JSON evidence; `validate`/`modelcheck`/
  `attest` exit non-zero on failure.
- **Bounded model checking**: 5 models all `HOLDS` — work-state safety, authority
  monotonicity, budget conservation, no-self-approval, cancellation — with
  counterexamples on violating variants and honest truncation.

## 6. Adversarial mutation campaign (§20.16)

`tests/test_governed_work_mutation.py` injects one invariant violation into an
otherwise-clean structure and asserts the kernel kills it — 16 mutants, one per
§20.16 row (message-grants-authority, memory/context authority, broader/longer
child lease, delegation cycle, budget overcommit, approval replay after target
change, self-approval, hard-drift-hidden-by-low-score, recurrence old-approval
reuse, cancellation new action, unknown-outcome blind retry, artifact-as-outcome,
accountability lost, proof-envelope binds leases). 100% killed.

## 7. Red-team (SWARM-M) findings + repairs

SWARM-M attacked the already-green kernel for false negatives with 22 adversarial
inputs and found **11 confirmed escapes** — two systemic root causes: truthy-
string coercion of boolean flags, and blacklist/"missing = permissive" logic. All
fixed and pinned in `tests/test_governed_work_redteam.py`.

| ID | Escape (unsafe admitted) | Fix | Lock |
|---|---|---|---|
| **E1** | `coordination_only:"false"` laundered an authority cycle past `validate_all` | authority edge unless `coordination_only is True` | `test_e1_*` |
| **E2** | under-classed approval token accepted (trusted its own required_class) | re-derive the class floor from the live action context and reject a downgrade (P0) | `test_e2_*` |
| **E3** | critical outcome verified by self-report + a junk oracle (blacklist subset) | require a **recognized primary** oracle (allowlist) | `test_e3_*` |
| **E4** | child lease omitting a bounded ceiling/use-count treated as unlimited | omitted bound ⇒ unbounded ⇒ not attenuated (fail-closed) | `test_e4_*` |
| **E5** | outcome redefinition bypass via `approved_replan:"false"` | `approved_replan is True` only | `test_e5_*` |
| **E6** | hidden work: param-smuggled step matched by action+target only | fingerprint the full material step | `test_e6_*` |
| **E7** | purpose memory-guard bypass (`"memory "`) + access self-authorization | strip/case-fold source; compatibility from work order, not access | `test_e7_*` |
| **E8** | `THRESHOLD:0`/negative ⇒ vacuous VERIFIED | require `1 ≤ n ≤ predicate count`; non-empty ALL | `test_e8_*` |
| **E9** | recurrence old-token replay via an alternate binding key | token must positively bind this instance hash (fail-closed) | `test_e9_*` |
| **E10** | no-self-approval defeated by identity case/whitespace | canonicalize identities before comparison | `test_e10_*` |
| **E11** | proof envelope authority via a synonym key | allowlist-style hint scan rejects any authority-implying key | `test_e11_*` |

E1 and E4 previously defeated the aggregate `validate_all` gate; both now cause it
to report `valid=False` on the corresponding unsafe program. (The `integrity_hash`
on approval/envelope is a deterministic digest, not a secret-keyed signature —
documented as a reference-implementation limitation; tamper-resistance for E2/E11
comes from context re-derivation and the key allowlist, not the digest.)

## 8. Independent verification (SWARM-N)

SWARM-N independently re-derived 10 claims (not trusting the committed tests):
roadmap reassignment integrity, predecessor tests green (214), product isolation,
stdlib-only, no DB migration (v27), zero product-code changes (`git diff --stat
HEAD -- finalis/` empty), deterministic bootstrap (byte-identical triple-bootstrap;
26 committed artifacts equal fresh), real program validates P0=0/P1=0 with all 5
models HOLDS, and non-vacuous tests (constructed clean/violating gate inputs).
**All verified.** The one gap raised — `projections.py` untested/unwired — was
closed: added `tests/test_governed_work_projections.py` (7 tests) and wired
projection validation into `validate_all` (a committed projection that claims
authority is now rejected).

## 9. Acceptance-criteria matrix (200)

Every criterion `AC-0006-001..200` maps to a kernel module and at least one test.
Test files: `B`=baseline, `W`=workorder, `D`=delegation, `U`=budget_approval,
`O`=outcome_formal, `P`=projections, `M`=mutation, `X`=redteam.

| AC range | Capability | Module(s) | Tests |
|---|---|---|---|
| 001–020 | roadmap identity + baseline (stdlib-only, isolated, no migration, deterministic) | `canon`,`loader`,`bootstrap` + Twin/manifest reassignment | B |
| 021–050 | candidate intent, work-order compiler, dual hashing, admission, ambiguity/conflict, clarification | `intent`,`workorder`,`ambiguity`,`admission` | W |
| 051–080 | execution identity, delegation DAG/depth/fanout, capability lease, attenuation, revocation | `identity`,`delegation`,`lease` | D, M, X |
| 081–100 | accountability conservation, budget vector, reservation ledger, conservation laws | `accountability`,`budget` | U, M |
| 101–107 | risk vector, non-compensatory control floor, calibrated loss/CVaR | `risk` | U |
| 108–125 | approval topology, class lattice, context-bound token, no-self-approval, quorum | `approval` | U, M, X |
| 126–130 | SP0003 plan binding (plan is not authority) | `plan` | U |
| 131–140 | hard + soft goal drift | `drift` | U, M, X |
| 141–145 | purpose/scope binding, hidden-work, least-authority, safe alternative | `purpose`,`ambiguity` | U, M, X |
| 146–159 | recurrence contract/instance/reauthorization, cancellation barrier, quarantine | `recurrence`,`cancellation` | O, M, X |
| 160–175 | outcome contract/predicates/verification/partial/defeaters/supersession, unknown outcome | `outcome`,`cancellation` | O, M, X |
| 176–190 | governed-work state machine + bounded model checking | `statemachine`,`modelcheck` | O |
| 191–195 | proof envelopes (deterministic, evidence-not-authority) | `envelope` | O, M, X |
| 196 | adversarial mutation campaign | (all) | M |
| 197–200 | full regression green, no test weakening, P0=0∧P1=0, complete at 200/200 | — | full suite |
| external | provider-neutral authorization projections (GNAP/OAuth/zcap/UCAN) | `projections` | P |

**200 / 200 satisfied.**

## 10. Full regression

The full suite ran as **4 parallel shards** (110 test files each) over the whole
`tests/` tree — the entire product suite plus the reassignment-affected
predecessor suites (program_graph, architecture) plus the 8 new
`test_governed_work_*.py` files.

| Shard | Files | Exit code | Failures |
|---|---|---|---|
| 0 | 110 | 0 | 0 |
| 1 | 110 | 0 | 0 |
| 2 | 110 | 0 | 0 |
| 3 | 110 | 0 | 0 |

**6382 test items collected · all four shards exit 0 · 0 failed / 0 errored.**
This includes the SP0005 product baseline (unchanged — zero tracked product files
touched), the reassignment-updated program_graph (111) + architecture (103)
suites, and the new SP0006 governed-work suite (161 tests). No product
regression; no test weakening.

## 11. Final verdict

The Governed Work Constitution is complete, deterministic, stdlib-only, and
product-isolated (no migration, no effects, zero tracked product-file changes; the
only modified tracked files are the authorized roadmap-reassignment artifacts).
The real program validates **P0=0 / P1=0 / P2=0**; the 16-mutant campaign kills
100%; the SWARM-M red-team's 11 false-negative escapes are all fixed and
regression-locked; SWARM-N independently verified all claims and its gap is closed;
all 5 bounded models HOLD. 200/200 acceptance criteria are satisfied with module +
test evidence. SP0006 is ready for commit on
`claude/finalis-ai-casewoker-blueprint-f1huse`.
