# Finalis AI — Math & Algorithm Verification Audit

> **Auditor's ground truth.** This repository contains **zero application code**. All 12
> scoring formulas audited below exist **only as documentation** in
> `05-algorithms-and-scoring.md` (with escalation rules cross-referenced from
> `13-autonomy-and-safety.md` §2). Nothing has been implemented, nothing has been executed,
> nothing has been tested. Every "Status" line below therefore reads **DOCUMENTED ONLY** —
> this is not boilerplate, it is the single most important fact in this audit. Any claim of
> determinism, auditability, or reproducibility in `05` is currently a claim about prose.
>
> The test vectors in this document are the **canonical fixtures** for the future scoring
> module. They were computed by hand, with arithmetic shown, and are intended to be executed
> verbatim in real tests. Tolerance for all expected values: `±1e-9` unless a vector says
> otherwise.

Global conventions assumed (from `05` §0): sub-signals normalized to `[0,1]` unless stated
otherwise; per-model weights sum to 1.0 except the explicitly additive/unbounded scores;
weights come from `IndustryPlaybook.scoring_weights`; every score persists inputs + weight
version to `AuditEvent`.

**Threshold defaults audit (cross-cutting):**

| Threshold | Default in doc | Status |
|---|---|---|
| `θ_mis` | 0.25 | Defined ✓ |
| `θ_docrisk` | 60 | Defined ✓ |
| `θ_conf` | 0.6 | Defined ✓ |
| `θ_escalate` | 1.5 | Defined ✓ |
| `θ_stuck` | — | **NEVER DEFINED anywhere in the doc set** ✗ |
| `θ_breach` | — | **NEVER DEFINED anywhere in the doc set** ✗ |

---

## 1. LeadScore (§1)

```
LeadScore = 100 · (0.30·V + 0.20·U + 0.15·F + 0.15·C + 0.10·D + 0.10·R)
```

### 1.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 1.2 Definition check
- Weights: `0.30 + 0.20 + 0.15 + 0.15 + 0.10 + 0.10 = 1.00` ✓ — sums to 1.0 as claimed.
- All six variables named and given production recipes ✓.
- Output bounds: implied `[0,100]` if all inputs are in `[0,1]`; **bounds are only as good
  as input clamping, which is not specified as a hard requirement** (only V has an explicit
  `min(1, ·)` clamp).
- Bands (Hot ≥ 70, Warm 45–69, Cool 25–44, Cold < 25) are contiguous and cover `[0,100]` ✓,
  but band edges use integer language against a continuous score — behavior at 44.7 vs 45.0
  must be pinned (round vs. raw comparison).

### 1.3 Defects found
1. **The "deterministic" claim leaks.** `U` (urgency from intake language/keywords) and `D`
   (decision-maker probability from phrasing like "my house" vs. "ask my partner") are
   **LLM-derived inputs**. The scoring *combination* is deterministic; the score is not
   reproducible end-to-end unless the extracted `U`/`D` values themselves are persisted as the
   input vector (the doc does say the input vector is persisted — good — but the boundary must
   be stated explicitly: *reproducibility starts at the input vector, not at the raw
   transcript*). Re-running extraction on the same transcript with an upgraded model can
   change LeadScore. **Flag this determinism boundary in the spec.**
2. **Only V is clamped.** `R` (EWMA) can, under a buggy update or negative-latency clock skew,
   leave `[0,1]`; `C` from embedding similarity can be negative (cosine ∈ [−1,1]). No global
   input clamp is mandated. See adversarial vector A2.
3. **U is a discrete 4-point mapping** (1.0/0.7/0.4/0.1) with no rule for ambiguous or
   in-between intents, and no stated default when urgency is unextractable.
4. **Missing-input semantics undefined.** Cold-start covers `R` (prior 0.5) and `V` (playbook
   median) but says nothing about missing `U`, `C`, or `D`. Silent-zero defaults would
   systematically depress scores for sparse intakes.
5. **`F = 1 − MIS_normalized`** inherits the MIS divide-by-zero defect (§2.3 below).

### 1.4 Required corrections
- Clamp **every** input: `x := min(1, max(0, x))` before weighting; log a `input_out_of_range`
  audit flag when clamping fires.
- Define missing-input defaults per variable in the playbook: `U=0.4`, `D=0.5`, `C` requires a
  value (hard error if service match cannot run), `R=0.5` (already defined), `V=playbook median`.
- State band comparison as raw float: `Hot ⇔ score ≥ 70.0` (no rounding before banding).
- Document the determinism boundary: "deterministic given the persisted input vector."

### 1.5 Test vectors

| # | V | U | F | C | D | R | Expected | Band |
|---|---|---|---|---|---|---|---|---|
| L1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | **100.0** | Hot |
| L2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | **0.0** | Cold |
| L3 | 0.5 | 0.7 | 0.8 | 1.0 | 0.6 | 0.5 | **67.0** | Warm |
| L4 (cold-start) | 0.2 | 0.4 | 0.5 | 1.0 | 0.5 | 0.5 | **46.5** | Warm, `low_confidence` flag |
| L5 (band edge) | 1.0 | 1.0 | 0.0 | 1.0 | 0.5 | 0.0 | **70.0** | Hot (≥ 70 inclusive) |

Arithmetic:
- L3: `0.30·0.5=0.15; 0.20·0.7=0.14; 0.15·0.8=0.12; 0.15·1.0=0.15; 0.10·0.6=0.06;
  0.10·0.5=0.05 → Σ=0.67 → 67.0`.
- L4: `0.06 + 0.08 + 0.075 + 0.15 + 0.05 + 0.05 = 0.465 → 46.5`.
- L5: `0.30 + 0.20 + 0 + 0.15 + 0.05 + 0 = 0.70 → 70.0`.

Adversarial:
- **LA1 (value over cap):** `estimated_value=45 000, value_cap=15 000 → V=min(1, 3.0)=1.0`.
  With U=F=C=D=R=1 → **100.0**. Asserts the clamp, not 300-style blowup.
- **LA2 (negative input):** `R=−0.2`, all others 1.0. Unclamped math gives
  `100·(0.90 + 0.10·(−0.2)) = 100·0.88 = 88.0`. **Required behavior:** clamp `R→0` and return
  `100·0.90 = 90.0` with an `input_out_of_range` audit flag. Test must assert 90.0, not 88.0.
- **LA3 (missing U):** `U=null` → must **not** be treated as 0; expected: playbook default
  `U=0.4` applied + `low_confidence` flag. With V=0.5,F=0.8,C=1.0,D=0.6,R=0.5:
  `0.15+0.08+0.12+0.15+0.06+0.05 = 0.61 → 61.0`.

### 1.6 Recommendation
**Hybrid** — keep the linear weighted form (auditable) but calibrate weights against closed-won
outcomes once ≥ a few hundred labeled cases exist; the doc's own §13 already commits to this.

### 1.7 Acceptance criteria
- All five main vectors + three adversarial vectors pass exactly (±1e-9).
- Property test: for any inputs in `[0,1]⁶`, output ∈ `[0,100]`.
- Out-of-range inputs are clamped and audited, never propagated.
- Score record persists `{V,U,F,C,D,R}`, weight version, and `low_confidence` flag.

---

## 2. Missing Information Score — MIS (§2)

```
MIS = Σ_i w_i · m_i,   m_i ∈ {0,1};   MIS_normalized = MIS / Σ_i w_i
```

### 2.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 2.2 Definition check
- Variables defined ✓. Default HVAC weights given: address 0.9, photo 0.7, preferred time 0.5,
  room dims 0.6, budget 0.3, decision 0.4; `Σw = 3.4`.
