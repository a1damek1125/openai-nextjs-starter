# FINALIS Research Register (SP0010)

**Execution date:** 2026-07-12. This register lists every external standard and
research item SP0010 drew on, states what each is, its maturity on the execution
day, how SP0010 applies it, and the honesty caveat. Two rules govern the whole
register:

- **Projections are not authority.** Where SP0010 emits an artifact in an
  external schema (OSCAL, SACM, PROV, NIST AI RMF), that artifact is a *view*
  for external consumers. Finalis authority lives in the closure kernel, not in
  the projection.
- **No runtime deployment of any standard is claimed, and formal bounds are
  disclosed.** No formal-verification tool is installed; every model-checked
  property is bounded; noninterference is never claimed as universal proof;
  control presence is never equated with control effectiveness.

---

## 1. Architecture description and assurance-case standards

### ISO/IEC/IEEE 42010:2022 — Architecture description
*What.* The standard vocabulary for architecture descriptions: entity of
interest, stakeholders, concerns, viewpoints, views, correspondences, and known
inconsistencies; and the principle that the **architecture is distinct from its
description**.
*Maturity.* Published international standard (2022 revision).
*How SP0010 applies it.* Directly implemented in `describe.py` — 6 stakeholders,
12 concerns, 5 viewpoints, 24 views (AD-01..AD-24), 3 correspondence rules, and
one recorded known inconsistency (KI-1). See
`FINALIS_ARCHITECTURE_DESCRIPTION_PACKAGE.md`.
*Caveat.* View conformance means the grounding evidence exists on disk, not that
the capability is production-grade.

### OMG SACM 2.3 — Structured Assurance Case Metamodel
*What.* A metamodel for exchanging assurance cases (claims / arguments /
evidence).
*Maturity.* Adopted OMG specification.
*How SP0010 applies it.* As an **external projection** only
(`FINALIS_SACM_PROJECTION.json`): the 16 top-level claims are exported for
evidence exchange.
*Caveat.* The projection is explicitly "evidence exchange only; **not Finalis
authority**." The authoritative reasoning is the four-valued closure, not the
SACM export.

### Assurance 2.0 defeaters (arXiv 2405.15800)
*What.* Defeasible assurance cases with explicit defeaters (rebuttal, undercut,
evidence attack, assumption/freshness invalidation).
*Maturity.* Research; an established direction in assurance-case methodology.
*How SP0010 applies it.* `defeaters.py` implements a grounded-extension defeater
engine; ungrounded defeaters never block, grounded unopposed defeaters are
BLOCKING (`D-0010-05`). Result: no defeaters present, mechanism live.
*Caveat.* Reference implementation of the semantics; not a claim of exhaustive
defeater discovery.

---

## 2. Compliance / provenance projections (control presence ≠ effectiveness)

### NIST OSCAL — Open Security Controls Assessment Language
*What.* A machine-readable format for assessment results and control catalogs.
*Maturity.* Actively maintained NIST project.
*How SP0010 applies it.* As an **assessment-results projection**
(`FINALIS_OSCAL_ASSESSMENT_PROJECTION.json`): the six critical controls are
exported with their counterfactual classification (all
`NECESSARY_NOT_SUFFICIENT`).
*Caveat.* The projection carries the note "**control presence != effectiveness**"
(`D-0010-39`). OSCAL records that controls exist and how they were assessed
in-model; it does not establish real-world effectiveness or sufficiency.

### W3C PROV — Provenance
*What.* A model for the provenance of entities, activities, and agents.
*Maturity.* W3C Recommendation.
*How SP0010 applies it.* As a **provenance projection** of the evidence-atom
algebra (producers, tools, parser families, trust domains, valid-time). The
evidence-provenance root (`84811cf0…`) accompanies the SP0011 admission package.
*Caveat.* Projection of the kernel's evidence provenance; not a separate
authority.

### NIST AI RMF 1.0 (+ Playbook)
*What.* The AI Risk Management Framework functions Govern / Map / Measure /
Manage.
*Maturity.* AI RMF 1.0, **revising in 2026**; the SP0010 mapping is
**snapshot-versioned** (`D-0010-40`).
*How SP0010 applies it.* A snapshot mapping (`FINALIS_NIST_AI_RMF_MAPPING.json`):
Govern → governed_work + safety; Map → contract inventory + semantics; Measure →
release assurance + SP0011 (**pending**); Manage → defeaters + requalification.
*Caveat.* Mapping only, snapshot-pinned to AI RMF 1.0; "Measure" is explicitly
pending SP0011. No runtime deployment of the framework is claimed.

---

## 3. Formal-methods and hyperproperty research

### TLA+/TLC, Apalache, Z3 — optional formal projections
*What.* Model checkers and an SMT solver for temporal/invariant verification.
*Maturity.* Mature, widely used tools.
*How SP0010 applies it.* As **OPTIONAL projections only**. They are **not
installed** in the execution environment. SP0010 therefore uses a **mandatory
deterministic repository-local reference verifier** (`modelcheck.py`,
`bootstrap_verify.py`) instead of depending on any external prover.
*Caveat.* No external formal tool ran. The reference model checks
(`four_valued`, `hyperedge_conjunctive`, `root_determinism`, `unsupported_cycle`
— all `HOLD`) are bounded, deterministic, repo-local checks, not TLC/Apalache/Z3
proofs.

