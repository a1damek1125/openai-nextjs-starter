# FINALIS Contract Inventory — Research Register (SP0008)

The methods SP0008 borrows from the literature, exactly how each is applied in
`tools/contracts_inventory/`, and — for every one — the honesty caveat that
governs its use. The theme is constant: each technique is used for what it can
soundly deliver, and its limits are declared, never hidden.

---

## 1. Capture-recapture / the Chao1 richness estimator

**Concept.** Capture-recapture estimates the size of a population — including the
part never observed — from repeated independent sampling occasions. The Chao1
non-parametric lower bound uses the counts of species seen exactly once
(singletons, Q1) and exactly twice (doubletons, Q2):
`S_hat = S_obs + Q1*(Q1-1) / (2*(Q2+1))`. Its core assumption is that sampling
occasions are **independent** and that a rarely-seen item is genuinely rare, not
merely visible to only one instrument.

**How it is applied here** (`residual.py`). Detectors are treated as capture
occasions; a surface seen by ≥2 distinct detectors is a "recapture", a surface
seen by one is a "singleton". `chao1()` computes S_obs, recapture fraction, Q1,
Q2, and — *only when recaptures actually occur* — the residual estimate.

**Honesty caveat (the load-bearing one).** SP0008's detector fleet is
**kind-partitioned**: each surface kind is seen, almost exclusively, by the one
detector capable of seeing it. There is therefore essentially no recapture, so a
"singleton" here is not a statistically rare surface — it was seen by the only
instrument that could see it, violating Chao1's independence assumption. The
tooling enforces a `MIN_RECAPTURE_FRACTION` floor of 5%; below it the estimator
is degenerate. In the committed run the effective recapture fraction is ≈ 0.08%
(1 recapture in 1295 surfaces; Q1 = 1294, Q2 = 1), so the residual is reported as
**NOT ESTIMABLE — the residual is UNKNOWN, not zero**. Completeness is instead
argued from the declared universe and blind-spot registry (see §2 and the
constitution §11). This is the register's clearest example of a method used
honestly: the code prefers to say "not estimable" over printing a spurious "0".

---

## 2. Negative-space verification (declared-universe counting)

**Concept.** Open-world completeness cannot be proven, but coverage *can* be
verified against a **declared universe**: an independent lower-bound count of what
should exist, produced by a method that does not share the primary detectors'
logic. The gap between the declaration and what was materialized is the
"negative space".

**How it is applied here** (`negative_space.py`). `declared_universe()` computes
per-kind floors by a *second, cheap* method — raw regex tallies of `@app.<method>`
decorators, distinct `CREATE TABLE` names, and `EVENT_SCHEMA` keys — distinct from
the AST detectors. A detector materialization below the independent floor is a
`NEGATIVE_SPACE_UNVERIFIED` finding (P1): surfaces the fleet should have caught
but did not.

**Honesty caveat.** This proves coverage only *relative to the declared floor*,
and only for the kinds that have a floor. It is a soundness check against
under-detection, not a proof of absolute completeness — which is why it is paired
with, not a substitute for, the blind-spot registry.

---

## 3. Common-mode / detector-diversity analysis

**Concept.** In reliability engineering, redundant instruments that share a
failure mode (common-mode) provide far less assurance than their number suggests:
if two sensors are blind in the same way, their agreement is not independent
corroboration.

**How it is applied here** (`detectors.py`). `diversity(a, b)` grades every
detector pair from the capability matrix and blind-spot registry:
`DIVERSITY_REAL` (different methods, disjoint blind spots), `DIVERSITY_PARTIAL`
(different methods, shared kinds, both under-report), or `DIVERSITY_COSMETIC`
(same method — agreement is not new evidence). A surface corroborated only by
common-mode agreement is flagged `DETECTOR_COMMON_MODE` (P2), and
`global_diversity_ok()` gates whether the fleet is diverse enough for
capture-recapture to even be meaningful.

**Honesty caveat.** Diversity is *graded, never assumed*. Two detectors agreeing
is only counted as corroboration when they are genuinely independent; otherwise
the residual story and confidence claims explicitly discount the agreement.

---

## 4. Dominator analysis and minimal cut sets

**Concept.** In a control-flow / dependency graph, a node *d* **dominates** node
*n* if every path from the entry to *n* passes through *d* — a single point of
control. A **minimal cut set** is a smallest set of nodes whose removal severs
every path between a source and a sink — the minimal way to break a reachability
relation.

**How it is applied here** (`chains.py`). Over the source-derived
route→table/event dependency graph: `dominators()` runs the classic iterative
data-flow computation from a synthetic root to find surfaces that, if removed,
cut all route→effect paths; `minimal_cut_sets()` enumerates smallest severing
sets between route sources and effect sinks.

