# SP0009 — Roadmap Identity Report

*Generated deterministically from the Program Twin node and the materialized
release twin (`docs/release/FINALIS_RELEASE_TWIN.json`). Execution date:
2026-07-12.*

---

## 1. Canonical identity

| Field | Value |
|---|---|
| **Canonical SP id** | `SP0009` |
| **Canonical title** (Program Twin node) | Release Train, Quality Gates and Definition of Done |
| **Extended title** | FINALIS Release Assurance, Quality Gates, Definition of Done & Proof-Carrying Promotion Constitution |
| **Mission class** | Constitution + deterministic release-assurance kernel |
| **Kernel location** | `tools/release/` |
| **CLI** | `python -m tools.release <command>` (26 subcommands) |

The `roadmap_identity` CLI subcommand emits this identity directly, including the
canonical and extended titles and the honest boundary list.

---

## 2. Roadmap position

| Relation | Missions |
|---|---|
| **Predecessors** | `SP0007` (Backward Compatibility, Migration, Versioning & Contract Evolution Constitution), `SP0008` (Canonical Contract Surface Inventory & Dependency Truth) |
| **Successors** | `SP0010` (Global Brand Naming Sprint), `SP0011` (Evaluation and 1000/1000 Score Charter) |

### Relation to SP0008 (predecessor consumed)
SP0009 **consumes SP0008's Contract Genome and canonical inventory** to build the
impact cone and the dependency-closed release slice. The candidate genome binds the
contract-genome root
`7269f08cd7d53679cae6ce3b134a00d6dd6146fde0c60e712a065a711be377b1`, read from
`docs/contracts_inventory/FINALIS_CONTRACT_GENOME.json`. The release slice `RS-SP0009`
records `CHG-SP0009` depending on `SP0008`, closed with no missing dependencies. The
impact cone for the reference candidate is over governance tooling, tests, and docs
only — no product contract is impacted (`impacted_contracts: []`), which is why the
change is low-risk despite touching 36 paths.

### Relation to SP0011 (successor reserved, not fabricated)
SP0009 reserves a **`PENDING_SP0011` interface** for evaluation evidence and **does
not fabricate any**. `sp0011_qualification` is `PENDING_SP0011` with `evidence: null`
and the note that "SP0011 Evaluation has not run; no evaluation evidence exists and none
may be fabricated" (`D-0009-61`). The AI release closure records the same honesty
(`SP0011_EVIDENCE_FABRICATION_REJECTED` guards against invented scores). SP0009 makes
no 1000/1000 claim; that charter is SP0011's, unstarted.

---

## 3. Mission class

SP0009 is both a **constitution** (the governing principles for proof-carrying,
revocable promotion) and a **deterministic release-assurance kernel** (the executable
`tools/release/` package that materializes and validates the reference candidate). It
is **governance tooling only** — never imported by product code, with zero deployment,
migration, credential, or external effect.

---

## 4. Existing CI / release mechanisms — documented ABSENCE

The release archaeology reads the repository's actual state, and finds that the usual
release machinery **does not exist here**. These absences are recorded as findings and
hashed into the candidate genome (absence is identity):

| Mechanism | State |
|---|---|
| CI workflow files (`.github/workflows`) | **ABSENT** (`ci_workflows_present: false`, `ci_workflow_hash: ABSENT`) |
| Lockfile pinning exact versions | **NONE** (`lockfile_pins_exact_versions: false`) |
| Declared build backend (`[build-system]`) | **NONE** (`build_backend_declared: false`) |
| Published artifacts | **NONE** (`published_artifacts: []`) |
| **Release mechanism today** | full pytest suite in 4 file shards with `tests/test_browser_e2e.py` excluded, plus per-mission P0=0/P1=0 validators |

Test surface at analysis time: **451 test files** (`test_file_count: 451`), browser E2E
present.

---

## 5. Known flake state

One known, pre-existing flake is documented and reproduced — not introduced by SP0009:

- **Test:** `test_browser_e2e.py::test_evidence_prompt_injection_flow_in_browser`
- **Classification:** `ENVIRONMENT_INSTABILITY`
- **Mechanism:** module-scoped shared server+page fixtures, fixed port 8765, stale-text
  waits under parallel load
- **Behavior:** passes in isolation; fails under full-suite parallel load
- **Prior documentation:** `docs/compatibility/FINALIS_SWARM_REVIEW.md`,
  `docs/contracts_inventory/FINALIS_SWARM_REVIEW.md`
- **SP0009's stance:** reproduced and classified, **NOT attributed to SP0009, NOT
  deleted, NOT weakened.** It is the single P2 finding in the reference twin
  (P0=0 / P1=0 / P2=1).

The deterministic (non-browser) suite is green and the mutation locks are green
(`docs/release/FINALIS_TEST_EVIDENCE.json`); mutation adequacy is 32/32 killed,
kill-rate 1.0.

---

## 6. Scope decision

**Decision: PROCEED, retaining V3 hardening.** The SP0009 change is assessed as
**semantically equivalent** to its intended blueprint — governance tooling, tests, and
docs that add no product surface — so the change proceeds and the V3 hardening is
retained rather than reworked. The classifier confirms the change carries no
tenant/authority/safety/migration/supply-chain surface (risk vector all-LOW, no hard
flags), which is consistent with a proceed-and-retain decision rather than a re-scope.

---

## 7. Baseline

| Field | Value |
|---|---|
| **Branch** | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| **Built on** | the SP0008 commit (`bb80912` — "SP0008: Canonical Contract Surface Inventory & Dependency Truth") |
| **Source commit binding** | `HEAD` (candidate genome `15fa5dc5…`) |
| **Release policy epoch** | `RPE-2026-07` |
| **Reference candidate** | `RC-SP0009`, status `READY_FOR_LATER_PROMOTION`, `qualifiable: true` |

The predecessor chain visible in history: SP0004 → SP0005 → SP0006 → SP0007 → SP0008,
with SP0009 building directly on the SP0008 commit.
