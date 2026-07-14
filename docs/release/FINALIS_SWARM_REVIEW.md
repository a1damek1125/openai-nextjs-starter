# SP0009 — Release Assurance Constitution: Swarm Review

Honest build-and-review record for SP0009. Documents how the release-assurance
kernel was built, what independent swarm agents found, every confirmed
false-negative escape and its fix, and the limitations recorded rather than
hidden.

## 1. What was built

A deterministic, repository-local **Release Assurance control system** under
`tools/release/` (31 modules, 26-command CLI) plus materialized artifacts and
schemas under `docs/release/`. It decides whether a change is sufficiently
defined, verified, evidenced and protected to advance to the next **non-
production** lifecycle state — and it materializes the REAL candidate for the
SP0009 change itself (`RC-SP0009`), not just schemas or examples.

Materialized twin facts (`docs/release/FINALIS_RELEASE_TWIN.json`):

| Property | Value |
|---|---|
| Candidate | `RC-SP0009` → `READY_FOR_LATER_PROMOTION` |
| Qualification conjuncts | all 5 True (hard gates PASS, non-waivable obligations closed, zero hard-scope unknowns, artifact closure COMPLETE, no blocking defeater) |
| Findings | **P0 = 0, P1 = 0, P2 = 1** |
| The one P2 | the pre-existing browser E2E flake, classified `ENVIRONMENT_INSTABILITY` |
| Determinism | twin rebuilds byte-identical |
| Bounded model checks | all HOLD |

The kernel binds the repository's REAL state: the SP0008 Contract Genome root,
the real dependency-lock hash, and the **absent** CI-workflow hash (this repo
has no CI, no lockfile, no build backend — each absence is hashed explicitly
into the candidate genome, never silently equal to presence).

## 2. Swarm process

- **SWARM-A (release archaeology)** mapped the actual release surface: NO CI
  workflows, NO lockfile, NO build backend, `dependencies=[]` in
  `pyproject.toml`; the "release train" today is the 4-shard pytest suite with
  `test_browser_e2e.py` excluded; the one live flake is
  `test_evidence_prompt_injection_flow_in_browser` (module-scoped shared
  server+page, fixed port 8765, stale-text waits, passes in isolation); no real
  AI provider exists (all mocks). These facts shaped every honest default.
- **SWARM-DOCS** wrote the constitution, roadmap-identity report, research
  register and README, each verified against the code and the twin (it caught
  and fixed a CLI flag-ordering error in the README).
- **SWARM-O (red-team)** found **8 real false-negative escapes** (4 P1, 4 P2).
  All fixed and regression-locked (§3).
- **SWARM-P (independent verifier)** re-checked every material claim (§4).

## 3. Confirmed false-negative escapes and fixes

Each is pinned by a lock in `tests/test_release_mutation.py`.

| # | Sev | Escape | Fix | Lock |
|---|---|---|---|---|
| 1 | P1 | `hard_verdict` accepted a WAIVED result on a hard gate on the strength of `status=="ACTIVE"` alone — a stale or cross-candidate waiver passed. | `_valid_waiver_for` now requires candidate-genome binding + non-expired + ACTIVE, validated with `now`; missing context fails closed. | R1 |
| 2 | P1 | `qualify()`'s `all_non_waivable_obligations_closed` conjunct used `not open_hard`, ignoring the `invalid_waivers` bucket — an illegally-waived non-waivable obligation qualified. | conjunct now also requires `not invalid_waivers`. | R2 |
| 3 | P1 | The release proof envelope substituted the truthy sentinel `"ABSENT"` for an omitted hash, and the missing-field check was a truthiness test — an omitted failure ledger passed. | reject `== "ABSENT"` for every required hash field as P0. | R3, M31 |
| 4 | P1 | `check_no_external_effect` exempted `os` and filtered os calls by a **denylist** — `os.execlp`/`rename`/`chmod`/`putenv`/… slipped through. | removed the `os` exemption entirely (nothing imports os); a pure fail-closed import allowlist, no call denylist. | R4 |
| 5 | P2 | `verify_receipt` trusted the checkpoint embedded IN the receipt — a size-1 self-asserted forgery verified clean. | `verify_receipt` now takes an independently pinned checkpoint the receipt must match; empty proofs without a pinned checkpoint are rejected. | supply-chain suite |
| 6 | P2 | `validate_root` never checked lifecycle `status` — a `SUPERSEDED`/`ROTATING` root still authorized signers. | require `status == "ACTIVE"` (allowlist). | R6 |
| 7 | P2 | Workflow overprivilege used a `>3`-write count threshold and untrusted context used a denylist — a single `id-token: write` or an unlisted `github.event.*` field slipped past. | any write scope outside a low-risk allowlist is flagged; any `github.event.*`/`head_ref` interpolation not on a trusted allowlist is flagged. | R7 |
| 8 | P2 | `resume()` set status directly with no "must be PAUSED" guard — an illegal jump to `VERIFYING` (and onward to `QUALIFIED`). | `resume` now requires a `PAUSED` candidate with a `pause_context`. | R8 |

