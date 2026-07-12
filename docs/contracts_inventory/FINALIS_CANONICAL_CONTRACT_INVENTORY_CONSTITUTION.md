# FINALIS Canonical Contract Surface Inventory Constitution

**Mission:** SP0008 — *FINALIS Canonical Contract Surface Inventory, Repository
Intelligence & Dependency Truth Constitution* (Program Twin canonical name:
*"Existing API/UI/Data Contract Inventory"*).

**Implementation:** `tools/contracts_inventory/` (deterministic, stdlib-only
governance tooling). **Materialized artifact:**
`docs/contracts_inventory/FINALIS_CONTRACT_INVENTORY.json`.

This document is the constitution for the inventory: what it is, the principles
it holds itself to, and the honest limits it declares. Every claim below is
traceable to a module in `tools/contracts_inventory/`.

---

## 1. Purpose

The inventory is a **deterministic, evidence-grounded, machine-queryable map of
the contract surfaces that are ACTUALLY implemented in the repository** — not the
surfaces a schema, a design doc, or a mock says *should* exist, but the ones the
source tree literally contains, each cited to a real file and line.

It exists to give the program a single, reproducible source of truth about its
own contract surface: what routes are exposed, what tables and migrations
persist state, what events are emitted, what proof artifacts are produced, who
owns them, what they can reach, and — crucially — what the tooling does **not**
know about them.

The inventory does not stand up a new registry. It **populates the SP0007
Contract Registry** (`docs/compatibility/FINALIS_CONTRACT_DESCRIPTORS.json`) by
resolving every discovered surface against that registry's descriptors. Standing
up a competing registry is itself a detectable failure
(`PARALLEL_REGISTRY_DETECTED`).

### Materialized scale (from the committed run)

| Quantity | Value |
|---|---|
| Observations (raw detector sightings) | 1296 |
| Canonical surfaces (after union) | 1295 |
| Evidence claims | 3616 |
| Grounded behavioral witnesses | 149 |
| Findings | P0 = 0, P1 = 0, P2 = 4890 |
| Residual unseen-surface estimate | **NOT ESTIMABLE** (see §11) |
| Determinism | byte-reproducible (fresh build byte-matches committed) |

Surface-kind breakdown of the 1295 canonical surfaces: 423 `HTTP_ROUTE`,
429 `PROOF_ARTIFACT`, 174 `AUDIT_EVENT`, 107 `DB_TABLE`, 82 `STATE_TRANSITION`,
35 `RUN_LEDGER_EVENT`, 27 `DB_MIGRATION` (frontier v27), 10 `CONFIG_KEY`,
8 `STATE_MACHINE`.

Identity resolution against SP0007: 610 `MATCHED_EXISTING` (under 5 registry
parents — `CT-HTTP-CASES` 420, `CT-DB-SCHEMA` 134, `CT-EVENT-RUN-LEDGER` 35,
`CT-WF-CASE-FSM` 18, `CT-PROOF-RUN-EVENT` 3), 675 `NEW_SURFACE`, and
10 `DUPLICATE_CANDIDATE`.

---

## 2. The "real records, not schemas" principle

This is the principle the whole mission turns on. A detector may only report a
surface it can **literally cite** in source: every raw observation carries
`evidence.path` + `evidence.line` pointing at the exact location it was read from
(`discover.Observation`). A detector never invents a surface it cannot ground,
and never reports a schema, an example payload, or a mock as if it were an
implemented surface.

The consequence is that the inventory is *evidence-first*. An assertion with no
grounding location is an `EVIDENCE_UNGROUNDED` finding (P1) and cannot be
admitted. This principle propagates upward: evidence claims are grounded
(`evidence.py`), behavioral witnesses are grounded (`witnesses.py`), and an
LLM may only *propose* candidates — an ungrounded candidate is rejected, never
merged.

---

## 3. The declared universe: 15 surface kinds

`model.SURFACE_KINDS` fixes the closed alphabet of contract-surface kinds. Every
materialized record is classified into exactly one:

`HTTP_ROUTE`, `REQUEST_SHAPE`, `RESPONSE_SHAPE`, `AUDIT_EVENT`,
`RUN_LEDGER_EVENT`, `DB_TABLE`, `DB_MIGRATION`, `STATE_MACHINE`,
`STATE_TRANSITION`, `PROOF_ARTIFACT`, `UI_SURFACE`, `PROVIDER_BINDING`,
`CONFIG_KEY`, `CLI_COMMAND`, `BACKGROUND_JOB`.

