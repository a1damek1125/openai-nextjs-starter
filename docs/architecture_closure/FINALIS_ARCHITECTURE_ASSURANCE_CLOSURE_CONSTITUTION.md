# FINALIS Architecture Assurance Closure Constitution (SP0010)

**Mission:** SP0010 — FINALIS Architecture Program Final Gate / Architecture
Assurance Closure, Constitutional Coherence & Program Seal.

**What this is.** A deterministic, repository-local system that decides one
question: *do the ten predecessor constitutions SP0000–SP0009 compose into a
single coherent, non-circular, evidence-grounded, replaceable, auditable
architecture?* If they do, SP0010 seals **one** verified snapshot and hands
SP0011 an admission package. Everything the kernel concludes is recomputable
byte-for-byte from the repository at commit `1e29581`; the materialized result
is `docs/architecture_closure/FINALIS_ARCHITECTURE_CLOSURE_TWIN.json`.

**What this is NOT.** SP0010 does **not** close product, operational, or field
readiness, and it assigns **no** 1000/1000 score. The sealed snapshot
`grants_production_authority: false` — always, by construction. The product
remains `NOT_PRODUCTION_READY`; production qualification is
`BLOCKED_PENDING_SP0011`.

This constitution states the reasoning rules the kernel is built on and the
distinctions it refuses to collapse. Section by section it maps to the kernel
modules under `tools/architecture_closure/` and to the real closure result.

---

## 1. The core distinctions (the things SP0010 refuses to conflate)

The kernel exists because each of the following left-hand facts is routinely
mistaken for the right-hand one. SP0010 keeps them apart on purpose.

1. **ALL PREDECESSOR SPs COMPLETE ≠ THE PROGRAM COMPOSES CORRECTLY.** Ten
   finished constitutions can still assume things of each other that no one
   guarantees. Composition is verified explicitly (interfaces → hypergraph),
   never inferred from completion.
2. **ALL LOCAL TESTS PASS ≠ GLOBAL INVARIANTS HOLD.** Per-SP green suites do
   not establish cross-cutting properties (tenant isolation, authority
   conservation, safety dominance). Those are evaluated as twelve *global*
   invariants that no single constitution owns alone.
3. **NO SUPPORTING EVIDENCE ≠ EVIDENCE AGAINST.** Absence of support is
   `NEITHER`, not refutation; it never reads as satisfaction.
4. **EVIDENCE FOR AND AGAINST ≠ UNKNOWN.** A claim with both support and
   refutation is `BOTH` — a contradiction — not an unresolved unknown. Support
   and refutation are tracked independently and never averaged.
5. **A SUPPORT CYCLE ≠ A VALID PROOF.** A constitution may not launder its own
   assumptions through a cycle. An unsupported strongly-connected component
   blocks any critical claim resting on it.
6. **NO DETECTED CROSS-TENANT PATH ≠ NONINTERFERENCE PROVEN.** Path absence in
   one execution is not a hyperproperty. Noninterference is checked over
   *paired worlds*, and even then only within a disclosed bound.
7. **CONTROL EXISTS ≠ CONTROL IS NECESSARY OR EFFECTIVE.** A guard that is
   present but never exercised, or whose removal changes nothing, is not a
   working control. Necessity and sufficiency are proven separately.
8. **ASSURANCE CASE CLOSED ≠ PRODUCT PRODUCTION-READY.** Constitutional
   architecture closure is a statement about coherence of the design and its
   proofs, not about deployability.
9. **PROGRAM SEAL ≠ PERMANENT VALIDITY.** The seal binds one snapshot. A
   material root change or a grounded defeater invalidates it; historical seals
   are superseded, never overwritten.
10. **FORMAL MODEL HOLDS ≠ REAL-WORLD SYSTEM UNIVERSALLY SAFE.** Bounded
    reference models are evidence within their bounds; they are not universal
    proofs and are never presented as such.

Every downstream rule in this document is an operationalization of one of these
ten distinctions.

---

## 2. Determinism, canonicalization, and the Merkle forest

Module: `canon.py`.

All reasoning is over canonical JSON: sorted keys, compact separators, no NaN,
UTF-8. Hashing is SHA-256 over that canonical form. Volatile presentation keys
(`display_name`, `label`, `notes`, `description`, `statement`, timestamps,
colours, UI hints) are stripped before *core* hashing, so cosmetic edits never
move a structural root while any material change always does.