- `MIS_normalized ∈ [0,1]` by construction **iff `Σw > 0` and all `w_i ≥ 0`** — neither is
  guaranteed anywhere.
- `θ_mis = 0.25` default given ✓.

### 2.3 Defects found
1. **Divide-by-zero (confirmed).** A playbook with **no required fields** for a case type gives
   `Σw_i = 0` and `MIS_normalized = 0/0`. The doc never handles this. A generic playbook with an
   empty field list is a realistic day-one configuration, not a corner case.
2. **`blocks_quote` flags never assigned.** The default weight table names six fields but does
   not say which carry `blocks_quote=true`. Since a missing `blocks_quote` field bypasses the
   threshold entirely, this is a functional hole, not cosmetics (is a missing address blocking?
   almost certainly — but the doc doesn't say).
3. **No weight validation.** Negative or zero weights are representable in the playbook JSON and
   silently corrupt both MIS and LeadScore's `F = 1 − MIS_normalized`.
4. Partial fields (address present but no postcode) have no semantics — `m_i` is binary only.

### 2.4 Required corrections
- Define: `MIS_normalized := 0 when Σw_i = 0` (nothing required ⇒ nothing missing), and emit a
  `playbook_empty_required_fields` warning.
- Playbook loader must reject `w_i < 0` and warn on `w_i = 0`.
- Ship default `blocks_quote` assignments: address `true`, nameplate photo `true`, others `false`
  (or whatever product decides — but decide).

### 2.5 Test vectors (HVAC default weights, Σw = 3.4)

| # | Missing fields | MIS | MIS_normalized | Trigger (θ=0.25)? |
|---|---|---|---|---|
| M1 | none | 0.0 | **0.0** | No |
| M2 | all six | 3.4 | **1.0** | Yes |
| M3 | photo + budget | 0.7+0.3 = 1.0 | **0.2941176471** | Yes (≥ 0.25) |
| M4 | budget only | 0.3 | **0.0882352941** | No (unless `blocks_quote`) |
| M5 | address only | 0.9 | **0.2647058824** | Yes — and via `blocks_quote` regardless |

Arithmetic: M3 `1.0/3.4 = 0.29411764705…`; M4 `0.3/3.4 = 0.08823529411…`;
M5 `0.9/3.4 = 0.26470588235…`.

Adversarial:
- **MA1 (Σw = 0):** empty required-field list → expected `MIS_normalized = 0`, no trigger,
  warning emitted. Current formula: `0/0` → NaN → **crash or NaN poisoning of LeadScore F**.
- **MA2 (negative weight):** playbook sets `w_budget = −0.5` → loader must reject the playbook;
  the scorer must never see it. Test asserts a validation error, not a score.

### 2.6 Recommendation
**Rule-based**, permanently. This is a checklist completeness measure; ML adds nothing.

### 2.7 Acceptance criteria
- M1–M5 + MA1–MA2 pass; Σw=0 returns 0 with a warning; negative weights rejected at load.
- Property: output ∈ [0,1] for any valid playbook.
- Any missing `blocks_quote=true` field forces the trigger regardless of MIS_normalized.

---

## 3. Next Best Action Utility (§3)

```
Utility(a) = P(close|a) · Value − Cost(a) − Risk(a) − DelayPenalty(a)
Value = estimated_value · LeadScore/100
DelayPenalty(a) = λ · TimeDecay · Value
```

### 3.1 Status
**DOCUMENTED ONLY.** Not implemented. (`do-web-research` additionally gated to Phase 3.)

### 3.2 Definition check
- Terms named and estimation strategy sketched ✓. Policy (`argmax`, tie-break to lower cost/risk,
  autonomy gate) defined ✓.
- **Units are NOT coherent as written.** `P(close|a)·Value` is in **euros**. `Cost(a)` is
  described as "monetary + effort cost … includes token/compute cost" — plausibly euros, but the
  ranking "human-call ≫ AI-call > … > email ≈ 0" is ordinal, not a euro table. `Risk(a)` is
  "chance of a bad outcome × severity" — a probability times a severity of **unspecified unit**.
  If severity is not in euros, subtracting it from a euro expectation is dimensionally
  meaningless: a Risk of 0.9 (probability-like) against a Value term of €196 is numerically
  invisible, and against a €20 job it dominates. **Every term must be denominated in euros.**
- `λ` has no default value or unit (per-day? dimensionless multiplier on TimeDecay?). `TimeDecay`
  here is presumably §4's `1 − e^(−Δt/τ)` but that is never stated.
- No output bound (fine for an argmax utility — but must be documented as unbounded and signed).

### 3.3 Defects found
1. **Unit incoherence (confirmed).** Pin: `Cost(a)` in € (explicit per-channel table:
   e.g. human call €25, AI call €2, WhatsApp/SMS €0.05, email €0.01 — playbook-owned),
   `Risk(a) = P(bad) · Severity_€` with severity in € (e.g. fraction of `Value` at risk),
   `DelayPenalty` already € via `Value`. Without this the argmax is garbage.
2. **`λ` undefined** — no default anywhere. Must ship a default (e.g. `λ = 0.05` per decay unit)
   in the playbook.
3. **§12 wiring defect:** step 3 says `FollowUpPriority` "feeds the follow-up actions'
   `P(close|a)`". FollowUpPriority ranges up to ~100 and can be negative (§4);
   `P(close|a) ∈ [0,1]`. **The mapping is undefined** — feeding one into the other without a
   squashing function is a type error.
4. **All-negative utilities unhandled.** If every action has `Utility < 0` (e.g. `Value = 0`),
   `argmax` still returns the least-bad action and the system acts on a case not worth acting on.
   Policy must define: if `max_a Utility(a) < 0` and `wait` is available → `wait`/park.
5. The `P(close|a)` "rule/heuristic prior table" is referenced but no priors are given — the
   selector cannot be implemented from this doc alone.

### 3.4 Required corrections
- Declare unit: **all four terms in euros**. Ship the per-channel Cost table and the
  `Risk = P(bad) · Severity_€` convention in the playbook.
- Default `λ` (proposed 0.05) with its semantics ("fraction of Value forfeited at full decay").
- Define `P(close|a) = clamp(FollowUpPriority/100, 0, 1) · base_prior(state, a)` or similar —
  any explicit, bounded mapping; pick one and write it down.
- Define the all-negative policy (prefer `wait`; never execute a negative-utility outbound).

### 3.5 Test vectors (all monetary terms in €)

| # | P(close\|a) | est_value | LeadScore | Cost | Risk | λ | TimeDecay | Expected Utility |
|---|---|---|---|---|---|---|---|---|
| N1 (call) | 0.15 | 2000 | 70 | 5 | 2 | 0.01 | 0.5 | **196.0** |
| N2 (wait) | 0.0 | 2000 | 70 | 0 | 0 | 0.02 | 0.8 | **−22.4** |
| N3 (email) | 0.05 | 2000 | 70 | 0.01 | 0.5 | 0.01 | 0.5 | **62.49** |
| N4 (tie-break) | two actions with equal Utility 62.49; Costs 0.01 vs 0.05 | | | | | | | **select the €0.01 action** |

Arithmetic:
- N1: `Value = 2000·70/100 = 1400`. `P·Value = 0.15·1400 = 210`.
  `DelayPenalty = 0.01·0.5·1400 = 7`. `Utility = 210 − 5 − 2 − 7 = 196.0`.
- N2: `0 − 0 − 0 − (0.02·0.8·1400) = −22.4`. (A pure-wait action's utility is all delay.)
- N3: `0.05·1400 = 70; 70 − 0.01 − 0.5 − 7 = 62.49`.

Adversarial:
- **NA1 (Value = 0):** `estimated_value = 0` → every action's utility = `−Cost−Risk−DelayPenalty
  ≤ 0`. Expected: policy selects `wait` (utility 0 − 0 − 0 − 0 = **0.0**, since DelayPenalty
  scales with Value=0), not the least-negative outbound. Asserts the all-negative rule.
- **NA2 (unitless Risk regression guard):** action with `Risk = 0.9` *unitless* against N1's
  numbers would give `210−5−0.9−7 = 197.1`. The fixture must instead carry
  `Risk = P(bad)·Severity_€ = 0.3·€300 = €90` → `210−5−90−7 = 108.0`. Test asserts **108.0** —
  i.e. the € convention — so a unitless-risk implementation fails loudly.

### 3.6 Recommendation
**Hybrid** — rule-based priors and euro-denominated cost/risk tables for MVP, upgrade
`P(close|a)` to a calibrated logistic model per the doc's own plan; keep the utility combiner
deterministic.

### 3.7 Acceptance criteria
- N1–N4, NA1–NA2 pass (±1e-9).
- Every term logged in € with the prior-table version.
- `argmax` never returns an outbound action with negative utility when `wait` exists.
- Autonomy gate test: `a*` above `effective_level` yields `HumanApproval`, never execution.

---

## 4. FollowUpPriority (§4)

```
FollowUpPriority = LeadScore · TimeDecay · IntentSignal − AnnoyanceRisk
TimeDecay = 1 − e^(−Δt/τ)   (gated by quiet hours & minimum interval)
```

### 4.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 4.2 Definition check
- `TimeDecay` has a formula ✓ (τ unspecified — no default).
- `IntentSignal` and `AnnoyanceRisk` are described directionally ("↑ when…") with **no formula,
  no scale, no bounds**.
- **Unit incoherence (confirmed):** the product `LeadScore·TimeDecay·IntentSignal` spans
  `[0,100]` (LeadScore 0–100 times two `[0,1)` multipliers), while `AnnoyanceRisk` has
  **unspecified scale**. If AnnoyanceRisk follows the doc's own global convention
  ("every sub-signal is normalized to [0,1]"), then subtracting a `[0,1]` quantity from a
  `[0,100]` product makes the anti-spam term **numerically irrelevant** — a maximum-annoyance
  1.0 barely dents a Hot lead's 60+ product. The formula's stated purpose (anti-spam) is
  defeated by its own scales.
- No output bound stated; range is actually `(−AR_max, 100)`.
- No trigger threshold: at what priority does a follow-up actually fire? Undefined.

### 4.3 Defects found
1. **Scale mismatch (above)** — the headline defect. Either normalize LeadScore to `/100` inside
   the product (output ∈ `[−1, 1]`) or put AnnoyanceRisk on a 0–100 scale. Pick one, document it.
2. `τ` has no default (proposed: playbook default 48 h for home services).
3. `IntentSignal` needs a concrete aggregation, e.g.
   `clamp(0.4·replied_recently + 0.3·opened_offer + 0.2·asked_price_or_timing + 0.1·sent_docs, 0, 1)`.
4. `AnnoyanceRisk` needs a formula, e.g.
   `min(100, 15·unanswered_touches + 40·asked_for_space + 100·optout_language)` on the 0–100
   convention.
5. The hard guarantees (quiet hours, max_attempts, STOP) are correctly stated as
   score-independent ✓ — keep them as pre-filters, never encoded into the score.

### 4.4 Required corrections
- **Declare the scale:** adopt `FollowUpPriority ∈ [−100, 100]` with LeadScore kept 0–100 and
  `AnnoyanceRisk ∈ [0,100]`. Rule: contact only if priority > 0 and all hard gates pass.
- Default `τ = 48 h`; per-playbook override.
- Concrete formulas for IntentSignal and AnnoyanceRisk (above).

### 4.5 Test vectors (τ = 48 h; AnnoyanceRisk on 0–100 scale)

| # | LeadScore | Δt (h) | TimeDecay | Intent | AR | Expected |
|---|---|---|---|---|---|---|
| F1 | 80 | 48 | 1−e⁻¹ = 0.6321205588 | 0.8 | 5 | **35.4557157613** |
| F2 | 100 | Δt→∞ | 1.0 | 1.0 | 0 | **100.0** (max) |
| F3 | 30 | 24 | 1−e⁻⁰·⁵ = 0.3934693403 | 0.2 | 10 | **−7.6391839577** → no contact |
| F4 | 60 | 96 | 1−e⁻² = 0.8646647168 | 0.5 | 20 | **5.9399415034** |

Arithmetic:
- F1: `80 · 0.6321205588 = 50.5696447042; ·0.8 = 40.4557157634; −5 = 35.4557157634`
  (assert `≈ 35.45571576`, tol 1e-6 for the transcendental).
- F3: `30 · 0.3934693403 = 11.8040802090; ·0.2 = 2.3608160418; −10 = −7.6391839582`.
- F4: `60 · 0.8646647168 = 51.8798830063; ·0.5 = 25.9399415032; −20 = 5.9399415032`.

Adversarial:
- **FA1 (Δt = 0):** `TimeDecay = 1 − e⁰ = 0` → priority `= −AR ≤ 0` → never contact
  immediately after progress. With AR = 0: expected exactly **0.0** and still no contact
  (rule is strictly `> 0`).
- **FA2 (scale-regression guard):** LeadScore 90, TimeDecay 0.9, Intent 1.0, client explicitly
  asked for space. On the mandated 0–100 AR scale (`asked_for_space → +40`):
  `90·0.9·1.0 − 40 = 81 − 40 = 41.0` — still positive, **but** the "asked for space" condition
  must ALSO set a hard gate that blocks contact regardless of score. Test asserts: score 41.0
  computed AND contact blocked. An implementation using AR ∈ [0,1] would compute 80.1 and, if
  the hard gate is missing, spam an annoyed client — this fixture exists to catch both bugs.

### 4.6 Recommendation
**Rule-based** for the score; **learned** only for channel preference ordering (as the doc
already scopes). Anti-spam behavior must never depend on a learned component.

### 4.7 Acceptance criteria
- F1–F4, FA1–FA2 pass (tol 1e-6).
- Property: hard gates (quiet hours, min interval, max_attempts, opt-out, STOP) block contact
  for **any** score value, including the maximum.
- Priority ≤ 0 never produces an outbound touch.

---

## 5. DocRisk (§5)

```
DocRisk = 100 · (0.25·A + 0.20·M + 0.20·C + 0.15·P + 0.10·L + 0.10·Q),  Q = 1 − OCR_q
```

### 5.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 5.2 Definition check
- Weights: `0.25+0.20+0.20+0.15+0.10+0.10 = 1.00` ✓.
- Output ∈ `[0,100]` if inputs ∈ `[0,1]` ✓ (same clamp caveat as LeadScore).
- `θ_docrisk = 60` default given ✓; action on breach defined ✓.
- `Q` fully defined from `OCR_q` ✓. **A, M, C, P, L have no scoring rubric** — "asymmetry of
  obligations" as a number in [0,1] is entirely LLM/analyzer-produced with no calibration
  anchor (what document scores A = 0.5?).

### 5.3 Defects found
1. **Rubric-free inputs.** Five of six inputs are model-judged severities with no anchored
   examples. Two model versions will score the same contract differently → threshold crossings
   flip across upgrades. Requires an anchored rubric (per-level exemplars) + regression fixtures.
2. **Missing OCR_q unhandled:** born-digital PDFs have no OCR pass — is `OCR_q = 1.0` (no
   penalty) or undefined? Must define `OCR_q := 1.0` for native text.
3. Same determinism-boundary caveat as LeadScore: deterministic *given* the persisted input
   vector only.
4. No input clamping mandated.

### 5.4 Required corrections
- Anchored 5-point rubric (0, 0.25, 0.5, 0.75, 1.0) with one exemplar clause per level for
  A/M/C/P/L; store rubric version with the score.
- `OCR_q = 1.0` for born-digital text; clamp all inputs to [0,1].

### 5.5 Test vectors

| # | A | M | C | P | L | OCR_q (→Q) | Expected | ≥ θ=60? |
|---|---|---|---|---|---|---|---|---|
| D1 | 1 | 1 | 1 | 1 | 1 | 0 (Q=1) | **100.0** | Yes |
| D2 | 0 | 0 | 0 | 0 | 0 | 1 (Q=0) | **0.0** | No |
| D3 | 0.8 | 0.5 | 0 | 1.0 | 0.6 | 0.85 (Q=0.15) | **52.5** | No |
| D4 | 1.0 | 1.0 | 0.5 | 0.5 | 0.5 | 0.5 (Q=0.5) | **72.5** | Yes → HUMAN_REVIEW_REQUIRED |

Arithmetic:
- D3: `0.25·0.8=0.20; 0.20·0.5=0.10; 0.20·0=0; 0.15·1.0=0.15; 0.10·0.6=0.06;
  0.10·0.15=0.015 → Σ=0.525 → 52.5`.
- D4: `0.25+0.20+0.10+0.075+0.05+0.05 = 0.725 → 72.5`.

Adversarial:
- **DA1 (missing OCR_q):** born-digital PDF, `OCR_q` absent. Expected: treated as `OCR_q=1.0`
  → `Q=0`; with A=M=C=P=L=0.5: `0.5·(0.25+0.20+0.20+0.15+0.10) + 0 = 0.45 → 45.0`. A NaN or
  crash fails the test.
- **DA2 (out-of-range severity):** analyzer emits `C = 1.4`. Expected: clamp to 1.0; with all
  other inputs 0: `0.20·1.0 = 0.20 → 20.0`, plus audit flag. Unclamped would give 28.0 — assert
  20.0.

### 5.6 Recommendation
**Hybrid** — deterministic combiner over LLM-produced, rubric-anchored severities; the rubric +
regression fixtures are what make the LLM inputs tolerable.

### 5.7 Acceptance criteria
- D1–D4, DA1–DA2 pass (±1e-9).
- `≥ 60.0` (raw float compare) routes to `HUMAN_REVIEW_REQUIRED` with the "requires human before
  signing" label; output separates found vs. unverified.
- Rubric version persisted with every score.

---

## 6. Evidence Confidence (§6)

```
Confidence = OCR_q · Extraction_q · Source_q · Consistency_q ∈ [0,1]
```

### 6.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 6.2 Definition check
- Four factors named with sources ✓; output bound `[0,1]` stated ✓; `θ_conf = 0.6` default ✓;
  abstention rule crisp ✓.
- **Scale mismatch with §11:** `Source_q` "from §11 trust score" — but SourceTrust is **0–100**
  and Confidence factors are **[0,1]**. The `/100` mapping is never written down. As documented,
  plugging SourceTrust = 75 in raw would give Confidence = 75·(other factors) ≫ 1.
- `Consistency_q` for an uncorroborated-but-unconflicted fact is "lower" — **no number given**.

### 6.3 Defects found
1. **Multiplicative severity is intentional but uncalibrated (confirmed).** Four independently
   "quite sure" factors at 0.9 each give `0.9⁴ = 0.6561` — squeaking past θ=0.6. At 0.87 each:
   `0.87⁴ = 0.57289761` → **abstain**, even though every individual factor is 87% confident.
   That harshness is arguably the *point* (compound uncertainty should compound), but it is a
   design decision that must be stated, and it only works if the factor values are **calibrated
   probabilities** — a vibes-based 0.85 vs 0.9 from a model flips the abstention decision. The
   doc's §13 calibration requirement (Brier/ECE) must explicitly cover these four factors, not
   just `P(close|a)`.
2. **Source_q mapping undefined** (`Source_q = SourceTrust/100` — write it down).
3. **Consistency_q defaults undefined.** Propose: corroborated = 1.0, standalone = 0.8,
   conflicted = 0.4 (playbook-tunable).
4. Missing factors (e.g. no OCR stage) — must default to 1.0 (no evidence against), not 0
   (which would zero every fact) and not silently skipped.

### 6.4 Required corrections
- `Source_q := SourceTrust/100`. Defaults: absent stage → factor 1.0; standalone Consistency_q
  = 0.8; conflicted = 0.4.
- Clamp each factor to [0,1]; calibration tracking (ECE) per factor in the Evaluation Lab.

### 6.5 Test vectors

| # | OCR_q | Extr_q | Source_q | Cons_q | Expected | Abstain (θ=0.6)? |
|---|---|---|---|---|---|---|
| C1 | 1.0 | 1.0 | 1.0 | 1.0 | **1.0** | No |
| C2 | 0.9 | 0.9 | 0.9 | 0.9 | **0.6561** | No (barely) |
| C3 | 0.87 | 0.87 | 0.87 | 0.87 | **0.57289761** | **Yes** |
| C4 | 0.95 | 0.9 | 0.8 | 0.7 | **0.4788** | Yes |
| C5 | 0.9 | 0.85 | 0.75 (SourceTrust 75) | 1.0 | **0.57375** | Yes |

Arithmetic:
- C2: `0.9² = 0.81; 0.81² = 0.6561`.
- C3: `0.87² = 0.7569; 0.7569² = 0.57289761`.
- C4: `0.95·0.9 = 0.855; ·0.8 = 0.684; ·0.7 = 0.4788`.
- C5: `0.9·0.85 = 0.765; ·0.75 = 0.57375` — also asserts the `/100` SourceTrust mapping.

Adversarial:
- **CA1 (zero factor):** `Extraction_q = 0` → Confidence **0.0** regardless of others → abstain.
- **CA2 (factor > 1):** miscalibrated model emits `OCR_q = 1.1`; with others 0.9:
  clamped result `1.0·0.9·0.9·0.9 = 0.729`; unclamped `1.1·0.729 ≠` — assert **0.729** + audit
  flag. (Unclamped would be `1.1·0.9³ = 0.8019` — a >1-input silently *raising* confidence is
  exactly the anti-hallucination failure mode.)

### 6.6 Recommendation
**Hybrid** — deterministic product, but the four inputs MUST be calibration-tracked
(reliability curves); otherwise the multiplicative form is precision theater.

### 6.7 Acceptance criteria
- C1–C5, CA1–CA2 pass (±1e-9).
- `Confidence < 0.6` blocks asserting the fact, blocks autonomous client-facing actions built
  on it, and raises `LowConfidence` in EscalationScore.
- Missing pipeline stage → factor 1.0 with an audit note; per-factor ECE dashboards exist.

---

## 7. OfferScore (§7)

```
OfferScore = 100 · (0.25·Price + 0.20·Scope + 0.15·Warranty + 0.15·Time
                    + 0.10·Payment + 0.10·Risk + 0.05·Service)
```

### 7.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 7.2 Definition check
- Weights: `0.25+0.20+0.15+0.15+0.10+0.10+0.05 = 1.00` ✓.
- Output ∈ [0,100] given [0,1] inputs ✓.
- **Price normalization formula never given** — only "cheapest = 1.0". Cheapest-anchored how?
  `min_price/price_i` (proposed here) vs. linear rescale between min and max produce different
  rankings. Must be pinned.
- **Polarity of `Risk` is ambiguous and dangerous.** DocRisk (§5) uses higher = worse; here
  `Risk` is *added* with positive weight, so it must mean higher = *safer* (i.e. `1 − risk`).
  The doc never says so. An implementer copying §5's polarity would rank the riskiest offer
  highest on that axis.
- Scope/Warranty/Time/Payment/Service have no normalization recipes (e.g. warranty years / cap).

### 7.3 Defects found
1. **Price divide-by-zero (confirmed):** with `Price_i = min_price/price_i`, a €0 offer
   (free quote line, data error) makes `min_price = 0` → every other offer's Price = `0/p = 0`
   and the zero-price offer's Price = `0/0` = NaN. Also `price_i = 0` alone → `min/0` = ∞.
2. **Single-offer degenerate set (confirmed):** with one offer, Price ≡ 1.0 by definition and
   the "comparison" axis carries dead weight; the recommendation must disclose that Price was
   non-informative.
3. Risk polarity (above).
4. No missing-axis semantics (offer omits warranty info → 0? penalized as worst? flagged?).

### 7.4 Required corrections
- Pin `Price_i = min_price / price_i` with guard: reject/flag offers with `price ≤ 0` before
  normalization; if the set is a single offer, set Price = 1.0 and flag `comparison_degenerate`.
- Rename/define `Risk` axis as `Safety = 1 − normalized_risk` (higher = better) or negate the
  weight; either way, write the polarity down.
- Define missing-axis rule: missing data scores the axis 0 **and** raises a hidden-risk flag
  (an offer shouldn't win by omitting its warranty terms).

### 7.5 Test vectors (Price_i = min_price/price_i; set of 3 offers priced €1000/€1250/€2000)

Price axes: A `1000/1000 = 1.0`, B `1000/1250 = 0.8`, C `1000/2000 = 0.5`.

| # | Offer | Price | Scope | Warr | Time | Pay | Risk(=safety) | Svc | Expected |
|---|---|---|---|---|---|---|---|---|---|
| O1 | A (€1000) | 1.0 | 0.8 | 0.6 | 0.7 | 1.0 | 0.9 | 0.5 | **82.0** |
| O2 | B (€1250) | 0.8 | 1.0 | 1.0 | 0.5 | 0.5 | 1.0 | 1.0 | **82.5** |
| O3 | perfect | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | **100.0** |

Arithmetic:
- O1: `0.25·1.0=0.25; 0.20·0.8=0.16; 0.15·0.6=0.09; 0.15·0.7=0.105; 0.10·1.0=0.10;
  0.10·0.9=0.09; 0.05·0.5=0.025 → Σ=0.82 → 82.0`.
- O2: `0.20+0.20+0.15+0.075+0.05+0.10+0.05 = 0.825 → 82.5`.
- Note O2 > O1: the pricier offer wins on value — this pair is the fixture for "value-based,
  not cheapest" and must keep this ordering.

Adversarial:
- **OA1 (price = 0):** offer priced €0 in a set with €1000 → expected: offer rejected from the
  comparison with a data-quality flag; the remaining set normalizes without it. Naive
  implementation yields `min_price = 0` → all Price axes 0 or NaN — test asserts the guard.
- **OA2 (single offer):** one offer only → Price = 1.0, `comparison_degenerate` flag set; with
  all other axes 0.5: `0.25·1.0 + 0.5·(0.20+0.15+0.15+0.10+0.10+0.05) = 0.25 + 0.5·0.75
  = 0.25 + 0.375 = 0.625 → 62.5`.

### 7.6 Recommendation
**Rule-based** — comparison must be explainable to the client ("B wins because warranty +
service"); ML ranking would destroy the product's explainability promise.

### 7.7 Acceptance criteria
- O1–O3, OA1–OA2 pass (±1e-9); O2 > O1 ordering preserved.
- price ≤ 0 never reaches the normalizer; single-offer sets are flagged.
- Every hidden-risk flag carries an evidence ref; Risk axis polarity documented and tested.

---

## 8. EscalationScore (§8; `13` §2)

```
EscalationScore = Risk + ValueCriticality + LowConfidence + ClientEmotion
                  + LegalSensitivity + UnusualRequest        (each ∈ [0,1])
```

### 8.1 Status
**DOCUMENTED ONLY.** Not implemented (and `13` §2.1 explicitly notes the model ships Phase 3;
MVP runs hard overrides + manual rules only).

### 8.2 Definition check
- Explicitly additive, not weight-normalized — stated up front ✓. Six terms, each ∈ [0,1] ✓.
- Output bound: `[0, 6.0]` — **derivable but never stated**; state it.
- `θ_escalate = 1.5` default ✓ — sane: it demands roughly "1.5 units of accumulated severity",
  reachable by one maxed term plus half of another. Not a defect in itself.
- Hard overrides (LegalSensitivity = 1 on signing; safety emergency) consistent between `05` §8
  and `13` §2.1 ✓ (`13` correctly narrows to exactly two).
- `ValueCriticality = min(1, value/high_value_threshold)` and `LowConfidence = 1 − Confidence`
  are defined ✓. **Risk, ClientEmotion, UnusualRequest have no calibration anchors** — the doc
  never says what makes `ClientEmotion = 0.5` vs 0.7. With an additive threshold at 1.5, a
  ±0.2 sentiment-model drift on two terms is the difference between silence and interrupt.

### 8.3 Defects found
1. **Term calibration undefined (confirmed).** Three of six terms are unanchored model outputs
   feeding a hard threshold. Requires anchored rubrics + drift monitoring (the doc's §13
   distribution monitoring must specifically alarm on per-term drift, not just the sum).
2. **No per-term clamping mandated.** A mis-scaled emotion classifier emitting 5.0 single-handedly
   breaches every threshold; a negative "risk" from a buggy signal *offsets* real severity.
3. Max value 6.0 undocumented; consumers (CaseRiskScore §10b divides by θ_escalate) should know
   the range.

### 8.4 Required corrections
- Clamp every term to [0,1] before summing; audit-flag clamps.
- State output range [0, 6.0].
- Anchored rubrics for Risk / ClientEmotion / UnusualRequest (0/0.25/0.5/0.75/1.0 exemplars);
  per-term distribution alarms.

### 8.5 Test vectors

| # | Risk | ValCrit | LowConf | Emotion | Legal | Unusual | Sum | Escalate (θ=1.5)? |
|---|---|---|---|---|---|---|---|---|
| E1 | 0 | 0 | 0 | 0 | 0 | 0 | **0.0** | No |
| E2 | 1 | 1 | 1 | 1 | 1 | 1 | **6.0** (max) | Yes |
| E3 | 0.2 | min(1, 12000/10000)=1.0 | 1−0.7=0.3 | 0.1 | 0 | 0 | **1.6** | Yes |
| E4 | 0.3 | 0.4 | 0.3 | 0.2 | 0 | 0.2 | **1.4** | No |
| E5 | 0 | 0 | 0 | 0 | **1.0 (signing)** | 0 | **1.0** | **Yes — hard override**, despite sum < 1.5 |

Arithmetic: E3 `0.2+1.0+0.3+0.1 = 1.6`; E4 `0.3+0.4+0.3+0.2+0.2 = 1.4`.

Adversarial:
- **EA1 (mis-scaled term):** emotion classifier emits `ClientEmotion = 5.0`, all else 0.
  Expected: clamp → sum **1.0**, no threshold escalation (though emotion=1.0 may still matter
  via rubric rules), audit flag. Unclamped sum 5.0 would falsely interrupt — assert 1.0.
- **EA2 (negative term):** `Risk = −0.5` with ValCrit=1.0, LowConf=0.6. Expected: clamp Risk→0,
  sum `1.6` → escalate. Unclamped `1.1` would suppress a legitimate escalation — assert 1.6.

### 8.6 Recommendation
**Rule-based** combiner permanently (it is a safety interlock — must be predictable); the term
*producers* (emotion, unusualness) are ML but rubric-anchored and drift-monitored.

### 8.7 Acceptance criteria
- E1–E5, EA1–EA2 pass (±1e-9).
- Hard overrides fire independent of the sum (E5); recomputed on every inbound event.
- Per-term clamps + per-term distribution monitoring in place before Phase-3 enablement.

---

## 9. StuckScore (§9)

```
StuckScore = DaysSinceProgress · LeadScore · MissingBlockerWeight
```

### 9.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 9.2 Definition check — FAILS
- `MissingBlockerWeight` defined (max blocking `w_i`, or 1 if stalled with none) ✓.
- **No output bound and no normalization of `DaysSinceProgress` (confirmed).**
  `DaysSinceProgress` is an unbounded raw count and `LeadScore` is 0–100, so the score grows
  without limit: 30 days × 100 × 0.9 = 2700. There is no defined range, so…
- **`θ_stuck` is referenced but NEVER given a default value anywhere in the document set
  (confirmed — grep of `05` and `13`).** A threshold over an unbounded, unit-incoherent
  quantity is unimplementable: is θ_stuck 50? 500? 5000? Every tenant's answer differs with
  their day counts. This formula cannot ship as written.

### 9.3 Defects found
1. Unbounded output + undefined θ_stuck (above) — **the formula has no operational semantics.**
2. Day-granularity cliff: score is 0 for 23 hours 59 minutes of staleness, then jumps.
3. Negative `DaysSinceProgress` possible under clock skew / future-dated progress events →
   negative score silently sorts the case to the bottom.
4. Unit incoherence: days × (0–100 score) × weight — three different unit systems multiplied.

### 9.4 Required corrections (proposed normalized form)
```
StuckScore_n = min(1, DaysSinceProgress / D_cap) · (LeadScore/100) · MissingBlockerWeight
D_cap default = 14 days (playbook);  θ_stuck default = 0.25;  clamp Days := max(0, Days)
```
Output ∈ [0,1]; dashboard sorts on the raw product before the min-clamp if desired, but the
*trigger* uses the bounded form.

### 9.5 Test vectors

Raw documented formula (for the dashboard-sort regression fixture):

| # | Days | LeadScore | MBW | Raw expected |
|---|---|---|---|---|
| S1 | 5 | 80 | 0.9 | **360.0** |
| S2 | 12 | 70 | 1.0 (stalled, no blocker) | **840.0** |
| S3 | 0 | 95 | 0.9 | **0.0** |
| S4 | 30 | 100 | 0.9 | **2700.0** — demonstrates unbounded growth |

Normalized form (D_cap = 14, θ_stuck = 0.25):

| # | Days | LeadScore | MBW | Expected | Trigger? |
|---|---|---|---|---|---|
| S5 | 5 | 80 | 0.9 | **0.2571428571** | Yes (≥ 0.25) |
| S6 | 3 | 60 | 0.5 | **0.0642857143** | No |
| S7 | 28 | 100 | 1.0 | **1.0** (clamped) | Yes |

Arithmetic:
- S5: `min(1, 5/14) = 0.3571428571; ·0.8 = 0.2857142857; ·0.9 = 0.2571428571`.
- S6: `3/14 = 0.2142857143; ·0.6 = 0.1285714286; ·0.5 = 0.0642857143`.

Adversarial:
- **SA1 (negative days):** progress event timestamped tomorrow → `Days = −1`. Expected: clamp
  to 0 → score **0.0** + `clock_skew` audit flag. Unclamped raw gives −72.0 with LeadScore 80,
  MBW 0.9 — a stuck case hidden below every healthy one.
- **SA2 (θ over raw scale):** assert the implementation refuses to compare a raw (unbounded)
  score to θ_stuck — trigger evaluation must use the normalized form. (Test: raw 360.0 with
  θ_stuck=0.25 must NOT be interpreted as "1440× over threshold" for alert severity.)

### 9.6 Recommendation
**Rule-based**, normalized form. It is a housekeeping sweep; interpretability beats precision.

### 9.7 Acceptance criteria
- S1–S7, SA1–SA2 pass (S5–S7 tol 1e-9).
- θ_stuck and D_cap exist as playbook defaults (0.25 / 14 d) before first sweep runs.
- Nightly sweep is idempotent; negative staleness clamped and flagged.

---

## 10. PromiseBreachScore (§10)

```
PromiseBreachScore = Importance · Delay · DependencyImpact
Delay = max(0, now − promise.due_at) "normalized by an expected-fulfillment window"
```

### 10.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 10.2 Definition check — FAILS
- Three terms named ✓; client/company symmetry well specified ✓.
- **The "expected-fulfillment window" is never defined (confirmed)** — not per promise type,
  not as a playbook default, not even a unit (hours? days?). `Delay` is therefore uncomputable.
- **`θ_breach` is referenced but never given a default value anywhere (confirmed).**
- `Importance` scale unstated (assume [0,1]); **`DependencyImpact` is "how many downstream
  steps… are blocked" — a raw count, not [0,1]** → the product is unbounded (e.g. 0.9·1.0·7
  = 6.3) and no threshold can be sensibly set.

### 10.3 Defects found
1. Undefined window → Delay uncomputable (above).
2. θ_breach undefined (above).
3. DependencyImpact unnormalized count → unbounded product.
4. Whether Delay saturates at 1.0 or keeps growing is unstated (a 10×-overdue promise: score
   10× or capped?).

### 10.4 Required corrections (proposed)
```
Delay = min(1, max(0, now − due_at) / W_type)
  W_type defaults (playbook): document/photo 72 h; payment 120 h; signed contract 48 h;
  generic 72 h.
DependencyImpact = min(1, blocked_count / 5)   (5 = playbook cap)
θ_breach default = 0.25;  output ∈ [0,1]
```

### 10.5 Test vectors (proposed normalization; generic W = 72 h, dep cap = 5)

| # | Importance | Overdue (h) | Delay | Blocked | DepImpact | Expected | Trigger (θ=0.25)? |
|---|---|---|---|---|---|---|---|
| P1 | 0.9 | 36 | 36/72 = 0.5 | 4 | 0.8 | **0.36** | Yes |
| P2 | 1.0 | not due yet | 0 | 3 | 0.6 | **0.0** | No |
| P3 | 1.0 | 200 | min(1, 2.7778) = 1.0 | 5 | 1.0 | **1.0** (max) | Yes |
| P4 | 0.3 | 72 | 1.0 | 1 | 0.2 | **0.06** | No — low-stakes promise, correctly quiet |

Arithmetic: P1 `0.9·0.5·0.8 = 0.36`; P4 `0.3·1.0·0.2 = 0.06`.

Adversarial:
- **PA1 (future due date):** `due_at = now + 24 h` → `max(0, −24) = 0` → score **0.0** ✓ (the
  documented `max(0,·)` already covers this; the fixture pins it).
- **PA2 (raw-count regression guard):** Importance 0.9, Delay 1.0, `blocked_count = 7` fed raw.
  Naive product `0.9·1.0·7 = 6.3` — out of [0,1] and 25× θ. Expected with normalization:
  `0.9·1.0·min(1, 7/5) = 0.9·1.0·1.0 = 0.9`. Test asserts **0.9**.
- **PA3 (W_type = 0):** misconfigured playbook window 0 h → division by zero. Expected: loader
  rejects `W_type ≤ 0`; scorer never sees it.

### 10.6 Recommendation
**Rule-based.** Promise tracking is a contract-with-the-user feature; behavior must be
predictable to the tenant who configured the windows.

### 10.7 Acceptance criteria
- P1–P4, PA1–PA3 pass (±1e-9).
- W_type table and θ_breach = 0.25 exist as playbook defaults before feature enablement.
- Company-side breach ≥ θ routes to owner alert; client-side to Missing-Info follow-up —
  both directions covered by integration tests.

---

## 11. SourceTrust (§11)

```
SourceTrust = 100 · (0.35·Authority + 0.25·Recency + 0.20·Corroboration
                     + 0.15·Directness + 0.05·Transparency)
```

### 11.1 Status
**DOCUMENTED ONLY.** Not implemented (WebScout itself is Phase 3).

### 11.2 Definition check
- Weights: `0.35+0.25+0.20+0.15+0.05 = 1.00` ✓. Output [0,100] given [0,1] inputs ✓.
- **`Corroboration` is defined as "Number of independent sources agreeing" — a raw count, not
  [0,1].** As written, 4 agreeing sources contribute `0.20·4 = 0.8` and the score exits its
  bounds (see adversarial vector below). Needs a saturating map.
- Authority/Recency/Directness/Transparency have ordinal descriptions but no numeric anchors
  (what is "retailer = mid" numerically? 0.5? 0.6?).
- Feeds §6 `Source_q` — the `/100` mapping gap is logged under §6 above.

### 11.3 Defects found
1. Corroboration raw count breaks the [0,100] bound (above).
2. No numeric anchor table for the ordinal levels — two implementers will produce different
   trust landscapes. Ship a lookup table (e.g. Authority: official 1.0, manufacturer 0.9,
   registry/gov 1.0, retailer 0.5, blog 0.3, forum 0.2, unknown 0.1).
3. Recency needs a concrete decay vs. fact-volatility class (price: half-life weeks; spec
   sheet: years) — currently prose only.

### 11.4 Required corrections
- `Corroboration = min(1, (n_agreeing − 1)/3)` (0 for standalone, saturates at 4 sources);
  or `n/(n+2)` — pick one, document it. Fixtures below use `min(1, (n−1)/3)`.
- Numeric anchor tables for the four ordinal terms, playbook-versioned.

### 11.5 Test vectors (Corroboration = min(1, (n−1)/3))

| # | Auth | Rec | n_agree → Corr | Direct | Transp | Expected |
|---|---|---|---|---|---|---|
| T1 (mfr spec PDF) | 1.0 | 0.9 | 3 → 0.6667 | 1.0 | 1.0 | **90.8333333333** |
| T2 (anon forum) | 0.2 | 0.5 | 1 → 0.0 | 0.3 | 0.0 | **24.0** |
| T3 (all max) | 1.0 | 1.0 | 4 → 1.0 | 1.0 | 1.0 | **100.0** |
| T4 (all min) | 0 | 0 | 1 → 0 | 0 | 0 | **0.0** |

Arithmetic:
- T1: `Corr = min(1, 2/3) = 0.6666666667`. `0.35·1.0 = 0.35; 0.25·0.9 = 0.225;
  0.20·0.6666666667 = 0.1333333333; 0.15·1.0 = 0.15; 0.05·1.0 = 0.05 →
  Σ = 0.9083333333 → 90.8333333333` (tol 1e-6).
- T2: `0.07 + 0.125 + 0 + 0.045 + 0 = 0.24 → 24.0`.

Adversarial:
- **TA1 (raw-count regression guard):** n_agree = 4 fed raw with Auth 1.0, Rec 0.9, Direct 1.0,
  Transp 1.0: naive `0.35 + 0.225 + 0.20·4 + 0.15 + 0.05 = 1.575 → 157.5` — out of bounds.
  Expected with saturation: `0.35 + 0.225 + 0.20·1.0 + 0.15 + 0.05 = 0.975 → 97.5`.
  Test asserts **97.5**.
- **TA2 (missing recency):** undated page → Recency must default to a defined pessimistic value
  (propose 0.2), not 1.0 and not null. With Auth 0.5, n=1, Direct 0.5, Transp 0:
  `0.175 + 0.25·0.2 + 0 + 0.075 + 0 = 0.30 → 30.0`.

### 11.6 Recommendation
**Rule-based** with versioned anchor tables; trust scoring must be explainable per URL
(it also feeds the anti-hallucination chain via Source_q).

### 11.7 Acceptance criteria
- T1–T4, TA1–TA2 pass (T1 tol 1e-6, rest ±1e-9).
- Property: output ∈ [0,100] for any n_agreeing ∈ ℕ.
- Every stored fact carries URL, source type, date checked, snippet, trust score;
  `Source_q = SourceTrust/100` covered by a §6 integration test (fixture C5).

---

## 12. CaseRiskScore (§10b)

```
CaseRiskScore = 100 · max(0.6 · max_open(RiskFlag.severity),
                          0.4 · DocRisk_max / 100,
                          min(1, EscalationScore / θ_escalate))
```

### 12.1 Status
**DOCUMENTED ONLY.** Not implemented.

### 12.2 Definition check
- Composition-of-max structure is deterministic and bounded [0,100] **iff** severity ∈ [0,1] —
  but `RiskFlag.severity`'s scale is defined in `04-data-model.md` territory and never
  restated here; if it is an enum (1–5) the first branch explodes to 300.
- `max_open(·)` over an **empty set** (case with no open risk flags — the common case!) is
  mathematically undefined; the doc doesn't specify the identity value.
- **Branch ceilings are asymmetric and probably unintended:** the coefficients cap branch 1 at
  60 and branch 2 at **40** — a document with `DocRisk = 100` (maximum possible document risk,
  already past the human-review threshold) contributes at most **40/100** to case risk, i.e.
  reads as "moderate" on any dashboard, while only the escalation branch can reach 100. If the
  0.6/0.4 factors are meant as *importance discounts* inside a max (unusual — discounts belong
  in weighted sums, not max compositions), the doc must say so and the UI must band accordingly;
  otherwise this silently under-reports document-driven risk.

### 12.3 Defects found
1. Empty-set `max_open` undefined → define identity 0.
2. Branch-ceiling asymmetry (above) — at minimum document that CaseRiskScore ∈ [0,100] but the
   DocRisk pathway saturates at 40 and the RiskFlag pathway at 60.
3. `RiskFlag.severity` scale not restated; must assert ∈ [0,1] at the scoring boundary.
4. Divide-by-θ: `θ_escalate` is tenant-tunable; a tenant setting it to 0 → division by zero.
   Config validation must enforce `θ_escalate > 0`.

### 12.4 Required corrections
- `max_open(∅) := 0`; assert severity ∈ [0,1]; validate `θ_escalate > 0` at config load.
- Explicitly document (or redesign) the 60/40 branch ceilings. If full-range document risk is
  desired, use `max(0.6·sev, DocRisk_max/100·0.4 + …)` alternatives are ugly — the honest fix
  is a design decision; audit only demands it be *made*.

### 12.5 Test vectors (θ_escalate = 1.5)

| # | max sev (open flags) | DocRisk_max | EscalationScore | Branches | Expected |
|---|---|---|---|---|---|
| R1 | 0.8 | 70 | 0.9 | 0.48 / 0.28 / 0.6 | **60.0** |
| R2 | none (∅ → 0) | 0 | 0 | 0 / 0 / 0 | **0.0** |
| R3 | 0.2 | 30 | 1.5 | 0.12 / 0.12 / min(1, 1.0)=1.0 | **100.0** |
| R4 | 1.0 | 100 | 0 | 0.6 / 0.4 / 0 | **60.0** — max-severity flag + max DocRisk still reads 60 (ceiling defect fixture) |
| R5 | 0 | 55 | 0.6 | 0 / 0.22 / 0.4 | **40.0** |

Arithmetic: R1 `0.6·0.8 = 0.48; 0.4·70/100 = 0.28; min(1, 0.9/1.5) = 0.6 → max = 0.6 → 60.0`.
R5 `0.4·0.55 = 0.22; 0.6/1.5 = 0.4 → 40.0`.

Adversarial:
- **RA1 (empty flag set):** implementation calling `max()` on an empty list must not throw or
  return −∞; expected branch value **0** (fixture R2 asserts end-to-end 0.0).
- **RA2 (θ_escalate = 0):** tenant config sets θ to 0 → config validation error at load; the
  scorer never divides. A runtime `min(1, x/0)` returning `min(1, inf) = 1 → 100` would mark
  every case critical — assert the load-time rejection instead.

### 12.6 Recommendation
**Rule-based** — it is a roll-up of other scores; any learning belongs in the constituents.

### 12.7 Acceptance criteria
- R1–R5, RA1–RA2 pass (±1e-9).
- Persisted to `Case.risk_score` with input branches in the audit payload (which branch won).
- Severity-scale assertion at the boundary; θ validation at config load.
- The 60/40 ceiling decision is documented in `05` §10b before implementation (blocker).

---

## Summary defect table

Severity: **CRITICAL** = formula unimplementable or produces wrong decisions as written;
**HIGH** = incorrect numbers/bounds under realistic inputs; **MEDIUM** = ambiguity that will
fork implementations; **LOW** = documentation gap.

| # | Formula | Severity | Defect | Fix |
|---|---|---|---|---|
| 1 | StuckScore | **CRITICAL** | Unbounded output (days × 0–100 × weight); no normalization; `θ_stuck` never defined | Normalized form `min(1, d/14)·(LS/100)·MBW`, θ_stuck = 0.25, clamp d ≥ 0 |
| 2 | PromiseBreachScore | **CRITICAL** | Fulfillment window undefined → Delay uncomputable; θ_breach never defined; DependencyImpact is a raw count → unbounded | `W_type` table (72 h generic), `Delay = min(1, overdue/W)`, `DepImpact = min(1, n/5)`, θ_breach = 0.25 |
| 3 | FollowUpPriority | **CRITICAL** | 0–100 LeadScore × [0,1] multipliers minus AnnoyanceRisk of unspecified scale — anti-spam term numerically irrelevant on the doc's own [0,1] convention | Declare AR ∈ [0,100] (or normalize LS/100); τ = 48 h default; concrete Intent/AR formulas; contact iff > 0 + hard gates |
| 4 | NBA Utility | **HIGH** | Monetary Value (€) mixed with unitless Cost/Risk; λ undefined; §12's FollowUpPriority→P(close\|a) mapping undefined; all-negative-utility policy missing | All terms in €; `Risk = P(bad)·Severity_€`; λ = 0.05 default; bounded P mapping; prefer `wait` when max < 0 |
| 5 | MIS | **HIGH** | Σw = 0 (playbook with no required fields) → 0/0; `blocks_quote` defaults never assigned; no weight validation | `MIS_n := 0` when Σw = 0 + warning; reject w < 0; ship blocks_quote defaults |
| 6 | OfferScore | **HIGH** | Price normalization formula never given; price = 0 → div-by-zero/NaN; single-offer set degenerate; Risk-axis polarity ambiguous (higher = safer, unstated) | Pin `min_price/price_i`; reject price ≤ 0; flag n=1; document polarity as safety axis |
| 7 | SourceTrust | **HIGH** | Corroboration = raw source count → score exits [0,100] (157.5 at n=4); no numeric anchors for ordinal levels; Source_q /100 mapping unstated | `Corr = min(1,(n−1)/3)`; anchor tables; `Source_q = SourceTrust/100` |
| 8 | CaseRiskScore | **HIGH** | `max_open(∅)` undefined; DocRisk branch ceiling = 40 / flag branch = 60 (silent under-reporting); θ_escalate = 0 div-by-zero; severity scale not restated | `max(∅) := 0`; document/decide ceilings; validate θ > 0; assert sev ∈ [0,1] |
| 9 | EscalationScore | **MEDIUM** | Range [0, 6.0] unstated; Risk/ClientEmotion/UnusualRequest have no calibration anchors against a hard θ = 1.5; no per-term clamping | Clamp terms to [0,1]; anchored rubrics; per-term drift alarms; state range |
| 10 | Evidence Confidence | **MEDIUM** | Multiplicative product is intentionally harsh (0.9⁴ = 0.6561 barely passes; 0.87⁴ = 0.5729 abstains) but works only with calibrated factors; Source_q scale gap; Consistency_q standalone value unnumbered | ECE tracking per factor; /100 mapping; standalone = 0.8, conflicted = 0.4; missing stage → 1.0 |
| 11 | LeadScore | **MEDIUM** | Determinism claim depends on LLM-derived U/D inputs (reproducible only from persisted input vector); only V clamped; missing-input defaults absent for U/C/D; band-edge comparison unstated | Clamp all inputs; per-variable defaults; document determinism boundary; raw-float banding |
| 12 | DocRisk | **LOW** | A/M/C/P/L severities rubric-free (model-drift flips θ crossings); missing OCR_q for born-digital docs unhandled | Anchored 5-point rubric + regression fixtures; `OCR_q := 1.0` for native text; clamp inputs |

**Cross-cutting:** `θ_stuck` and `θ_breach` are the only two thresholds in the entire document
set with no default value — both formulas are unshippable until they exist. The doc's global
"[0,1] unless stated otherwise" convention is violated by its own Corroboration (count),
DependencyImpact (count), AnnoyanceRisk (unspecified), and DaysSinceProgress (days) terms.

---

## Canonical fixtures notice

The test vectors in this document (L1–L5/LA1–LA3, M1–M5/MA1–MA2, N1–N4/NA1–NA2, F1–F4/FA1–FA2,
D1–D4/DA1–DA2, C1–C5/CA1–CA2, O1–O3/OA1–OA2, E1–E5/EA1–EA2, S1–S7/SA1–SA2, P1–P4/PA1–PA3,
T1–T4/TA1–TA2, R1–R5/RA1–RA2) are the **canonical fixtures for the scoring module
implementation**. They must be committed as machine-readable test data alongside the first
line of scoring code, executed in CI, and version-locked to the weight-set version they were
computed against (the `05` HVAC/home-services MVP profile). Any change to a default weight or
threshold requires recomputing and re-reviewing the affected vectors — a fixture edit without a
weight-version bump is a red-flag review item. Vectors marked "regression guard" (LA2, NA2,
FA2, PA2, TA1, EA1, SA2) exist specifically to fail against the naive-but-wrong reading of the
current documentation; do not "fix" the test to match such an implementation.
