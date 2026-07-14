# FINALIS Architecture Description Package (ISO/IEC/IEEE 42010)

Module: `tools/architecture_closure/describe.py`. Materialized in the closure
twin under `architecture_description` and `conformance_matrix`; description hash
`a6e272bb7b13ac9799dea389a38810a384367613cc1794c612eb085a78605042`.

**The architecture is distinct from its description** (`D-0010-11`). This package
is the *description*: it records stakeholders, concerns, viewpoints, 24 views,
correspondence rules, and — crucially — the **repository conformance** of each
view (does its declared evidence exist on disk?). A view whose evidence is
present is `IMPLEMENTED`; a documentation-only view is `DECLARATIVE_ONLY`. Both
are recorded; neither is hidden.

**Entity of interest:** FINALIS AI Employee OS (governance kernel + mocked
vertical SaaS).

---

## 1. Stakeholders and concerns

Six stakeholders, each with the concerns the description must serve for them:

| Stakeholder | Concerns |
|---|---|
| `architect` | compositional_coherence, no_circular_assurance |
| `safety_owner` | safety_dominance, hazard_control |
| `security_owner` | tenant_isolation, authority_conservation |
| `release_owner` | proof_not_authority, release_runtime_separation |
| `evaluator_sp0011` | reliability_admission, evidence_provenance |
| `operator` | production_gaps, observability |

The full concern set (twelve) also includes `compositional_coherence`,
`evidence_provenance`, `observability`, `production_gaps`, and
`proof_not_authority`, which recur across stakeholders. `evaluator_sp0011` is the
SP0011 successor as a first-class stakeholder — the description is written partly
*for* the evaluator, which is why reliability admission and evidence provenance
are named concerns rather than assumptions.

---

## 2. Viewpoints

Views are grouped by concern into five viewpoints:

- **VP-COMPOSITION** — AD-01, AD-03, AD-04, AD-08
- **VP-SECURITY** — AD-10, AD-11
- **VP-SAFETY** — AD-12
- **VP-EVOLUTION** — AD-15, AD-16, AD-17
- **VP-OPERATIONS** — AD-18, AD-22, AD-23, AD-24

Views not assigned to a viewpoint (AD-02, AD-05, AD-06, AD-07, AD-09, AD-13,
AD-14, AD-19, AD-20, AD-21) are still first-class views; viewpoints are a
concern-oriented grouping, not a partition.

---

## 3. The 24 views and their repository conformance

Each view names the real repository evidence path(s) that ground it; conformance
is `IMPLEMENTED` when at least one path exists on disk. **All 24 views are
`IMPLEMENTED`** at commit `1e29581` — no view is `DECLARATIVE_ONLY`.

| View | Title | Grounding evidence | Conformance |
|---|---|---|---|
| AD-01 | Entity of Interest & Mission | `docs/roadmap/ROADMAP_LOCK_1_FINALIS_AI_EMPLOYEE_OS.md` | IMPLEMENTED |
| AD-02 | Stakeholders & Concerns | `docs/architecture` | IMPLEMENTED |
| AD-03 | Constitutional Layers | `docs/architecture/FINALIS_1000_MASTER_ARCHITECTURE_LOCK.md` | IMPLEMENTED |
| AD-04 | Capabilities | `docs/architecture` | IMPLEMENTED |
| AD-05 | Runtime Boundaries | `finalis/portal/app.py` | IMPLEMENTED |
| AD-06 | Semantics | `tools/semantics`, `docs/semantics` | IMPLEMENTED |
| AD-07 | Data & Memory | `finalis/portal/db.py` | IMPLEMENTED |
| AD-08 | Program Dependencies | `tools/program_graph`, `docs/program/FINALIS_1000_PROGRAM_REGISTRY.json` | IMPLEMENTED |
| AD-09 | Technology & Providers | `tools/technology`, `docs/technology` | IMPLEMENTED |
| AD-10 | Authority & Approvals | `tools/governed_work`, `finalis/portal/app.py` | IMPLEMENTED |
| AD-11 | Tenant Isolation | `finalis/portal/app.py`, `finalis/portal/db.py` | IMPLEMENTED |
| AD-12 | Safety & Regulatory Truth | `tools/safety`, `docs/safety` | IMPLEMENTED |
| AD-13 | Governed Work | `tools/governed_work`, `docs/governed_work` | IMPLEMENTED |
| AD-14 | Outcomes & Evidence | `tools/governed_work` | IMPLEMENTED |
| AD-15 | Contract Evolution | `tools/compatibility`, `docs/compatibility` | IMPLEMENTED |
| AD-16 | Contract Inventory | `tools/contracts_inventory`, `docs/contracts_inventory` | IMPLEMENTED |
| AD-17 | Release Assurance | `tools/release`, `docs/release` | IMPLEMENTED |
| AD-18 | Failure & Recovery | `finalis` | IMPLEMENTED |
| AD-19 | Learning | `tools/governed_work` | IMPLEMENTED |
| AD-20 | Multilingual Control | `tools/semantics` | IMPLEMENTED |
| AD-21 | Pack Extensibility | `finalis` | IMPLEMENTED |
| AD-22 | Observability | `finalis/audit.py` | IMPLEMENTED |
| AD-23 | Performance & Scale | `docs/architecture` | IMPLEMENTED |
| AD-24 | Production Gaps | `docs/audits` | IMPLEMENTED |

**A caution about "IMPLEMENTED".** Here it means only that the view's grounding
evidence *exists on disk* — the description conforms to the repository. It does
**not** mean the capability is production-grade. AD-24 (Production Gaps) is
itself `IMPLEMENTED` precisely because the audit documents that record the six
standing production gaps exist; the view faithfully points at the evidence that
the system is not production-ready. Conformance of the *description* and
readiness of the *product* are different questions, and this package answers only
the first.

---

## 4. Correspondence rules

Three rules require pairs of views to agree:

| Rule | From → To | Meaning |
|---|---|---|
| CR-1 | AD-11 → AD-10 | tenant isolation view must agree with the authority view |
| CR-2 | AD-16 → AD-15 | contract inventory must agree with contract evolution |
| CR-3 | AD-17 → AD-16 | release assurance references the contract inventory genome |

CR-3 is the description-level reflection of the machine-checked cross-link in the
closure (`CT-release-genome-crosslink`): the Release Assurance twin embeds the
Contract Genome root and that pin equals the committed Contract Genome
`global_root`.

---

## 5. The one known inconsistency (KI-1)

The description records exactly one known inconsistency, and does **not** paper
over it:

> **KI-1** — Contract Genome `leaf_counts` (routes 423, tables 107) differ from
> the audit raw grep (routes 402, tables 108) — **distinct enumeration
> provenance, not equated.**

The two numbers come from different methods: the Contract Genome enumerates
contract surfaces through its own structural parse, while the audit uses raw
text grep. 42010 requires known inconsistencies to be *recorded*, not silently
resolved. SP0010 records KI-1 as a provenance difference rather than forcing the
two counts to match — consistent with the cross-twin rule that *similar labels
do not force identity* and that contradictions stay first-class. KI-1 is
descriptive; it is not a closure blocker and does not appear as a cross-twin
contradiction, because the two counts are not claimed to measure the same thing.

---

## 6. How to regenerate

`python -m tools.architecture_closure describe --root .` emits this description
deterministically; the `conformance_matrix` and the full `views` array also
appear inside the closure twin. Because `describe.build_description` hashes the
canonicalized description, any change to a view, its evidence, a viewpoint, a
correspondence rule, or KI-1 moves `description_hash`.
```
