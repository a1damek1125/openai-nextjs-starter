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

---

# SP0010 V5 — Proof-Carrying Assurance Closure (supersedes V2/V3/V4)

## 8. What V5 adds (on top of the V3 core, same change boundary)

V5 extends the sealed closure with **proof-carrying, dual-graph and
causal/CEGAR** subsystems. The V3 kernel is unchanged and its 7 red-team fixes
(R1–R7) remain regression-locked; V5 adds 9 modules and 12 docs artifacts, all
deterministic, standard-library-only, never imported by product code, with the
product runtime + migration frontier (v27) byte-untouched.

| V5 subsystem | Module | Fail-closed discipline |
|---|---|---|
| Dual-Graph conformance | `dual_graph.py` | declared ADG vs an independently-scanned Repository Evidence Graph; 5 classes; **CONFLICT = P0**, critical DECLARED_ONLY = P0, AMBIGUOUS never rounded to MATCH |
| Extraction Uncertainty Firewall | `extraction.py` | every declared node needs a resolvable on-disk source span; an ungrounded critical node is quarantined and **blocks** — it can never become hard truth |
| Trusted Computing Base | `tcb.py` | 11 content-hashed trusted members + a 4-module minimal kernel; a missing member is P0 |
| Proof-Carrying Certificates | `certificates.py` | an **independent checker** re-derives every obligation; a SUPPORTED_ONLY solver verdict **without a VALID certificate is advisory-only** (PROOF_HOLE, P0) |
| Causal control verification | `causal.py` | structural causal model + backdoor criterion; a control whose effect is **NOT_IDENTIFIED** (unobserved confounder) is P0 |
| CEGAR | `cegar.py` | sound abstraction, concretize, spurious→refine; **LIMIT_REACHED is not a pass**; a REAL_COUNTEREXAMPLE is P0 |
| Robustness Frontier | `robustness.py` | exact **cut number** (min producer domains to break a guarantee) in domain space; cut 0 = P0, cut 1 = disclosed P2 |
| Federated N-Version | `federated.py` | 4 heterogeneous backends; each must be deterministic + **sensitive** to a canary root change + agree on the anchor; insensitive/diverged/common-mode = P0 |
| Minimal Correction Sets | `correction.py` | lexicographic (hard-first) repair portfolio; a repair that would **weaken an invariant is rejected** (P0); a clean closure certifies an empty portfolio |

The 7 new roots (dual_graph, extraction_firewall, tcb, certificate, causal,
cegar, robustness) are folded into the Architecture Genome's class roots, so any
of them moving moves the global architecture root; the seal remains fail-closed
on the full P0/P1 finding set.

## 9. V5 sealed twin (materialized)

| Property | Value |
|---|---|
| Dual-graph nodes | 57, all MATCH; 0 CONFLICT / DECLARED_ONLY / AMBIGUOUS / IMPLEMENTATION_ONLY |
| Extraction firewall | every critical declared node GROUNDED (0 quarantined) |
| Proof-carrying certificates | 16/16 guarantees certified VALID by the independent checker; 0 proof holes |
| Causal identifiability | 6/6 controls IDENTIFIED |
| CEGAR | 4/4 properties PROVED (each after refining away a spurious counterexample) |
| Federated verification | CONVERGED across 4 heterogeneous backends (4 distinct fingerprints) |
| Robustness frontier | min critical cut = 1 (single-producer common-mode, disclosed as P2 assurance debt) |
| Repair portfolio | EMPTY, certified (no repair owed) |
| TCB | complete (11 members, 4-module minimal kernel) |
| Findings | **P0 = 0, P1 = 0, P2 = 48** |
| Closure state | `CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS` |
| Determinism | closure rebuilds byte-identical |

## 10. V5 swarm process

- **SWARM-A** re-mapped the repository into a Repository Evidence Graph adapter
  (governance packages, product access-control symbols, twin roots, migration
  frontier) — the independent side of the dual-graph.
- **SWARM-P (red-team)** attacked the new fail-closed disciplines for
  false-negative escapes (coercion, missing==permissive, self-certification,
  gate bypass, root omission, firewall bypass, correction weakening).
- **SWARM-Q (independent verifier)** re-derived determinism, code↔docs
  consistency, dual-graph groundings, the certificate gate, federation
  heterogeneity, and the change boundary.

Red-team + independent-verifier outcomes are recorded in §11.

## 11. V5 red-team escapes and fixes