Roots are organized as a **Merkle forest**: per-class roots are binary Merkle
roots over *sorted* leaves (order-independent within a class); the **global
architecture root** is the SHA-256 of the ordered `class=<root>` list, so a
change to any single class root moves the global root. The kernel opens no
subprocess, performs no external effect, and emits no secret values. Rerunning
the closure rebuilds the twin byte-identically — `model_checks.root_determinism`
is `HOLD` and the closure digest is `5816e8414cc6018d0c6fad0a38c3e413d96cd31e84b601330283cd0d57dc566c`.

---

## 3. The four-valued epistemic lattice, and why only SUPPORTED_ONLY closes

Modules: `model.py`, `epistemic.py`.

Every claim carries **two independent bits**: does it have positive support, and
does it have refuting support? They are never subtracted or averaged. The pair
`(support, refute)` yields exactly four states:

| State | (support, refute) | Meaning |
|---|---|---|
| `SUPPORTED_ONLY` | (1, 0) | supported and not refuted — **the only closing state** |
| `REFUTED_ONLY` | (0, 1) | refuted |
| `BOTH` | (1, 1) | contradiction — never PASS |
| `NEITHER` | (0, 0) | unresolved — never PASS |

A **critical** claim is closure-admissible **only** in `SUPPORTED_ONLY`
(`closes_critical`). `BOTH` is a contradiction, `NEITHER` is unresolved,
`REFUTED_ONLY` is refuted — none may be promoted to PASS. This is the machine
encoding of distinctions 3 and 4: absence of support is not satisfaction, and
evidence-for-and-against is not an unknown to be split.

Refutation has its own least-fixed-point closure (`refutation_closure`) that
propagates through rebuttal/undercut/contradiction edges, so a refutation of a
premise can refute a conclusion. Booleans are strict: a truthy string is not
`True`.

**Materialized result.** All 48 claims are `SUPPORTED_ONLY`; of those, 38 are
critical and all 38 are `SUPPORTED_ONLY`. Critical `BOTH` = 0, critical
`NEITHER` = 0. The 48 decompose as 16 top-level guarantee claims, 12 global
invariants, 10 cross-twin claims (each critical), and 10 non-critical
`CL-SP*-evidence-present` grounding facts.

---

## 4. The conjunctive assurance hypergraph and its least fixed point

Modules: `interfaces.py`, `hypergraph.py`.

**Interfaces.** Each of SP0000–SP0009 is described by what it OWNS, what it
ASSUMES from predecessors, what it GUARANTEES to successors, its hard
INVARIANTS, its FAILURE states, and the real on-disk EVIDENCE that grounds its
guarantees. Evidence references are checked for existence on disk: a guarantee
cannot draw support from an artifact that is not there. A missing assumption
**never defaults to satisfied** — an assumption that references no predecessor
guarantee is a dangling premise and a P0 finding (`D-0010-06`).

**Hypergraph.** A guarantee that needs several assumptions becomes **one
conjunctive hyperedge** `{A1,A2,A3} → G`, not three simple edges. A single
satisfied premise must **never** activate a multi-premise guarantee
(`INV-0010-12`). Positive support is the **least fixed point** over active
hyperedges, starting from anchored claims (guarantees whose evidence is present
and whose premise set is already supported). A hyperedge fires only when *every*
premise is already supported. The iteration count is bounded and reported.

**Materialized result.** 10 constitutional interfaces produce **16 assurance
hyperedges** (SP0006 contributes 3, SP0002/SP0007/SP0008/SP0009 contribute 2
each, the rest 1). The fixed point reached closure in **2 iterations** and 26
claims are in the positive-support set. `model_checks.hyperedge_conjunctive` is
`HOLD`.

---

## 5. Grounded defeaters

Module: `defeaters.py`.

Defeaters can rebut a claim, undercut an argument, attack evidence reliability,
or invalidate an assumption or its freshness. Resolution uses the deterministic
**grounded extension** of the defeater attack graph: an argument is IN only when
every attacker is OUT; an attacker is OUT only when some IN argument attacks it.
No favourable extension is chosen merely because it produces closure
(`D-0010-05`). An ungrounded defeater is a rumor and stays `PROPOSED` — it never
blocks. A grounded, unopposed defeater is `BLOCKING`; a blocking defeater on a
critical claim refutes it and reopens closure.