**Classes with no escape found** (independently confirmed): rerun laundering
(append-only ledgers, `anti_laundering_findings` P0), missing gate = PASS
(→ blocks), artifact substitution / same-bytes, wrong-subject SBOM, quorum
duplicate/domain collapse, VEX auto-waive, AI closure identity, flag authority
widening (strict `is True` + guards scan), single-rerun flake confirmation,
non-compensatory lattice / UNKNOWN-blocks, hermeticity fail-closed, and
determinism (no time/random in hashed outputs).

## 4. Honest limitations (recorded, not hidden)

- **No production readiness.** SP0009 creates repository evidence only; the
  product remains `NOT_PRODUCTION_READY`, production qualification stays
  `BLOCKED_PENDING_SP0011`. The release proof envelope creates **no** deployment
  authority.
- **No CI / lockfile / build backend exist.** The candidate genome binds these
  as explicit `ABSENT` hashes. Supply-chain, reproducibility and diverse-builder
  gates operate on the honest source-tree artifact and on fixtures for future
  workflows; no SLSA level is claimed, no reproducibility asserted as a standing
  property.
- **No real AI provider.** All adapters are mocks; the AI Release Closure and
  AI/ML-BOM record that honestly. The SP0011 evaluation interface is a
  `PENDING_SP0011` placeholder that cannot carry evidence.
- **The browser E2E file is environment-sensitive and unresolved by SP0009.**
  It drives live Chromium against a module-scoped subprocess server on fixed
  port 8765 with 15s selector-wait timeouts, and is excluded from the
  deterministic release suite by established repo convention
  (`--ignore=tests/test_browser_e2e.py`). SP0009's 4-shard full-suite run
  produced exactly ONE failure — `test_evidence_viewer_restricted_in_browser`
  (a `wait_for_selector('#ev-list table')` 15s timeout under live Chromium);
  the previously-documented `test_evidence_prompt_injection_flow_in_browser`
  (`'450 EUR'`) is the same class. Both are classified
  `ENVIRONMENT_INSTABILITY`, reproduced and recorded (not hidden). They are NOT
  attributed to SP0009 (`finalis/` and `test_browser_e2e.py` are byte-untouched,
  zero references to SP0009 tooling), NOT deleted, NOT weakened. The
  **deterministic (browser-excluded) suite is fully green** — SP0009 does not
  claim unconditional full-suite green.

## 5. Change boundary — verified clean

Zero live deployment, zero product migration (frontier stays v27, checked via
AST), zero external effect (fail-closed import allowlist over the package),
never imported by product code (`finalis/` byte-untouched). `boundary.check_
boundary` returns empty on the shipped tree.

## 6. Test status

`tests/test_release_core.py`, `tests/test_release_mutation.py` (32 constitutional
mutants + 8 red-team regression locks), `tests/test_release_supply_chain.py`,
and `tests/test_release_integration.py` all pass. The twin is deterministic and
re-validates against a fresh build.