This 15-kind union is the **declared universe** against which negative-space
verification and residual reasoning operate. In the committed run, 9 of the 15
kinds are materialized; the remaining kinds are declared but had no grounded
sightings under the current detector fleet — an honest gap the tooling records
rather than hides.

A subset are **effect-bearing kinds** (`model.EFFECT_BEARING_KINDS`) — the
surfaces that *are* an external or irreversible effect and therefore act as the
reachability sinks: `AUDIT_EVENT`, `RUN_LEDGER_EVENT`, `DB_TABLE`,
`DB_MIGRATION`, `PROVIDER_BINDING`, `BACKGROUND_JOB`. `HTTP_ROUTE` is
deliberately **excluded** — a route is the ingress *source* that reaches effects
through its handler, not an effect in itself.

---

## 4. The detector fleet, multi-detector union, and declared blind spots

### The fleet

`discover.py` implements ten deterministic detectors, each a reader over one
specific code pattern (`detectors.CAPABILITY` records each detector's method and
the kinds it can materialize):

| Detector | Method | Materializes |
|---|---|---|
| `http_routes` | AST decorators + `add_api_route` calls | `HTTP_ROUTE` |
| `db_migrations` | AST `MIGRATIONS` list + `CREATE TABLE` regex | `DB_MIGRATION`, `DB_TABLE` |
| `run_ledger_events` | AST `EVENT_SCHEMA` dict keys | `RUN_LEDGER_EVENT` |
| `audit_events` | AST `event_type=` literal keyword args | `AUDIT_EVENT` |
| `state_machines` | AST `Enum` subclasses + members | `STATE_MACHINE`, `STATE_TRANSITION` |
| `proof_artifacts` | AST function names matching proof/hash/merkle | `PROOF_ARTIFACT` |
| `proof_versions` | AST `finalis-<slug>-v<N>` string constants | `PROOF_ARTIFACT` |
| `config_keys` | AST `os.environ` / `os.getenv` access | `CONFIG_KEY` |
| `declared_config` | text scan of `.env.example` | `CONFIG_KEY` |
| `cli_commands` | AST `add_parser(...)` | `CLI_COMMAND` |

Detector order is fixed and `discover_all` sorts observations canonically, so
repeated runs are bit-stable.

### Why multi-detector union

Detectors are unioned before reconciliation (`observations_by_surface`,
`normalize.reconcile`). Two detectors that see the same surface *corroborate* it
— but only if they are genuinely independent. `detectors.diversity` grades any
pair:

- `DIVERSITY_REAL` — different methods, disjoint blind spots (real corroboration);
- `DIVERSITY_PARTIAL` — different methods but shared kinds and both under-report;
- `DIVERSITY_COSMETIC` — the *same* method; their agreement is **not** new
  evidence.

A surface whose only agreement is common-mode is flagged `DETECTOR_COMMON_MODE`
(P2). This distinction protects the residual estimator and the confidence story
from being fooled by correlated instruments.

### Declared blind spots

A blind spot is a **first-class inventory output**, never a silent omission
(`discover.BLIND_SPOTS`). The fleet declares, for example, that:

- `http_routes` is blind to `add_api_route` paths built by string concatenation
  (only literal `arg0` paths are recovered) — **under-reports**;
- `state_machines` is blind to transitions synthesized at runtime (universal
  edges, set-unions, dict-comprehension splats) — **under-reports**;
- `audit_events` is blind to `event_type` values built from f-strings/variables
  — **under-reports**;
- `config_keys` is blind to keys read via a settings object rather than a direct
  `os.environ` literal — **under-reports**;
- `cli_commands` notes that the product package `finalis/` exposes no argparse
  CLI (only governance tooling under `tools/` does) — does not under-report.

Recording a blind spot bounds the negative space and feeds the completeness
argument. The inventory's honesty about what it *cannot* see is the reason its
statements about what it *can* see are trustworthy.

---

## 5. Identity resolution and the no-parallel-registry rule

`normalize.py` reconciles the union of observations into `CanonicalSurface`
records and resolves each against the SP0007 registry. A surface's opaque
identity (`canon.surface_id`) is derived only from `(kind, canonical_name)` —
independent of display label or file location, so identity is stable across
cosmetic churn.

