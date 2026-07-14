# Finalis AI — Algorithm Autofix & Test Report

> Follow-up to `26-math-and-algorithm-verification.md`, whose ground truth was "zero application
> code; every formula DOCUMENTED ONLY." That is no longer true: all 12 scoring models are now
> **Implemented and tested** as pure functions in `finalis/scoring.py`, with the test suite in
> `tests/test_scoring.py` (part of the **102-test passing** suite on branch
> `claude/finalis-ai-enterprise-e2e-autofix`). Every function validates and clamps its inputs so
> no formula can produce NaN or an out-of-bounds result.

---

## 1. The 12 models — implementation and test matrix

| # | Model (function) | Input range | Output range | Normalization | Default weights / thresholds | Tests (`tests/test_scoring.py`) |
|---|---|---|---|---|---|---|
| 1 | LeadScore (`lead_score`) | V,U,F,C,D,R clamped to [0,1] | [0,100] | 100·Σwᵢxᵢ, Σw must = 1.0 | V .30, U .20, F .15, C .15, D .10, R .10 | zero: `test_all_zero`; max: `test_all_max_bounded_100`; adversarial: `test_out_of_range_inputs_clamped` (5.0/−3.0 clamp to 1/0); weights: `test_bad_weights_rejected` (ValueError); vector: `test_hot_hvac_emergency` (79.0) |
| 2 | MIS (`mis`) | binary flags + non-negative weights | raw ≥ 0; normalized [0,1] | raw/Σw, guarded | θ_mis 0.25 (consumer-side); HVAC weight table per doc 05 | Σw=0: `test_sigma_w_zero_guard` → (0,0); adversarial: `test_negative_weight_rejected` (ValueError); zero: `test_nothing_missing`; vector: `test_hvac_example` (1.3, 1.3/3.4) |
| 3 | NBA Utility (`nba_utility`, `next_best_action`) | p_close clamped [0,1]; value floored at 0; cost/risk/delay in € | unbounded signed utility; argmax over candidates | p·max(0,value) − cost − risk − delay | tie-break to lower cost then lower risk | `test_hot_call_beats_cold_email`, `test_wait_costs_delay`; missing: `test_empty_candidates_rejected` (ValueError); tie: `test_tie_breaks_to_lower_cost` |
| 4 | FollowUpPriority (`followup_priority`) | lead as LeadScore/100; all factors clamped [0,1] | **[−1, 1]** | lead/100 puts all factors on one scale | contact iff > 0 (policy layer) | unit fix: `test_unit_coherence` (extremes exactly 1.0 / −1.0); `test_annoyance_dominates_low_lead` |
| 5 | DocRisk (`doc_risk`) | A,M,C,P,L,Q clamped [0,1] | [0,100] | fixed weights .25/.20/.20/.15/.10/.10 | θ_docrisk 60 | bounds: `test_bounds` (0 and 100); vector: `test_risky_contract` (66.5 ≥ 60) |
| 6 | Evidence Confidence (`evidence_confidence`) | 4 factors clamped [0,1] | [0,1] | multiplicative product | θ_conf 0.6 | `test_multiplicative` (0.9⁴ = 0.6561); threshold: `test_below_theta_conf` (0.87⁴ < 0.6, doc-26 harshness note); zero: `test_any_zero_kills_confidence` |
| 7 | OfferScore (`offer_score`, `normalize_prices`) | axis values clamped [0,1]; prices > 0 for normalization | [0,100]; price axis (0,1] | cheapest/priceᵢ; Σw must = 1.0 | price .25, scope .20, warranty .15, time .15, payment .10, risk .10, service .05 | vector: `test_full_axes` (84.0); missing: `test_missing_axis_scores_zero_not_crash` (axes default 0, no KeyError); guards: `test_price_normalization_guards` (empty → [], zero → [0.0], single → [1.0], pair → [1.0, 0.5]) |
| 8 | EscalationScore (`escalation_score`, `must_escalate`) | 6 terms each clamped [0,1] | [0, 6] additive | per-term clamp (doc-26 §9 fix) | θ_escalate 1.5; hard overrides `legal_signing`, `safety_emergency` | threshold: `test_threshold` (1.4 no / 1.6 yes); overrides: `test_hard_overrides_ignore_threshold` (escalate at score 0.0); adversarial: `test_bounds` (all-9s clamp to 6.0) |
| 9 | StuckScore (`stuck_score`) | days ≥ 0 normalized by cap; lead/100; blocker weight clamped | **[0,100] bounded** | days/days_cap clamped to 1 | days_cap 30; θ_stuck 40 (consumer-side, provisional) | max/adversarial: `test_bounded_at_100` (3650 days → exactly 100); zero: `test_zero_days`; vector: `test_typical` (11.2) |
| 10 | PromiseBreachScore (`promise_breach_score`) | importance, dependency_impact clamped [0,1]; delay hours ≥ 0 | **[0,1] bounded** | delay/expected_window clamped to 1 | expected_window_hours 72; θ_breach 0.3 (consumer-side, provisional) | max/adversarial: `test_bounded_0_1` (100 000 h late → exactly 1.0); zero: `test_not_yet_late`; vector: `test_typical` (0.24) |
| 11 | SourceTrust (`source_trust`) | 5 factors clamped [0,1] | [0,100] | fixed weights .35/.25/.20/.15/.05 | — | vector: `test_manufacturer_pdf` (81.5); adversarial: `test_corroboration_must_be_normalized` (raw count 7 clamps — no 157.5-style blowout) |
| 12 | CaseRiskScore (`case_risk_score`) | severity [0,1], doc_risk/100, escalation/θ — all clamped | [0,100] | max of three clamped branches | branch weights .6 (risk flags) / .4 (doc risk) / 1.0 (escalation); θ_escalate 1.5 | rollup: `test_rollup_takes_max_branch` (escalation branch clamps to 1 → 100); empty: `test_empty_case` (max(∅) := 0 semantics); bounds: `test_bounds` |