**Honesty caveat.** Cut-set enumeration is **bounded** (`CUT_SET_LIMIT` = 200,
`MAX_CUT_SIZE` = 3) and every result is tagged `EXACT`, `BOUNDED`, or
`LIMIT_REACHED`. A truncated search emits `CUT_SET_LIMIT_REACHED` and is reported
as a lower bound — a bounded search is **never presented as a complete one**.
Likewise reachability is fail-closed: a route whose effect edges cannot be
statically resolved is `UNKNOWN`, not "reaches no effect".

---

## 5. W3C PROV provenance data model

**Concept.** The W3C PROV standard models provenance as a graph of three node
kinds — **Entity**, **Activity**, **Agent** — connected by relations such as
`wasGeneratedBy`, `used`, `wasAttributedTo`, `wasDerivedFrom`, and
`wasInformedBy`. It answers "where did this fact come from, and by what process".

**How it is applied here** (`evidence.py`, `model.py`). Each evidence claim is
projected into a PROV graph: the claim is an ENTITY that `WAS_GENERATED_BY` a
detector ACTIVITY, which `USED` the source file ENTITY; the claim `WAS_ATTRIBUTED_TO`
the detector AGENT and `WAS_DERIVED_FROM` the source. Edge kinds are drawn from a
closed set (`PROV_EDGE_KINDS`) and validated: an edge with an unknown kind or an
undeclared endpoint is `PROVENANCE_BROKEN` (P1).

**Honesty caveat.** The PROV projection records *how the inventory came to
believe a claim* (which detector, from which file) — it is a chain of custody for
the tooling's own assertions, not a claim about the product's runtime behavior.

---

## 6. Bitemporal modeling (valid-time vs transaction-time)

**Concept.** Bitemporal data modeling separates two independent time axes:
**valid time** (when a fact was true in the world) and **transaction time** (when
the system recorded or retracted its belief in that fact). Keeping both lets a
system answer "what did we believe on date D, and what was actually true then"
without destroying history.

**How it is applied here** (`evidence.py`). Every `Claim` carries `valid_from` /
`valid_to` (valid time) and `observed_at` / `superseded_at` (transaction time).
Intervals that close before they open are `BITEMPORAL_INCONSISTENT` (P1).
Contradictory claims are **preserved** (`CONTRADICTION_PRESERVED`, P2): both
values are kept and flagged, never averaged or dropped.

**Honesty caveat.** To stay byte-reproducible the temporal endpoints are
**symbolic and deterministic** (`REPO_EPOCH`, `INVENTORY_RUN`, `OPEN`) — no
wall-clock `now()`. The model gives the inventory the *structure* to reason
bitemporally and to retract without rewriting history; it does not fabricate
precise timestamps it cannot ground.

---

## 7. Merkle trees / Merkle forests

**Concept.** A Merkle tree hashes leaves pairwise up to a single root, so any
change to any leaf changes the root, and the root is a compact, verifiable
fingerprint of the whole set. A Merkle *forest* keeps a root per partition plus a
root over the roots.

**How it is applied here** (`canon.py`, `genome.py`). The Contract Genome is a
Merkle forest: a per-kind class root over the **material** fingerprints of that
kind's surfaces, plus a global root over the ordered class roots. Any material
change (new route, changed table, retired event) moves the relevant class root
and therefore the global root; a recomputed root that diverges from the recorded
one is `GENOME_ROOT_MISMATCH` (P0).

**Honesty caveat.** Material fingerprints **strip volatile presentation**
(`strip_volatile`, `VOLATILE_KEYS`) so a cosmetic change (renamed label, comment)
does *not* move the root — the genome tracks contract substance, not churn. The
`model_material_vs_cosmetic` bounded model proves both directions
(move-on-material, still-on-cosmetic). A structural fingerprint proves shape
equality but is explicitly **not** proof of semantic identity
(`structural_fingerprint` docstring).

---

## 8. Value-of-Information (VoI) for probe planning

**Concept.** Value-of-Information decision theory ranks possible observations by
how much they would reduce uncertainty, weighted by the stakes of the decision
they inform — so scarce investigative effort goes where it resolves the most
consequential unknowns first.

**How it is applied here** (`probes.py`). Each residual unknown (UNKNOWN effect
reachability, dark consumer, unresolved hard criticality flag, ambiguous/duplicate
identity) becomes a probe, scored by a VoI weight tied to the affected surface's
criticality (`CRITICAL` 3.0, `ELEVATED` 2.0, `UNKNOWN` 1.5, `STANDARD` 1.0), and
ranked into a deterministic worklist.

**Honesty caveat.** The output is a **plan, not an action**: every probe carries
`executes_against_product: false`, and the tooling never runs anything against
the live product (INV-0008-52). It hands a human or a future tool a ranked list;
it does not act.

---

## Cross-cutting principle

Across all eight methods the same discipline holds: a technique is applied only
for what it can soundly deliver, its assumptions are checked in code, and where
those assumptions fail the tooling reports **UNKNOWN / NOT ESTIMABLE /
LIMIT_REACHED / BOUNDED** rather than a false precision. Honest uncertainty is
recorded as an advisory (P2) result and never invalidates a correct inventory —
the committed run carries 4890 such advisories alongside zero P0 and zero P1
findings.