### Hyperproperties — noninterference / observational determinism / confidentiality (arXiv 2510.03942, 2512.23324, 2405.13488)
*What.* Properties over *sets* of executions (paired worlds), the correct frame
for information-flow and noninterference claims.
*Maturity.* Active research literature.
*How SP0010 applies it.* `noninterference.py` runs four paired-world
hyperproperties (tenant / approval / provider-account / control-language). Each
compares two bounded worlds differing only in a protected variable and requires
the other party's observable to be invariant. All four `PASS`.
*Caveat.* **Bounded reference models, not universal proof** (`D-0010-41`). Path
absence in a single execution is explicitly *not* accepted as noninterference.
Each result discloses its `varying_domain`; the same limits are re-stated in the
SP0011 admission package's `noninterference_limits`.

### Semiring / minimal-support semantics (arXiv 2605.10829)
*What.* Provenance semirings and minimal-support (antichain) semantics for
evidence, bounded to avoid symbolic explosion.
*Maturity.* Research.
*How SP0010 applies it.* `evidence.py` computes minimal antichain support sets
with AND/OR composition, strict-superset removal, and domain-based independence;
bounds are exact and truncation is an explicit `SUPPORT_SET_LIMIT_REACHED`.
*Caveat.* Bounded (support-set limit 256); no symbolic explosion; truncation
never silent.

### Formal evidence generation (arXiv 2602.03550)
*What.* Techniques for generating machine-checkable evidence for assurance.
*Maturity.* Research.
*How SP0010 applies it.* Informs the evidence-atom + minimal-support-set design;
each atom is content-addressed and its on-disk grounding is verified.
*Caveat.* Repo-local evidence; not externally attested (see the unanchored-
evidence production gap).

---

## 4. Graph / knowledge-graph and repository-grounded verification

### Assurance-case graph diagnostics (arXiv 2604.20577)
*What.* GNN/LLM-based diagnostics over assurance-case graphs.
*Maturity.* Research.
*How SP0010 applies it.* As a **candidate technique only** — SP0010 uses
deterministic graph analysis (Tarjan SCCs, least-fixed-point support, grounded
extension), not GNN/LLM inference, for any load-bearing conclusion.
*Caveat.* No GNN/LLM output is treated as evidence in the closure.

### Knowledge graphs for verification (arXiv 2605.06434)
*What.* Using knowledge graphs to structure verification artifacts.
*Maturity.* Research.
*How SP0010 applies it.* Conceptual grounding for the cross-twin consistency
matrix and the assurance hypergraph.
*Caveat.* Structural inspiration; the kernel's graphs are explicit and
deterministic.

### Repository-grounded verification (arXiv 2601.10112, 2601.13007)
*What.* Verification anchored in the actual repository, where **LLM-proposed
edges remain proposals until verified**.
*Maturity.* Research.
*How SP0010 applies it.* Every evidence reference, control exercise site, and
twin root is checked against on-disk repository facts; nothing is admitted on an
unverified proposal. The closure opens no external effect and derives all facts
from the frozen tree.
*Caveat.* Any LLM-proposed relationship would be a proposal, not evidence, until
verified against the repository — the kernel admits only the verified facts.

---

## 5. Vendor comparison — Viktor 2026 (treated as vendor claims)

*What.* Viktor 2026 markets an AI-employee product with: one coherent employee,
workspace isolation, separate connected accounts, OAuth-first, credentials kept
outside model context, approval before sensitive actions, task termination,
pause/resume, workflow ownership, and visible status.
*Maturity.* Vendor product claims (execution-day marketing posture).
*How SP0010 applies it.* As a **comparison baseline only** — these are treated as
**vendor claims**, not verified properties. Finalis *strengthens* the same
surface with machine-checked constructs: relational tenant proofs (paired-world
noninterference), context-bound approval, authority conservation, capability
attenuation, versioned contracts, provider replaceability, outcome evidence, and
global assurance closure.
*Caveat.* SP0010 makes no claim about Viktor's actual implementation. The Finalis
strengthenings are themselves bounded (bounded noninterference models; controls
necessary-not-sufficient), and none of them makes the product production-ready.

---

## 6. Standing honesty caveats (apply to the whole register)

- **No formal tool installed.** TLA+/TLC, Apalache, and Z3 are optional and were
  not run; the mandatory verifier is the deterministic repo-local reference
  engine.
- **Bounded models.** Every hyperproperty and model check is bounded and
  discloses its bound; none is a universal proof.
- **No universal proof.** "No detected cross-tenant path" is not "noninterference
  proven"; the closure only asserts what the paired-world models establish within
  their domains.
- **Control presence ≠ effectiveness.** OSCAL export and counterfactual analysis
  show necessity in-model, not sufficiency or real-world effectiveness.
- **Projections are views, not authority.** OSCAL, SACM, PROV, and NIST AI RMF
  outputs are external projections; Finalis authority is the closure kernel.
- **No score, no fabricated evidence.** SP0010 assigns no 1000/1000 score and
  fabricates no evaluation evidence; SP0011 is admitted `PENDING_EXECUTION`.
- **Not production-ready.** None of these standards' presence implies deployment;
  the product remains `NOT_PRODUCTION_READY` with production qualification
  `BLOCKED_PENDING_SP0011`.
```