## 2. Doc-26 defects → what the implementation fixed

| Doc-26 defect (summary table #) | Fix in `finalis/scoring.py` | Proving test |
|---|---|---|
| #1 StuckScore CRITICAL: unbounded (days × 0–100 × weight), θ_stuck undefined | Bounded [0,100] via `days_cap=30` normalization (`_clamp(days/days_cap)`); θ_stuck=40 shipped as the consumer default in `CompletionLoop.stuck_sweep` | `TestStuckScore::test_bounded_at_100` |
| #2 PromiseBreachScore CRITICAL: fulfillment window undefined, unbounded, θ_breach undefined | Bounded [0,1] via `expected_window_hours=72` delay normalization; dependency_impact clamped; θ_breach=0.3 shipped in `CompletionLoop.promise_check` | `TestPromiseBreach::test_bounded_0_1` |
| #3 FollowUpPriority CRITICAL: 0–100 LeadScore against [0,1] multipliers made anti-spam term irrelevant | Unit coherence: LeadScore/100 so all factors share [0,1]; output bounded [−1,1]; annoyance term now numerically meaningful | `TestFollowUpPriority::test_unit_coherence`, `test_annoyance_dominates_low_lead` |
| #4 NBA HIGH: units mixed, all-negative policy | All terms euro-denominated in `ActionCandidate`; p_close clamped; value floored at 0; deterministic tie-break to lower cost/risk. (All-negative → `wait` remains a policy-layer decision, see §3) | `TestNBA::*` incl. `test_tie_breaks_to_lower_cost`, `test_wait_costs_delay` |
| #5 MIS HIGH: Σw=0 → 0/0 NaN; no weight validation | `Σw = 0 → (0, 0)` guard; negative weights raise `ValueError`; length mismatch raises | `TestMIS::test_sigma_w_zero_guard`, `test_negative_weight_rejected` |
| #6 OfferScore HIGH: price normalization never given; price ≤ 0 / single-offer degenerate; missing axes | Pinned `cheapest/priceᵢ` in `normalize_prices` with guards for empty list, all-zero prices, and single offer; missing axes score 0 (worst) instead of crashing; weight-sum validated | `TestOfferScore::test_price_normalization_guards`, `test_missing_axis_scores_zero_not_crash` |
| #7 SourceTrust HIGH: raw corroboration count exits [0,100] | All five inputs clamped to [0,1] before weighting — a raw count of 7 cannot push the score past 100 | `TestSourceTrust::test_corroboration_must_be_normalized` |
| #8 CaseRiskScore HIGH: max(∅) undefined, θ_escalate=0 div-by-zero | Max-of-branches rollup with every branch clamped; empty inputs yield 0; escalation branch `_clamp(esc/θ)` cannot exceed 1 | `TestCaseRisk::test_rollup_takes_max_branch`, `test_empty_case`, `test_bounds` |
| #9 EscalationScore MEDIUM: range unstated, no per-term clamping, hard overrides | Per-term clamp gives stated range [0,6]; `must_escalate` implements θ=1.5 **plus** the two 13 §2 hard overrides (`legal_signing`, `safety_emergency`) that ignore the score entirely | `TestEscalation::test_bounds`, `test_hard_overrides_ignore_threshold`, `test_threshold` |
| #10 Evidence Confidence MEDIUM: harshness works only with calibrated factors | Product form implemented with clamped factors; the harshness regime is pinned by test (0.87⁴ abstains). Calibration itself remains open (§3) | `TestEvidenceConfidence::test_below_theta_conf`, `test_any_zero_kills_confidence` |
| #11 LeadScore MEDIUM: only V clamped, weight drift, missing-input defaults | Every input clamped; weight sum validated with `ValueError` on drift. (Per-variable missing-input defaults remain a playbook-loader concern, see §3) | `TestLeadScore::test_out_of_range_inputs_clamped`, `test_bad_weights_rejected` |
| #12 DocRisk LOW: severities rubric-free, inputs unclamped | Inputs clamped; weights fixed and bounded. Rubric anchoring is a data problem, not a code one (§3) | `TestDocRisk::test_bounds`, `test_risky_contract` |

Cross-cutting: doc 26's two missing thresholds (`θ_stuck`, `θ_breach`) now exist as shipped
defaults (40 on the 0–100 StuckScore scale; 0.3 on the 0–1 breach scale), and its global
"[0,1] unless stated" convention is now *enforced* by `_clamp` at every entry point rather than
assumed.

## 3. Remaining OPEN items code cannot fix alone

1. **Calibration data for `P(close|a)` and Evidence Confidence factors.** The NBA priors and the
   four confidence factors are implemented as pass-through inputs; whether 0.9 *means* 90% needs
   production outcome data and ECE tracking per doc 26 §6.6 — no amount of scaffold code
   substitutes for it.
2. **Term calibration for EscalationScore inputs.** Risk, ClientEmotion, and UnusualRequest are
   LLM-derived signals scored against a hard θ=1.5; the combiner is safe and clamped, but the
   anchored rubrics and drift alarms (doc 26 §9) require labeled transcripts.
3. **Provisional thresholds.** `θ_stuck=40` and `θ_breach=0.3` were chosen in the scaffold
   (doc 26 proposed 0.25 on differently-normalized forms). Both are consumer-side parameters of
   `CompletionLoop`, deliberately easy to retune — **mark provisional until Evaluation Lab
   (doc 15) data exists.** Same for `days_cap=30` and `expected_window_hours=72`.
4. **Playbook-loader concerns:** per-variable missing-input defaults for LeadScore (U/C/D),
   `blocks_quote` default assignments, and DocRisk severity rubrics live in playbook
   configuration/validation, not in the pure functions.

## 4. Verdict

**Rule-based now, hybrid (calibrated) later — exactly per doc 26's recommendations.** The
deterministic combiners are implemented, bounded, validated, and locked by tests derived from
doc 26's canonical vectors (including its adversarial regression guards). The safety-interlock
scores (Escalation, MIS, PromiseBreach, OfferScore, SourceTrust, CaseRisk) stay rule-based
permanently; LeadScore weights, NBA priors, and confidence factors graduate to calibrated
hybrids once a few hundred labeled outcomes exist. Any threshold or weight change must recompute
the affected vectors and bump the weight-set version, per doc 26's canonical-fixtures notice.