**Materialized result.** `defeater_resolution` is empty: no defeaters, no
blocking, no blocked targets. This is a clean state, not a suppressed one — the
mechanism is present and would fire.

---

## 6. Unsupported-cycle blocking

Module: `circularity.py`.

Support dependencies form a graph; its strongly-connected components are found
by **Tarjan's algorithm** (iterative, to avoid recursion limits). A non-trivial
SCC is **ANCHORED** only when at least one required support chain enters it from
an independently grounded external source (an anchored claim outside the SCC);
otherwise it is **UNSUPPORTED**. An unsupported cycle blocks any critical claim
resting on it (distinction 5: a cycle is not a proof). This is how the kernel
enforces that no constitution launders its own assumptions.

**Materialized result.** `circularity.sccs = []`, `unsupported = []`.
`model_checks.unsupported_cycle` is `HOLD`. There are no support cycles at all
in this program.

---

## 7. Evidence-provenance algebra and independence

Module: `evidence.py`.

Support is algebraic. Each claim is backed by **minimal antichain sets** of
evidence atoms. AND-composition is the minimized Cartesian union of prerequisite
support sets; OR-composition is the minimized union of alternatives; strict
supersets are removed (`D-0010-09`). Bounds are exact: truncation is an explicit
`SUPPORT_SET_LIMIT_REACHED`, never silent (limit 256).

Independence is **domain-based**, not count-based: many evidence files produced
by one generator, tool, or parser family are **one common-mode domain** and
count once for quorum (`D-0010-10`). A support set is `INDEPENDENT` only when its
atoms span at least two distinct trust domains after common-mode quotienting.
**Self-referential** evidence — an atom whose producer is the claim's own
generator — cannot close a critical claim (`INV-0010-14`). **Stale** evidence
(past its `valid_to`) cannot close a current claim (`INV-0010-16`). A common-mode
graph groups atoms sharing a producer/tool/parser family, so that agreement
among dependent sources is recognized as weaker evidence.

**Materialized result.** Every one of the 16 top-level claims has a minimal
support set of two atoms drawn from two distinct trust domains
(`kernel-SP*` and `proof-SP*`), classified `INDEPENDENT`, `current: true`,
`limit_reached: false`. The common-mode graph honestly records that the kernel
atoms all share the `ast`/`kernel` families and the proof atoms all share the
`canonical-json`/`proof-artifact` families — the independence that closes each
claim comes from spanning kernel *and* proof domains, and this shared-family
structure is disclosed, not hidden.

---

## 8. Cross-twin coherence

Module: `crosstwin.py`.

The closure compares the current truths of nine predecessor twins/registries
(Architecture, Semantic, Program, Technology, Safety, Governed Work,
Compatibility, Contract Inventory, Release Assurance) across eight shared
dimensions: identity, semantic epoch, valid time, contract version, ownership,
authority, tenant scope, effect class. **Similar labels do not force identity**
(`INV-0010-18`); contradictions stay first-class and are never silently resolved
(`D-0010-12`). The module also guards against a **parallel registry or parallel
authority** — a twin minting competing constitutional truth. The closure
references existing roots and never persists a competing registry of its own.

Not every twin exposes a single aggregate top-level root (the Compatibility twin
is a set of per-artifact hashes; the Semantic `registry_hash` is nested
per-epoch). The absence of one aggregate root is a known structural fact and
must not read as `NEITHER`. There is one machine-checkable **cross-link**: the
Release Assurance twin embeds the Contract Genome root, which must equal the
committed Contract Genome `global_root` — a genuine cross-twin agreement.

**Materialized result.** All nine twins present; ten cross-twin identity claims
(`CT-*`) `SUPPORTED_ONLY`, including `CT-release-genome-crosslink`
(the real release↔contract-genome agreement). No contradictions, no parallel
registry.

---

## 9. Global invariants (non-compensatory)

Module: `invariants.py`.