Resolution outcomes (`model.IDENTITY_OUTCOMES`): a surface whose contract-kind
matches a descriptor and whose evidence path lies within that descriptor's
declared `source_paths` is `MATCHED_EXISTING` under that `CT-*` parent. Multiple
matching descriptors yield `AMBIGUOUS_IDENTITY` — the tooling **never guesses**.
A surface the registry did not name is `NEW_SURFACE`. Surfaces sharing a
structural fingerprint are surfaced as `DUPLICATE_CANDIDATE`/`ALIAS_CANDIDATE` —
recorded for review, **never silently merged**.

The no-parallel-registry rule is enforced: the inventory references SP0007's
`CT-*` ids, and `parallel_registry_paths` flags any surface that appears to mint
its own `CT-*` id (`PARALLEL_REGISTRY_DETECTED`).

---

## 6. Bitemporal, provenance-carrying evidence

Every assertion is an **evidence claim** (`evidence.Claim`) that is grounded,
bitemporal, and provenance-linked:

- **Grounded** — cites a real `source.path` + `source.line`.
- **Bitemporal** — carries `valid_from`/`valid_to` (when the fact *held*) and
  `observed_at`/`superseded_at` (when we *recorded/retracted* it). Symbols are
  deterministic (`REPO_EPOCH`, `INVENTORY_RUN`, `OPEN`) — no wall-clock `now()`,
  so runs stay reproducible. Bitemporality lets the inventory answer "what did we
  believe about this contract on date D, and what was true then" without
  rewriting history.
- **Provenance-linked** — projected into a W3C PROV graph (`prov_projection`):
  each claim is an ENTITY `WAS_GENERATED_BY` a detector ACTIVITY, `USED` a source
  ENTITY, `WAS_ATTRIBUTED_TO` a detector AGENT, and `WAS_DERIVED_FROM` the source.

**Contradictions are preserved, never averaged.** Two claims with the same
subject+predicate but different values produce `CONTRADICTION_PRESERVED` (P2):
both values are kept and the disagreement is flagged. The inventory records
disagreement as a fact, it does not paper over it.

---

## 7. Criticality as a VECTOR (hard flags conjunctive, UNKNOWN never safe)

Criticality is **eight independent dimensions** (`model.CRITICALITY_DIMS`), never
a scalar score:

`authority`, `tenant`, `data`, `externality`, `irreversibility`, `centrality`,
`proof`, `historical_obligation`.

Six of these are **hard, non-compensatory dimensions**
(`HARD_CRITICALITY_DIMS`): `authority`, `tenant`, `externality`,
`irreversibility`, `proof`, `historical_obligation`. The verdict
(`criticality.verdict`) is **conjunctive**:

- any hard flag = `YES` → **CRITICAL**, regardless of every other dimension;
- any hard flag = `UNKNOWN` (none `YES`) → **ELEVATED** — must be resolved, never
  assumed safe;
- otherwise → **STANDARD**.

Dimensions are **never averaged into a score** — a single hard flag cannot be
diluted by others. Each dimension value is `YES` / `NO` / `UNKNOWN`, and
**UNKNOWN is a first-class result**. An unresolved hard dimension emits
`HARD_FLAG_UNVERIFIED` (P2) — it is never silently read as "safe". This is the
fail-closed discipline in miniature: the tooling would rather say "I do not know
whether this route touches authority" than assume it does not.

The `model_criticality_conjunctive` bounded model exhaustively proves this holds
for each hard dimension in isolation.

---

## 8. Effect reachability, dominators, and minimal cut sets

`chains.py` derives a **real** dependency graph from source: each HTTP route's
handler body is scanned for the table names and event literals it references,
and each becomes an outgoing edge. It then answers three questions
deterministically:

- **Effect reachability** — which effect sinks a surface can reach, tagged
  `EXACT` when the surface's outgoing edges are fully resolved (or it is itself a
  sink). A route with no statically resolvable effect edges is `UNKNOWN`, and
  emits `EFFECT_REACHABILITY_UNKNOWN` (P2): it is **never** silently reported as
  "reaches no effect" (fail-closed).
- **Dominators** — the classic iterative dominator computation from a synthetic
  root: which surface, if removed, cuts *all* paths from a route to an effect (a
  single point of control).
