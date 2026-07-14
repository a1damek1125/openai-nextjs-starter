# SP0010 Roadmap Identity Report

**Canonical id:** SP0010
**Canonical title:** FINALIS Architecture Program Final Gate
**Extended title (V5):** Proof-Carrying Architecture Assurance Closure,
Compositional Coherence, Relational Noninterference & Cryptographic Program Seal
**Classification target:** `FINALIS_ARCHITECTURE_ASSURANCE_CLOSURE_V4`
**Spec revision:** SP0010 **V5 FINAL** (supersedes V2/V3/V4)
**Mission class:** constitutional program closure + architecture description
package + program seal (no evaluation, no score)
**Execution date:** 2026-07-12
**Frozen baseline commit:** `1e29581` (SP0009); authoring successor `d3f2fd9`
(SP0010 V3)

This report states what SP0010 *is*, resolves the scope-labeling question
transparently, records the frozen baseline it operated over, documents the
PROCEED decision, and (§0) records the V5 supersession — the new proof-carrying
subsystems added on top of the V3 core and the elements deliberately excluded.

---

## 0. V5 supersession & scope decision (PROCEED, not BLOCKED)

**Scope check first (spec FINAL EXECUTION COMMAND).** The V5 specification
requires that, before any tracked file is modified, this report confirm whether
the canonical SP0010 scope materially differs from the spec. It does **not**.
The canonical scope — *Architecture Program Final Gate: prove SP0000–SP0009
compose into one coherent, non-circular, evidence-grounded, replaceable,
auditable architecture, then seal one snapshot and admit SP0011 with no score* —
is **semantically identical** across V2/V3/V4/V5. V5 changes only the *depth of
proof*, not the mission. Therefore the decision is **PROCEED**, not
`BLOCKED_BY_SP0010_SCOPE_MISMATCH`. The stale program-registry label ("Global
Brand Naming Sprint") is handled exactly as in §2 (documented non-silent
reassignment, registry unedited, recorded as `ACCEPTED_FUTURE_ENHANCEMENT`).

**Baseline reconciliation (repository truth overrides authoring-time text).**
The V5 spec names SP0009 commit `1e29581` as the expected baseline but explicitly
permits *an authorized successor* and states *repository truth overrides every
authoring-time statement*. The repository HEAD is `d3f2fd9` — the committed
SP0010 V3 gate, a direct authorized descendant of `1e29581`. The closure still
**freezes and verifies the SP0000–SP0009 arc at SP0009 head `1e29581`, migration
frontier v27** (that is the object under assurance); the V3/V5 gate commits are
the *authoring* successors that carry the tooling. This is consistent, not a
baseline violation: the frozen object is the predecessor arc; the tooling that
proves it lives one commit later.

**What V5 ADDS on top of the V3 core** (all deterministic, standard-library
only, never imported by product code, zero product/runtime/migration/external
effect — the V3 change boundary is unchanged and re-verified):