Global invariants are cross-cutting properties no single constitution owns
alone. Each has an OWNER constitution, evidence requirements, a criticality
flag, and optionally an associated hyperproperty. An invariant HOLDS only when
its establishing guarantee claim(s) are all `SUPPORTED_ONLY`, its grounding
control ref(s) exist on disk, and its hyperproperty (if any) PASSes. Global
invariants are **non-compensatory** (`D-0010-13`): no average architecture score
offsets a failed hard invariant. An invariant with `UNKNOWN` status **blocks
closure** (fail-closed).

The twelve invariants and owners: `INV-TENANT-ISOLATION` (SP0006),
`INV-AUTHORITY-CONSERVATION` (SP0006), `INV-DELEGATION-ATTENUATION` (SP0006),
`INV-APPROVAL-CONTEXT-BOUND` (SP0006), `INV-SAFETY-DOMINATOR` (SP0005),
`INV-PROOF-NOT-AUTHORITY` (SP0009), `INV-RELEASE-RUNTIME-SEPARATION` (SP0009),
`INV-ZERO-LOST-WORK` (SP0006), `INV-OUTCOME-EVIDENCE` (SP0006),
`INV-HISTORICAL-INTERPRETABILITY` (SP0002),
`INV-LEARNING-PROMOTION-GATED` (SP0006),
`INV-CONTROL-LANGUAGE-INVARIANCE` (SP0002).

**Materialized result.** All twelve are `HOLD`, all critical. Four are backed by
a passing hyperproperty (tenant, approval, control-language, and — via
authority — provider account); the other eight hold on supported claims plus
present controls.

---

## 10. Paired-world relational noninterference (bounded, not universal)

Module: `noninterference.py`.

Path absence is **not** noninterference (`INV-0010-27`): a hyperproperty compares
*multiple* executions. Each check runs **two bounded worlds** that differ only in
a protected variable and requires the declared observable of the *other* party
to be equivalent across both worlds. A correct reference model ignores the
protected variable; a violation would read it. The four hyperproperties:

- `HP-TENANT-NONINTERFERENCE` — Tenant B observables invariant under Tenant A's
  secret (grounded in real per-tenant `WHERE tenant_id` scoping).
- `HP-APPROVAL-ISOLATION` — Work B admissibility invariant under Work A approval.
- `HP-PROVIDER-ACCOUNT-SEPARATION` — Tenant B provider binding invariant under
  Tenant A account.
- `HP-CONTROL-LANGUAGE-INVARIANCE` — policy outcome invariant under the
  control-language surface (EN/PL/DE/ES).

**These are bounded deterministic reference models grounded in the real
controls, never universal proof** (`D-0010-41`). Each result discloses its
`varying_domain` and carries the explicit note "bounded reference model; not
universal proof." This is the machine form of distinctions 6 and 10.

**Materialized result.** All four `PASS` with no counterexample, over 4 / 2 / 1 /
2 world-pairs respectively. The bounds are stated in the twin and re-stated in
the SP0011 admission package's `noninterference_limits`.

---

## 11. Counterfactual control necessity vs sufficiency

Module: `counterfactual.py`.

**Control exists ≠ control is necessary or effective** (distinction 7). For each
critical declared control the kernel (1) verifies the protected property holds
*with* the control, (2) removes the control in a bounded mutation model, and (3)
shows the expected violation becomes reachable (necessity) — or explains
redundancy. Necessity and sufficiency are kept **separate** (`D-0010-20`): a
control necessary in the model may still be insufficient, so `sufficiency_witness`
is `null` and requires a separate proof. A control class that merely exists but
is never exercised cannot be counted (`D-0010-18`).

**Materialized result.** All six critical controls are
`NECESSARY_NOT_SUFFICIENT`, each with a reachable violation on removal and a
recorded exercise site in real code:

| Control | Protected property | Exercised by |
|---|---|---|
| `CTL-AUTH-GATE` | no unauthenticated protected effect | `Depends(current_user)` (400×) |
| `CTL-RBAC` | no over-authority action | `require_permission` (375×) |
| `CTL-TENANT-SCOPE` | no cross-tenant row access | `tenant_id WHERE` scoping (279×) |
| `CTL-SAFETY-ADMISSION` | no unsafe protected effect admitted | `tools/safety` admission gate |
| `CTL-APPROVAL-BINDING` | no protected effect without bound approval | `tools/governed_work` binding |
| `CTL-RELEASE-PROOF-BOUNDARY` | release proof grants no runtime authority | `tools/release/envelope.py` |

