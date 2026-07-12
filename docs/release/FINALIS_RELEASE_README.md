# FINALIS Release Assurance — README

The SP0009 release-assurance kernel is a **deterministic, repository-local** command
line tool. It reads the repository, materializes the reference candidate `RC-SP0009`
and its twin, and answers the release questions as **canonical JSON**. It performs **no
deployment, no migration, no external effect**, reads no secrets, and is never imported
by product code.

---

## Running

```
python -m tools.release [global options] <command> [command options]
```

**Global options come BEFORE the subcommand** (they belong to the top-level parser):

| Option (before the command) | Meaning |
|---|---|
| `--root <path>` | repository root to analyze (default `.`) |
| `--json` | emit compact **canonical** JSON (deterministic byte form) instead of pretty-printed JSON |

**Command options come AFTER the subcommand.** Most commands that report on the twin
accept:

| Option (after the command) | Meaning |
|---|---|
| `--from <file>` | load a materialized twin from a file instead of rebuilding it from source (e.g. `docs/release/FINALIS_RELEASE_TWIN.json`) |

Ordering matters: `--root`/`--json` before the command, `--from` (and `classify`'s
positional paths) after it. For example `python -m tools.release --root . validate` is
correct, while `python -m tools.release validate --root .` is rejected by the argument
parser.

When `--from` is omitted, the command **rebuilds the twin from source** on the fly.
Because the kernel is deterministic, a fresh rebuild is byte-identical to the committed
twin (this is exactly what `validate` checks).

Run from the repository root so the archaeology and impact analysis see the real tree.

---

## The 26 subcommands

| Command | Answers |
|---|---|
| `roadmap_identity` | SP0009 canonical/extended title, predecessors, successors, boundary |
| `archaeology` | the repository's actual release state (CI absence, lockfile absence, flakes, test count) |
| `classify` | change classes + 10-dimension risk vector for given paths |
| `create_candidate` | the immutable candidate record and its genome |
| `impact` | the impact cone over the SP0008 inventory |
| `slice` | the dependency-closed release slice |
| `plan_gates` | gate applicability plan, results, and verdict |
| `select_tests` | mandatory + selected tests and the selection proof |
| `flakes` | flake classification and environment-conditioned posterior |
| `flake_clusters` | systemic co-failure (Jaccard) clusters |
| `rerun_ledger` | append-only execution ledger + rerun accounting |
| `build_manifest` | hermetic build manifest |
| `reproduce` | reproducibility (byte-equality) record |
| `builder_quorum` | attestation/builder quorum and domain diversity |
| `artifact_closure` | the artifact closure graph |
| `verify_attestations` | attestations (subject digest + predicate) |
| `verify_trust` | trust roots (version, expiry, revocation, threshold) |
| `verify_transparency` | transparency (Merkle inclusion) receipts |
| `sbom` | the SBOM and its completeness state |
| `ai_bom` | the distinct AI/ML-BOM |
| `ci_taint` | CI workflow security + agentic-injection taint posture |
| `ai_closure` | composite AI release closure + SP0011 status |
| `dod` | obligations and Definition-of-Done closure |
| `defeaters` | open defeaters (none for RC-SP0009) |
| `qualify` | the five-conjunct qualification verdict + unknown budget |
| `attest` | the release proof envelope + twin digest |
| `validate` | whole-twin validation (**exit code carries the verdict**) |
| `dossier` | a consolidated slice of the twin for review |

---

## Example invocations

Identity and repository reality:

```
python -m tools.release roadmap_identity
python -m tools.release archaeology
```

Classify a set of changed paths (no `--from`; classification is computed directly):

```
python -m tools.release classify tools/release/gates.py docs/release/FINALIS_RELEASE_README.md
```

Walk the reference candidate against the committed twin:

```
python -m tools.release create_candidate --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release plan_gates       --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release dod              --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release qualify          --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release attest           --from docs/release/FINALIS_RELEASE_TWIN.json
```

Inspect the honest edges — the flake, the SBOM completeness, the AI closure, the
transparency receipt:

```
python -m tools.release flakes            --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release sbom              --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release ai_closure        --from docs/release/FINALIS_RELEASE_TWIN.json
python -m tools.release verify_transparency --from docs/release/FINALIS_RELEASE_TWIN.json
```

Emit deterministic canonical JSON (for hashing/diffing) with `--json` (global flag,
before the command):

```
python -m tools.release --json dossier --from docs/release/FINALIS_RELEASE_TWIN.json
```

---

## `validate` and its exit-code semantics

`validate` re-derives the twin from source and checks the whole proof, then **exits with
a code that carries the verdict**:

```
python -m tools.release --root . validate
echo $?     # 0 = valid, 1 = invalid
```

| Exit code | Meaning |
|---|---|
| `0` | **valid** — the report has **zero P0 and zero P1** findings |
| `1` | **invalid** — at least one P0 or P1 finding |

What `validate` checks:

- **Required keys** present in the twin (missing keys are P1).
- **Determinism (P0):** a freshly built twin's `twin_digest` must byte-match the
  committed twin. A committed twin that does not match a fresh build is **stale or
  non-deterministic** and fails P0.
- **Envelope** structural allowlist validation.
- **Boundary:** the fail-closed import allowlist / AST frontier check (the kernel must
  not import product code).
- **Bounded invariant models:** genome sensitivity, lattice fail-closed, ledger
  append-only, quorum diversity.

**Honest UNKNOWNs do not fail validation.** P2 findings — such as the reference twin's
single P2, the `ENVIRONMENT_INSTABILITY` browser flake and the `INCOMPLETE_THIRD_PARTY`
SBOM — are recorded and reported but **do not** flip the exit code. Only P0/P1 do. A
correct twin with honest unknowns exits `0`; a broken or stale one exits `1`.

For RC-SP0009 the report is **valid** (P0=0 / P1=0 / P2=1), so `validate` exits `0`.

---

## Notes on scope

- Every command prints JSON to stdout and nothing else — no files written, no network,
  no secrets.
- `qualify` reaching `qualifiable: true` advances the candidate no further than
  `READY_FOR_LATER_PROMOTION`, a **non-production** assurance state. It grants **no
  deployment authority**.
- The AI closure honestly reports **no real AI provider** (all mocks) and the SP0011
  status is `PENDING_SP0011` — **no evaluation evidence exists and none is fabricated.**