**SWARM-Q (independent verifier)** returned a clean bill on all 8 audit items:
determinism (closure rebuilds byte-identical), code↔docs consistency (every
materialized root equals a fresh build), no over-claim (state is
`…CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS`, seal grants no authority, SP0011
score null), the Repository Evidence Graph is a genuine independent disk scan
(adg_root ≠ reg_root; 57/57 nodes MATCH re-confirmed by independent grep of
`tenant_id`/`require_permission`/`non_authoritative` and frontier v27), the
change boundary holds (`finalis/` byte-untouched, `boundary.check_boundary` empty).

**SWARM-P (red-team)** confirmed the primary seal gate is genuinely fail-closed
(`hard_finding_count = P0+P1` over the FULL finding set blocks any hard finding —
no input made a hard failure seal) but found **five real weaknesses**: four V5
gates whose blocking signal was structurally unreachable (ceremonial), plus one
dead-code path. All five are fixed and regression-locked.

| # | Sev | Escape | Fix | Lock |
|---|---|---|---|---|
| P1-A | P1 | **The proof-carrying certificate checker was common-mode with the solver.** `check_certificate` trusted the solver-supplied `claimed_state` and never re-derived the claim's epistemic state from ground truth, nor checked that support atoms actually referenced the claim — so a lying/mis-classified solver verdict (SUPPORTED_ONLY over an empty supported set, or atoms of an unrelated claim) certified VALID. | The checker now re-derives closure INDEPENDENTLY from the `supported_set`/`refuted_set` it is given (`claim_id ∈ supported ∧ ∉ refuted`), requires every support atom's `claim_refs` to include the claim, and drives `admitted_closed` off the independent verdict — never the solver's self-report. | `test_certificate_checker_rejects_lying_solver_state`, `…_rejects_atoms_of_unrelated_claim`, `…_rejects_refuted_claim` |
| P1-B | P1 | **The federated convergence gate's sensitivity canary tested only the lexically-first class root**, so a backend blind to any other root passed `sensitive=True`; federation converged on garbage. | The canary now perturbs EVERY root in turn; a backend is `sensitive` only if its fingerprint moves for every root, and `blind_to_roots` is reported. | `test_federation_backend_blind_to_one_root_diverges`, `…_every_backend_sensitive_to_every_root` |
| P1-C | P1 | **The 7 V5 class roots were absent from `REQUIRED_CLASS_ROOTS`**, so Phase C's root-omission guard did not cover them — a V5 subsystem root could be unwired from the sealed genome undetected. | All 7 V5 root keys added to `REQUIRED_CLASS_ROOTS`; Phase C now flags a dropped V5 root as `missing_class_roots`. | `test_v5_roots_required_by_ceremony`, `test_dropping_v5_root_is_detected_by_phase_c` |
| P1-D | P1 | **CEGAR ran only hard-coded honest models**, so `REAL_COUNTEREXAMPLE`/`LIMIT_REACHED` were unreachable on the real tree — a genuine information-flow leak produced no finding. | Each CEGAR property's model is now GROUNDED on a real repository control (file+symbol); an absent control yields a leaky model and a concretized `REAL_COUNTEREXAMPLE` (P0). | `test_cegar_grounded_ungrounded_control_yields_real_counterexample` |
| P2-A | P2 | **`extraction.extraction_findings` was never called** — an ungrounded critical node's dedicated P0 was silently downgraded to the dual-graph MATCH→AMBIGUOUS P1 (still caught, but the firewall's own signal was inert). | `build_closure` now folds `extraction_findings` over the firewall, restoring the independent `EXTRACTION_NODE_UNGROUNDED` P0. | `test_extraction_ungrounded_critical_is_p0` (+ wiring) |

**Classes with no escape found** (SWARM-P, stated explicitly): truthy/coercion
(strict `is True` throughout), seal-gate bypass (the full-finding `hard_finding_
count` holds), correction weakening (a weakening repair is always routed to
`unrepairable_without_weakening` → P0), and causal identifiability (an ungrounded
control leaves the confounder unobserved → NOT_IDENTIFIED → P0). The permissive
`hard_truth` default SWARM-P first suspected was already fail-closed (`False`) on
disk — it retracted that suspicion after re-reading.

After the fixes the closure re-seals `P0 = 0, P1 = 0` (the real tree passes every
now-effective gate) and remains deterministic; the four previously-ceremonial
gates now do real work.