- **Minimal cut sets** — the smallest sets of intermediate surfaces whose removal
  severs every source→sink path, bounded and tagged
  `EXACT` / `BOUNDED` / `LIMIT_REACHED` (`model.CUT_SET_EXACTNESS`). A truncated
  search is reported as `LIMIT_REACHED` with a `CUT_SET_LIMIT_REACHED` finding —
  a lower bound, **never mistaken for a proven-complete set**.

---

## 9. Ownership and producer/consumer certainty

`ownership.py` infers ownership from the repository's real signal: the capability
tag (`CORE|TOOL|EMP-<X><N>`) on the first line of the owning module's docstring,
with a deterministic path-convention fallback. Unresolvable ownership is
`OWNERSHIP_UNRESOLVED` (P2), never guessed.

Consumers are typed by certainty (`model.CONSUMER_CERTAINTY`):
`STATIC_CONFIRMED`, `TEST_CONFIRMED`, `DECLARED`, `HISTORICALLY_EVIDENCED`,
`TRANSITIVE_INFERRED`, `UNKNOWN`. The load-bearing rule: **"no consumer found" is
UNKNOWN, never zero** (`DARK_CONSUMER`, P2). A surface with no resolvable
consumer is a dark-consumer *risk*, not a proven-unused surface. An effect-bearing
event with no consumer is an `ORPHAN_PRODUCER` candidate — surfaced for review,
**not deleted**.

---

## 10. Behavioral witnesses (source-grounded, LLM candidate-only)

A witness (`witnesses.py`) is a concrete behavioral fact grounded in source —
e.g. a route's `raise HTTPException(status, detail)` is a grounded
`NEGATIVE`/`AUTHORITY` witness (401/403 → `AUTHORITY`). Witness kinds:
`POSITIVE`, `NEGATIVE`, `FAILURE`, `METAMORPHIC`, `TENANT`, `AUTHORITY`;
outcomes: `CONFIRMED`, `REFUTED`, `UNKNOWN_OUTCOME`.

**An LLM may only PROPOSE witness candidates.** A candidate with no source
grounding is `WITNESS_UNGROUNDED` (P1) and cannot be admitted. A witness whose
outcome cannot be determined is `UNKNOWN_OUTCOME` — **never silently assumed to
pass**. Surfaces with zero witnesses have that recorded (NONE is a fact, not a
gap hidden). The committed run holds 149 grounded witnesses.

---

## 11. The honest residual story: why it is NOT ESTIMABLE

`residual.py` implements Chao1 capture-recapture: independent detectors are
"capture occasions", a surface seen by many detectors is a "recapture", a surface
seen by exactly one is a "singleton", and the estimator projects unseen richness
from singleton (Q1) and doubleton (Q2) counts:

```
S_hat = S_obs + Q1*(Q1-1) / (2*(Q2+1))
```

**This tooling's detector fleet is kind-partitioned**: each surface kind is,
almost entirely, seen by exactly one detector capable of seeing it. There is
therefore no genuine recapture — a surface seen by one detector was not a
statistical singleton, it was simply seen by the only instrument that could see
it. Chao1's independence assumption is violated.

The tooling **detects this and refuses to emit a number**. In the committed run:
S_obs = 1295, recaptured surfaces = 1, effective recapture fraction ≈ **0.08%**
(well below the 5% floor), Q1 = 1294, Q2 = 1. The estimate is reported as:

> **NOT ESTIMABLE**: detector fleet is kind-partitioned; the residual is
> UNKNOWN, not zero.

This is the fail-closed philosophy applied to statistics: rather than print a
spuriously precise "0 unseen surfaces", the tooling says the honest thing.
**Completeness is therefore argued from the declared universe + blind-spot
registry** (`negative_space.py`), not from capture-recapture. Negative-space
verification computes an independent lower-bound count per kind by a *second*
method (raw text tallies of route decorators, `CREATE TABLE` statements,
`EVENT_SCHEMA` keys) and flags any shortfall (`NEGATIVE_SPACE_UNVERIFIED`, P1)
where detectors found fewer surfaces than the independent floor. A saturation
curve records whether discovery was still climbing at the last detector.

---

## 12. Value-of-Information probe planning