The word *not-sufficient* is load-bearing: SP0010 proves these controls are
necessary in-model, not that they are sufficient for real-world safety.

---

## 12. Assurance resilience (redundancy ≠ correctness)

Module: `resilience.py`.

Diagnostic analysis: for each critical claim, what happens when one — or a
bounded *k* — assurance element is removed (a verifier, an evidence trust
domain, an adapter, a projection, a control)? A claim whose support collapses on
any single removal is a `SINGLE_POINT_OF_ASSURANCE`. **Redundancy is not
correctness** (`D-0010-21`): this measures *fragility*, not truth. Exact
enumeration and bounded sampling are kept distinct — exactness is claimed only
when the full removal set was enumerated.

**Materialized result.** All 16 top-level claims are
`SINGLE_POINT_OF_ASSURANCE` under N-1 removal of an `EVIDENCE_DOMAIN` (each rests
on exactly two domains, kernel and proof, so losing either collapses support).
These are the **16 P2 findings** in the report — explicitly diagnostic, not
blocking, and honestly surfaced rather than hidden. They do not affect closure;
they tell SP0011 where the assurance is thin.

---

## 13. Gap taxonomy: closure blockers vs production gaps

Module: `gaps.py`.

Every gap is typed, owned, and carries a next action. Three types **block**
architecture closure: `CONSTITUTIONAL_BLOCKER`, `CROSS_TWIN_CONTRADICTION`,
`GLOBAL_INVARIANT_GAP`. All other types — implementation, production
infrastructure, field validation, SP0011 evaluation, operational, regulatory,
accepted-future-enhancement — remain visible in the final report but do **not**
block closure. SP0010 may close the constitutional architecture with
non-blocking production gaps, but **never** with a constitutional blocker
(`INV-0010-55`). This is the machine form of distinction 8.

**Materialized result.** **0 constitutional blockers, 0 blocking gaps, 6
standing production gaps**, all `OPEN`, none blocking closure:

| Gap type | Statement | Owner | Next action |
|---|---|---|---|
| `PRODUCTION_INFRASTRUCTURE_GAP` | single-node SQLite + local-FS persistence; no prod storage/deploy/secrets/monitoring | infra | provision prod storage + deployment controller (post-SP0011) |
| `PRODUCTION_INFRASTRUCTURE_GAP` | no CI / lockfile / build backend; each absence hashed into the SP0009 genome | release | add provider-neutral CI + pinned lockfile when a runtime target exists |
| `IMPLEMENTATION_GAP` | all external effects are mocks (telephony, email/SMS, calendar, video, PDF, e-sign, payment, AV, OCR, ASR/TTS, web fetch) | product | wire real providers behind the SP0004 replaceable adapters |
| `FIELD_VALIDATION_GAP` | browser E2E is environment-sensitive; excluded from the deterministic release suite | release | stabilize module-scoped fixtures + fixed-port allocation |
| `SP0011_EVALUATION_GAP` | reliability/evaluation and the 1000/1000 score are not produced here; SP0011 interface is PENDING and cannot carry evidence | SP0011 | execute SP0011 against this seal + admission package |
| `OPERATIONAL_GAP` | auth is dev-grade; evidence unanchored (no transparency log deployed); no rollback infra | ops | production auth + anchored transparency (post-SP0011) |

Note the honesty of the second gap: the *absence* of CI, a lockfile, and a build
backend is itself hashed into the SP0009 candidate genome. The system records
what it does not have.

---

## 14. The Architecture Genome and the Program Seal

Modules: `genome.py`, `seal.py`.

**Genome.** The Architecture Merkle forest binds the repository commit, the ten
per-constitution roots, the twin roots, and the hypergraph / epistemic /
invariant / hyperproperty / assurance / gap / verifier-set roots into one
deterministic **global architecture root**. A change to any material root moves
the global root. Omitting a constitution or a root is caught by seal
verification, which recomputes the global root from the same components.

Materialized: `global_architecture_root =
ee167b18786153be`, genome
version `1.0.0`, closure epoch `ACE-2026-07`.