| V5 subsystem | Module | What it proves |
|---|---|---|
| Dual-Graph conformance | `dual_graph.py` | Declared Architecture Description Graph vs an **independently-built** Repository Evidence Graph; every node classified MATCH / DECLARED_ONLY / IMPLEMENTATION_ONLY / CONFLICT / AMBIGUOUS. A CONFLICT is P0. |
| Extraction Uncertainty Firewall | `extraction.py` | Every declared node must carry an on-disk **source span**; an ungrounded, agent-extracted node is quarantined UNGROUNDED and can never become hard truth (fail-closed). |
| Trusted Computing Base manifest | `tcb.py` | Enumerates the minimal set of modules the verdict trusts; anything outside the TCB cannot silently affect the seal; TCB is content-hashed. |
| Proof-Carrying Certificates + Independent Checker | `certificates.py` | Each critical closure claim carries a machine-checkable certificate; a **small independent checker** re-validates it. A solver verdict *without* a valid certificate is **advisory only**, never closing. |
| Causal + counterfactual control verification | `causal.py` | Structural causal model per control; identifiability IDENTIFIED / PARTIALLY_IDENTIFIED / NOT_IDENTIFIED; only an IDENTIFIED necessary control counts. |
| CEGAR | `cegar.py` | Sound abstraction, concretize counterexamples, classify spurious vs real, refine; `LIMIT_REACHED` is **not** PASS. |
| Assurance Robustness Frontier | `robustness.py` | Per-domain **cut number** — how many independent supports must be removed to break each critical guarantee; a cut of 1 is a single point of assurance. |
| Minimal Correction Sets + Repair Portfolios | `correction.py` | If anything were BLOCKED, the lexicographic minimal repair (hard constraints first) that **cannot weaken any invariant**; on a clean closure the portfolio is empty and that emptiness is itself certified. |
| Federated N-Version verification | `federated.py` | Heterogeneous proof backends (canonical-JSON, Merkle-tree, sorted-fold) with a **convergence gate**; divergence blocks the seal. |
| W3C PROV + LGGT+ projections | (docs) | The closure evidence re-expressed as W3C PROV provenance and an LGGT+ assurance-certification projection. |
| Expanded gap taxonomy | `model.py` | `PROOF_HOLE`, `HYPERPROPERTY_GAP`, `CONTROL_EFFECTIVENESS_GAP`, `DUAL_GRAPH_CONFLICT`, `EXTRACTION_UNGROUNDED`, `CERTIFICATE_MISSING`, `CEGAR_LIMIT` — new blocking/advisory gap types. |

**Retained V3 hardening** (all 7 red-team fixes R1–R7 remain regression-locked):
fail-closed seal on the full P0/P1 set, genuine Phase-C construction diversity,
hardcoded frozen-verifier constant, external-only cycle anchor, producer-quotient
independence, on-disk-grounded counterfactuals, symbol-checked invariant controls.

**Elements deliberately EXCLUDED** (recorded, not silently dropped): no external
solver/SMT dependency is introduced (the "solver" is a deterministic
standard-library reference reasoner, and its verdict is gated by the independent
certificate checker exactly as the spec requires for an *untrusted* solver); no
network proof backend; no change to the frozen product runtime; no 1000/1000
score. These exclusions are logged as `ACCEPTED_FUTURE_ENHANCEMENT`, consistent
with the standing change boundary.

---

## 1. Identity and mission class

SP0010 is the **final architecture gate** of the FINALIS program. Its job is to
determine whether the ten predecessor constitutions SP0000–SP0009 compose into
one coherent, non-circular, evidence-grounded, replaceable, auditable
architecture, then to seal one verified snapshot and hand SP0011 an admission
package. It is a *closure* mission, not a *build* mission and not an *evaluation*
mission.

Concretely SP0010 produces three deliverable classes:

1. **Constitutional program closure** — the Architecture Assurance Closure twin
   (interfaces, hypergraph, epistemic states, cross-twin matrix, invariants,
   hyperproperties, counterfactual controls, resilience, gaps, genome, seal,
   verifier ceremony).
2. **An architecture description package** — the ISO/IEC/IEEE 42010 view set
   (24 views, stakeholders, viewpoints, correspondence rules, conformance).
3. **A Program Seal + SP0011 admission package** — one sealed snapshot that
   grants no production authority, and an admission package with **no score and
   no fabricated evaluation evidence**.

What SP0010 explicitly does **not** do: it assigns no 1000/1000 score, closes no
product/operational/field readiness, deploys nothing, changes no product
runtime, and performs no external effect. The product remains
`NOT_PRODUCTION_READY`; production qualification is `BLOCKED_PENDING_SP0011`.

---

## 2. The scope-reassignment decision (stated transparently)

The FINALIS program registry
(`docs/program/FINALIS_1000_PROGRAM_REGISTRY.json`) labels the SP0010 node
**"Global Brand Naming Sprint"** — a **stale placeholder with no outputs and no
evidence**. Three converging authorities establish the *actual* canonical scope
of SP0010 as the Architecture Program Final Gate:

- the **SP-AUTHOR-0000 mission** that defines the program's purpose;
- the **SP0000–SP0009 constitutional arc**, which is an architecture-assurance
  progression that structurally requires a final composition gate; and
- the declared **successor SP0011 = Evaluation** ("Evaluation and 1000/1000
  Score Charter"), which presupposes a completed, sealed architecture to
  evaluate.

A naming sprint has no coherent place between a release-assurance constitution
(SP0009) and an evaluation charter (SP0011). SP0010 therefore proceeded under a
**documented, non-silent reassignment**, following the **SP0006 precedent** for
correcting a stale registry label without editing the registry. Two consequences
were handled explicitly:

- the naming activity is recorded as an **`ACCEPTED_FUTURE_ENHANCEMENT`** gap
  (a non-blocking gap type in the taxonomy), and
- **the program registry was NOT edited** — SP0010 references the existing
  `program_id` and never mints competing constitutional truth (the cross-twin
  parallel-registry guard confirms this).

This decision is surfaced directly by the CLI `roadmap_identity` subcommand, so
the reassignment is machine-visible, not buried in prose.

---

## 3. Predecessors SP0000–SP0009 (with frozen commits)

The ten predecessor constitutions, their titles (from
`tools/architecture_closure/interfaces.py`), and the exact commits recorded at
the freeze ceremony:

| SP | Title | Commit |
|---|---|---|
| SP0000 | Architecture Lock | `e1b6b5c` |
| SP0001 | Architecture Immune System | `19413f2` |
| SP0002 | Semantic Operating Constitution | `3eacdb0` |
| SP0003 | Program Dependency & Uncertainty Constitution | `1ffb4e4` |
| SP0004 | Technology Sovereignty Constitution | `e82ca87` |
| SP0005 | Safety Kernel, Assurance & Regulatory Truth | `610e1e3` |
| SP0006 | Governed Work, Delegated Autonomy & Outcome Accountability | `d6ac046` |
| SP0007 | Compatibility, Migration & Contract Evolution | `4eda536` |
| SP0008 | Contract Inventory & Contract Genome | `bb80912` |
| SP0009 | Release Assurance, Quality Gates & Definition of Done | `1e29581` |

Each constitution contributes an interface (owned concepts / assumptions /
guarantees / invariants / evidence). The assumption chain is acyclic: SP0000
anchors the baseline; SP0001–SP0004 assume the baseline; SP0005 assumes semantics
+ baseline; SP0006 assumes safety dominance; SP0007 assumes historical epoch
interpretability; SP0008 assumes directional contract evolution; SP0009 assumes
the sealed contract genome and context-bound approval. A missing assumption is
never treated as satisfied.

**SP0001, the architecture immune system**, is the existing architecture-audit
mechanism the program already relies on: it owns `architecture_conformance` and
`drift_detection`, assumes the SP0000 baseline, and enforces
`architecture_and_description_distinct`. SP0010 does not replace SP0001; it
composes SP0001's conformance guarantee into the global hypergraph as one
supported claim among 38.

---

## 4. Successor SP0011 and the hand-off

**SP0011 = "Evaluation and 1000/1000 Score Charter."** SP0010 produces its
admission package and nothing more:

- `admission_state = ADMITTED_PENDING_EXECUTION`;
- `score = null` (SP0010 assigns no score, `D-0010-45`);
- `evaluation_evidence = null` (never fabricated before SP0011 runs);
- the package carries the Program Seal hash, the genome root, the 16 top-level
  claims, the 12 global invariant statuses (all `HOLD`), the assumptions,
  the evidence-provenance root, an empty contradictions list, an empty
  critical-unknowns list, the 6 production gaps, the formal bounds
  (`noninterference: bounded reference model`, `resilience: N-1 EVIDENCE_DOMAIN`)
  and the per-hyperproperty noninterference limits.

The admission-package validator rejects any of: a state other than
`ADMITTED_PENDING_EXECUTION`, a non-null score, or non-null evaluation evidence
(`SP0011_EVIDENCE_FABRICATION_REJECTED`). SP0011 may *evaluate* these artifacts;
it may not rewrite them to obtain a higher score.

---

## 5. Relation to SP0009

SP0010 **consumes** SP0009's outputs and **freezes** its verifier:

- it reads the SP0009 **Release Assurance twin**
  (`docs/release/FINALIS_RELEASE_TWIN.json`, root
  `916dd687…`) as a predecessor twin root and cross-links it;
- it records the **FROZEN SP0009 verifier identity** — the content hash of the
  exact verifier files `tools/release/{validate,modelcheck,boundary,envelope,qualify}.py`
  — as `92d9590c…`, and uses it as the Phase-A verifier of the bootstrap
  ceremony.

The closure tooling **never imports** `tools.release`; it verifies the frozen
verifier's *identity* and the twin's *committed validity* without executing
SP0009's engine in-process. A verifier modified inside SP0010's qualification
step no longer matches the frozen identity and cannot serve as the frozen
Phase-A verifier — a verifier cannot silently re-certify itself.

---

## 6. The frozen baseline

Module: `freeze.py`. The deterministic baseline freeze record:

- **Branch:** `claude/finalis-ai-casewoker-blueprint-f1huse`
- **HEAD:** `1e29581` (= SP0009)
- **Migration frontier:** v27 (AST-extracted from `finalis/portal/db.py`;
  unchanged by SP0010)
- **Predecessor commits:** the ten listed in §3
- **Predecessor twin roots:** `contract_genome
  7269f08c…`, `contract_inventory 52c462f8…`, `release_assurance
  916dd687…`
- **Frozen SP0009 verifier hash:** `92d9590c…`
- **Program registry present:** true
- **freeze_hash:** `89cf0572…`

Any material change after freeze (a divergent fresh freeze, or a migration
frontier other than v27) raises `BASELINE_CHANGED_AFTER_FREEZE` /
`BASELINE_CHANGED` and invalidates the candidate (`D-0010-27`). Git SHAs are
recorded facts of the ceremony; the tooling opens no subprocess and derives
everything else deterministically from the tree.

---

## 7. The PROCEED decision

SP0010 proceeded, and closure succeeded, on the following grounds:

- **Scope resolved.** The stale "Global Brand Naming Sprint" label was corrected
  by documented non-silent reassignment (SP0006 precedent); the naming work is
  logged as `ACCEPTED_FUTURE_ENHANCEMENT`; the registry was left unedited.
- **Baseline clean and frozen.** HEAD `1e29581`, frontier v27, all predecessor
  twin roots present and read, frozen verifier identity recorded.
- **Composition verified.** 10 interfaces → 16 conjunctive hyperedges, no
  dangling premises; 38 critical claims all `SUPPORTED_ONLY`; 0 unsupported
  cycles; 0 grounded defeaters; 12 invariants `HOLD`; 4 hyperproperties `PASS`
  within bounds; 6 controls `NECESSARY_NOT_SUFFICIENT`.
- **No blockers.** 0 constitutional blockers; 6 production gaps, all
  non-blocking and honestly recorded.
- **Verifier diversity satisfied.** 3-phase ceremony across 3 distinct trust
  domains agrees; `sealed_ok: true`.
- **Boundary respected.** No product runtime change, no migration, no external
  effect; closure tooling not imported by product code.

**Outcome:** `closure_state =
CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_PRODUCTION_GAPS`; one
snapshot sealed (`status: CANDIDATE`, `seal_hash 7185652a9497741b…`); SP0011 admitted
`PENDING_EXECUTION` with no score. Product `NOT_PRODUCTION_READY`; production
qualification `BLOCKED_PENDING_SP0011`.
```