When the inventory has unknowns, it does not stop — it **plans the next probe**
(`probes.py`). Each unknown (UNKNOWN effect reachability, UNKNOWN/dark consumer,
unresolved hard criticality flag, ambiguous/duplicate identity) becomes a ranked
probe: `STATIC_TRACE`, `CONSUMER_SEARCH`, `CRITICALITY_REVIEW`,
`IDENTITY_ADJUDICATION`, or `WITNESS_ELICITATION`, scored by a Value-of-Information
weight (criticality of the affected surface). The plan is a deterministic,
ranked worklist a human or a future tool can act on — and **it never executes
anything against the running product** (`executes_against_product: false`).

---

## 13. Advisory agent-readiness (grants NO authority)

`readiness.py` answers, per surface, "does the inventory know *enough* for an
autonomous agent to act safely?" — purely as a **diagnostic**. A `READY` /
`NO_KNOWN_BLOCKER` verdict **grants no authority**; authority lives in the
product's own gates (RBAC, approval, authority boundary), and `grants_authority`
is hard-wired `False`. Readiness is fail-closed: any hard blocker (unknown tenant
scope, unknown authority, unknown external effect, unknown idempotency, unknown
approval requirement, or an `UNKNOWN_OUTCOME` witness) makes the surface
`NOT_READY` (`AGENT_READINESS_BLOCKED`, P2). Absence of a blocker is "no known
blocker", never a positive grant.

---

## 14. The Merkle Contract Genome

`genome.py` seals the inventory into a **per-class Merkle root** over the
*material* fingerprints of every surface of a kind, plus a **global root** over
the ordered class roots. The genome property: any material change to any surface
(a new route, a changed table, a retired event) moves that class's root and
therefore the global root, while a purely cosmetic change (renamed display label,
a comment) does not — because material fingerprints strip volatile presentation
(`canon.strip_volatile`, `VOLATILE_KEYS`).

A recomputed genome that diverges from the recorded one is a P0
`GENOME_ROOT_MISMATCH` (material drift or corruption). The committed global root
is `7269f08cd7d53679cae6ce3b134a00d6dd6146fde0c60e712a065a711be377b1`; the
`model_material_vs_cosmetic` bounded model proves the move-on-material /
still-on-cosmetic property.

---

## 15. Proof envelopes (structural allowlist, non-authoritative)

`envelope.py` seals a verifiable run summary: genome roots, surface/finding
counts, detector names, and a content digest — enough to pin the inventory and
detect drift, with **nothing that grants authority**. The validator uses a
**structural allowlist** (`ENVELOPE_KEYS`): only known structural keys are
permitted, and any extra key — especially an authority-flavoured synonym like
`mandate`/`ratifies`/`empowers` — is rejected as `PROOF_ENVELOPE_MISMATCH` (P0).
The envelope must declare `non_authoritative: True`, or it is rejected. Allowlist
+ fail-closed, never a blacklist.

---

## 16. The change boundary

The mission's non-negotiable boundary (`closure.py`, enforced as P0
`BOUNDARY_VIOLATION`):

- **Zero product-runtime change** — governance/analysis tooling only.
- **Zero product DB migration** — the frontier stays **v27**
  (`check_frontier_unchanged`).
- **Zero external effect** — no socket/network/subprocess; a static allowlist
  forbids `socket`, `urlopen`, `Popen`, `system`, `connect`, `request`,
  `urlretrieve` (`check_no_external_effect`).
- **Never imported by product code** — no file under `finalis/` may import
  `tools.contracts_inventory` (`check_no_product_import`).

These are checked against the actual tree on every build and validate, so a
violation surfaces as a P0 rather than shipping silently.

---

## 17. Fail-closed philosophy: UNKNOWN is a result, never permission to omit

The single thread running through every module: **UNKNOWN is a first-class,
recorded result — never a license to omit, and never silently read as safe.**

- An unresolved hard criticality flag is `ELEVATED`, not `STANDARD`.
- A route with no resolvable effect edges is `UNKNOWN`, not "no effect".
- A surface with no found consumer is a dark-consumer risk, not "unused".
- A witness with no determinable outcome is `UNKNOWN_OUTCOME`, not "pass".
- A residual that cannot be estimated is `NOT ESTIMABLE`, not "0 unseen".
- A blind spot is a declared output, not a silent gap.

The finding severity model (`model.Report`) makes this liveable: honest UNKNOWNs
are advisory **P2** findings — the committed run has 4890 of them — and do
**not** invalidate the inventory. Only true correctness violations (P0) or unmet
required properties (P1) do. The committed run has **zero P0 and zero P1**: the
inventory is valid *and* honest about everything it does not know.