**Seal.** The Program Seal identifies **one** verified snapshot: repository
commit, branch, migration frontier, the genome root, the predecessor twin roots,
the closure state, and the counts that gate closure (critical BOTH/NEITHER,
constitutional blockers, production gaps). It creates **no production authority**
(`INV-0010-60`, `D-0010-28`) — `grants_production_authority` is hard-wired
`false`. A material root change **invalidates** it (`D-0010-27`); historical
seals are immutable and superseded, never overwritten (`D-0010-26`). Closure
requires zero critical BOTH, zero critical NEITHER, and zero constitutional
blockers.

`closure_state()` returns `BLOCKED` on any critical BOTH/NEITHER/blocker; else
`CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS` when
production gaps exist, else `CONSTITUTIONAL_ARCHITECTURE_CLOSED`.

**Materialized result.** `closure_state =
CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS`,
`status: CANDIDATE`, `seal_hash =
7185652a9497741b`, sealed
`2026-07-12`. This is distinction 9 made concrete: a seal over a snapshot, not a
grant of permanent validity or production authority.

---

## 15. Bootstrap-safe N-version verification

Module: `bootstrap_verify.py`.

**A verifier cannot solely certify itself** (`D-0010-24`), and two wrappers over
one engine are common-mode (`D-0010-22`). The ceremony has three phases in three
distinct trust domains:

- **Phase A — the FROZEN SP0009 verifier** (`release-frozen`). Its identity is
  the content hash of its exact files; a verifier modified inside this
  qualification step no longer matches the frozen identity and is rejected
  (`D-0010-23`). The closure tooling never *imports* `tools.release` (the
  fail-closed allowlist forbids it); Phase A checks identity and records the
  SP0009 twin's committed validity.
- **Phase B — the SP0010 REFERENCE verifier** (`closure-reference`) recomputes
  the genome global root from its component class roots.
- **Phase C — an INDEPENDENT verifier** (`closure-independent`) recomputes the
  material roots by a distinct path and searches Phase A and Phase B for
  disagreement.

Verifier diversity is real only across distinct trust domains. The seal is
issued only when required results agree.

**Materialized result.** Phase A frozen identity matches
(`92d9590c…`); Phase B root matches the genome; Phase C agrees with no
disagreements; **3 distinct trust domains**, `diverse: true`, `sealed_ok: true`.

---

## 16. Incremental requalification

Module: `requalify.py`.

When a predecessor root changes, the kernel identifies the changed leaves,
computes the **affected assurance cone** (claims transitively downstream of the
changed constitution's guarantees), stales only those claims, recomputes the
affected closure, and compares with a **full recompute**. The incremental result
**must equal** the full recompute on reference fixtures (`D-0010-25`); otherwise
the impact analysis is unsound (`INCREMENTAL_FULL_MISMATCH`). No old seal
silently remains current after a material root change (`D-0010-27`). This keeps
re-verification cheap without letting it become a second, weaker oracle.

---

## 17. Fail-closed philosophy and the change boundary

Modules: `boundary.py`, `model.py`.

The kernel is **inert governance tooling**: no live external effect, no product
migration (frontier stays v27, AST-checked), and it is never imported by product
code under `finalis/`. Imports are governed by a **fail-closed allowlist** (a
denylist of known-bad calls is bypassable — the SP0008 red-team lesson), so only
a fixed set of standard-library modules is permitted.

Fail-closed shows up throughout: an `UNKNOWN` hard invariant blocks closure; a
missing assumption is a dangling premise, not a satisfied one; a critical claim
in `NEITHER` cannot close; a bounded enumeration that hits its limit is reported
explicitly rather than silently truncated. A `Report` is valid **iff** it
contains zero P0 and zero P1 findings; P2 findings are diagnostic. The closed
vocabulary is a fixed set of ~65 reason codes (`REASON_CODES` in `model.py`,
mirrored in `FINALIS_REASON_CODE_REGISTRY.json`), and any Finding using an
unknown code raises rather than passing.

**Materialized result.** Findings: **P0 = 0, P1 = 0, P2 = 16** — the report is
valid; the sixteen P2s are the single-point-of-assurance diagnostics of §12.

---

## 18. What closure means here, precisely

At commit `1e29581`, on branch `claude/finalis-ai-casewoker-blueprint-f1huse`,
migration frontier v27, SP0010 establishes:

- 10 constitutional interfaces compose into 16 conjunctive assurance hyperedges
  with no dangling premises;
- 38 critical claims are all `SUPPORTED_ONLY` (0 critical `BOTH`, 0 critical
  `NEITHER`), on independent minimal support sets;
- 0 unsupported support cycles; 0 grounded defeaters;
- 12 global invariants `HOLD` (non-compensatory);
- 4 paired-world hyperproperties `PASS` **within their disclosed bounds**;
- 6 critical controls are `NECESSARY_NOT_SUFFICIENT`;
- 0 constitutional blockers; 6 non-blocking production gaps;
- a 3-phase, 3-trust-domain verifier ceremony agrees;
- the closure rebuilds byte-identically.

Therefore the **constitutional architecture is closed with non-blocking
production gaps**, one snapshot is sealed, and SP0011 is admitted
`PENDING_EXECUTION` with **no score**. And, with equal weight: the product is
**`NOT_PRODUCTION_READY`**, production qualification is
**`BLOCKED_PENDING_SP0011`**, the seal **grants no production authority**, the
noninterference results are **bounded, not universal**, and control necessity is
**not** control sufficiency. Both halves of that statement are the constitution.

---

## V5 addendum — proof-carrying, dual-graph, causal closure

SP0010 **V5** (supersedes V2/V3/V4) does not change the mission or the change
boundary; it deepens the *proof*. The following reasoning rules are added to the
constitution, each fail-closed:

1. **Do not trust the description — check it against reality.** A declared
   Architecture Description Graph is compared, node by node, against an
   **independently scanned** Repository Evidence Graph. Each node is exactly one
   of MATCH / DECLARED_ONLY / IMPLEMENTATION_ONLY / CONFLICT / AMBIGUOUS. A
   CONFLICT (the description asserts what the tree contradicts) blocks; a
   critical DECLARED_ONLY blocks; AMBIGUOUS is never rounded up to MATCH.

2. **No ungrounded claim becomes hard truth.** Every declared node must resolve
   an on-disk **source span**; an ungrounded, agent-extracted node is quarantined
   and, if critical, blocks. Description is not evidence.

3. **A solver verdict is advisory until an independent checker validates its
   certificate.** Each critical guarantee carries a proof-carrying certificate;
   a distinct checker re-derives every obligation. A SUPPORTED_ONLY verdict with
   no VALID certificate is a **PROOF_HOLE** and cannot close.

4. **Necessity must be causally identifiable.** A control counts only when its
   effect on the protected property is identifiable (backdoor criterion) — an
   unobserved confounder makes it NOT_IDENTIFIED, which blocks.

5. **An exhausted search is not a proof.** CEGAR proves each safety property
   through a sound abstraction; `LIMIT_REACHED` is never a pass, and a
   concretized real counterexample blocks.

6. **Diversity must be real, not nominal.** Federated N-version verification
   requires heterogeneous backends that are each deterministic, **sensitive** to
   a canary root change, and agreed on the anchor; a backend blind to a change
   is common-mode and blocks.

7. **You may not fix a closure by lowering the bar.** Any minimal correction set
   is invariant-preserving by construction; a repair that would weaken an
   invariant or disable a control is rejected, not selected.

8. **Trust is pinned to exact bytes.** The Trusted Computing Base manifest
   content-hashes the small set of modules the seal depends on; a change to any
   trusted module (down to a comment) moves the TCB root and thus the global
   architecture root. Everything outside the TCB is either re-checked by a TCB
   member or non-load-bearing.

On the sealed repository these eight rules all pass: 57/57 dual-graph nodes
MATCH (0 CONFLICT), 16/16 guarantees certified by the independent checker, 6/6
controls IDENTIFIED, 4/4 properties CEGAR-PROVED, federation CONVERGED across 4
heterogeneous backends, the repair portfolio EMPTY (certified), the TCB complete
— `P0 = 0, P1 = 0`. The V5 roots are folded into the Architecture Genome, so the
Program Seal is fail-closed on the full finding set and pinned to exact bytes.
```
