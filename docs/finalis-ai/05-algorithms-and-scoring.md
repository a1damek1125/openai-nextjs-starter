# Finalis AI — Algorithms & Mathematical Scoring Models

> All scores are computed by deterministic, auditable functions — **not** by asking an LLM
> "rate this 0–100". LLMs and specialist models produce the *inputs* (e.g. an urgency signal,
> an OCR confidence, an extracted price); the scoring layer combines them with tenant-tunable
> weights. This keeps behavior explainable, testable, and stable across model upgrades.

Conventions:
- Every sub-signal is normalized to `[0, 1]` before weighting unless stated otherwise.
- Weights per model sum to 1.0 (except additive escalation/stuck/breach scores, which are
  explicitly unbounded-then-thresholded).
- Weights live in `IndustryPlaybook.scoring_weights` (JSON) so verticals differ without code
  changes. The defaults below are the HVAC/home-services MVP profile.
- Every score persists with its **input vector** and **weight set version** in `AuditEvent`
  so any number can be reproduced and back-tested.

---

## 1. Lead Score

```
LeadScore = 100 · (0.30·V + 0.20·U + 0.15·F + 0.15·C + 0.10·D + 0.10·R)
```

| Symbol | Meaning | How the input is produced (normalized 0–1) |
|---|---|---|
| V | Predicted job value | `min(1, estimated_value / value_cap)`; `value_cap` per playbook (e.g. €15k). Estimate from job type + scope + Deal Memory of similar closed cases. |
| U | Urgency | Emergency=1.0, this-week=0.7, this-month=0.4, "someday"=0.1. Derived from intake language + keywords (e.g. "no heating", "leak"). |
| F | Info completeness | `1 − MIS_normalized` (see §2). Fraction of required fields present, weighted. |
| C | Fit to company services | Rule/embedding match of requested job vs. `BusinessProfile.services`. 0 if out of area/scope. |
| D | Decision-maker probability | Signals: "I", "my house", budget authority language, sole owner vs. "I need to ask my partner/landlord". |
| R | Responsiveness | EWMA of past reply latency and reply rate for this party (Deal Memory). New client = prior 0.5. |

**Bands**: Hot ≥ 70 · Warm 45–69 · Cool 25–44 · Cold < 25. Bands drive dashboard sorting
and default follow-up aggressiveness. Bands are tunable per tenant.

**Cold-start**: with no history, `R = 0.5`, `V` from playbook medians; the score is flagged
`low_confidence` until ≥3 real signals exist.

---

## 2. Missing Information Score (MIS)

```
MIS = Σ_i  w_i · m_i          m_i ∈ {0,1}  (1 = required field i is missing)
MIS_normalized = MIS / Σ_i w_i           (over all required fields for the case type)
```

- `w_i` = business weight of the field from the playbook. Fields also carry a boolean
  `blocks_quote`. A missing field with `blocks_quote=true` prevents entering
  `QUOTE_PREPARATION` regardless of MIS.
- Default HVAC weights: address **0.9**, nameplate/appliance photo **0.7**, preferred time
  **0.5**, room dimensions **0.6**, budget band **0.3**, decision confirmation **0.4**.
- **Trigger**: if `MIS_normalized ≥ θ_mis` (default 0.25) *or* any `blocks_quote` field is
  missing → Missing Information Hunter creates/queues a `MissingItem` request via the best
  channel (chosen by §4). One consolidated request per contact, never field-by-field spam.

---

## 3. Next Best Action (NBA) Utility

For each candidate action `a` in the action space (call, WhatsApp, SMS, email, request-doc,
prepare-quote, escalate, wait, schedule, compare-offers, do-web-research):

```
Utility(a) = P(close | a) · Value  −  Cost(a)  −  Risk(a)  −  DelayPenalty(a)
```

| Term | Definition & estimation |
|---|---|
| `P(close \| a)` | Marginal probability this action advances toward close. Start with a **rule/heuristic prior table** per (state, action); upgrade to a logistic model trained on outcomes once data exists. |
| `Value` | `estimated_value · LeadScore/100` (risk-adjusted expected value). |
| `Cost(a)` | Monetary + effort cost: human-call ≫ AI-call > phone-minutes > WhatsApp ≈ SMS > email ≈ 0; includes token/compute cost. |
| `Risk(a)` | Chance of a bad outcome (annoyance, wrong info, compliance) × its severity. Escalation-worthy actions inherit `EscalationScore`. |
| `DelayPenalty(a)` | Opportunity cost of *not* acting now = `λ · TimeDecay · Value` (a "wait" action's whole cost is delay). |

**Policy**: choose `a* = argmax_a Utility(a)`. If `a*` requires an autonomy level above the
case's setting, emit a `HumanApproval` instead of executing. Ties break toward lower-cost,
lower-risk actions. The chosen `a*` becomes `Case.next_best_action`.

> Design note: NBA is a **decision-theoretic** selector, not an RL agent, for the MVP. This
> keeps it auditable. It can later be framed as a contextual bandit once we have enough
> logged (context, action, reward=closed?) tuples.

---

## 4. Follow-up Priority (anti-spam scheduler)

```
FollowUpPriority = LeadScore · TimeDecay · IntentSignal − AnnoyanceRisk
```

| Term | Definition |
|---|---|
| `TimeDecay` | Rises with time since last progress but is **gated by quiet hours & minimum interval**. E.g. `1 − e^(−Δt/τ)` with per-step floors so we never contact twice in a cool-down window. |
| `IntentSignal` | ↑ when the client sent docs, asked about timing/price, opened the offer, replied recently. |
| `AnnoyanceRisk` | ↑ with number of recent unanswered outbound touches, ↑ if client asked for space, ↑ near opt-out language. Hard cap: after `max_attempts` with no reply → `RECOVERY_LATER`. |

**Channel & timing selection**: among allowed channels (respecting client preference & quiet
hours), pick the one maximizing expected reply probability per unit AnnoyanceRisk. Preference
order is learned per party (Deal Memory) with a playbook default (WhatsApp → SMS → email →
call for home services).

**Hard guarantees (never violated regardless of score)**:
- Never contact during quiet hours / outside allowed local time window.
- Respect explicit channel opt-outs and global STOP.
- Enforce minimum inter-touch interval and max total attempts.

---

## 5. Document Risk Score

```
DocRisk = 100 · (0.25·A + 0.20·M + 0.20·C + 0.15·P + 0.10·L + 0.10·Q)
```

| Symbol | Meaning |
|---|---|
| A | Asymmetry of obligations (one-sided terms) |
| M | Missing standard elements (dates, parties, signatures, warranty, attachments) |
| C | Contradictions vs. prior agreements / other docs / call transcript |
| P | Risky payment terms (large upfront, no milestones, unclear currency) |
| L | Risky clauses (auto-renewal, uncapped penalties, unusual liability) |
| Q | OCR/scan quality penalty = `1 − OCR_q` (poor scans raise risk because we're less sure) |

**Action**: `DocRisk ≥ θ_docrisk` (default 60) → `HUMAN_REVIEW_REQUIRED` with the label
**"requires human before signing"**. The output always separates *what we found* (with
evidence refs) from *what we couldn't verify*. Never presented as legal advice.

---

## 6. Evidence Confidence

```
Confidence = OCR_q · Extraction_q · Source_q · Consistency_q         (∈ [0,1])
```

| Factor | Source |
|---|---|
| `OCR_q` | Recognition confidence for the region the field came from (per-region/line OCR confidence; see `07-document-intelligence.md`). |
| `Extraction_q` | Model/parse confidence that the region maps to this field (schema-constrained extraction confidence). |
| `Source_q` | Trust of the source (client-provided original > photo of a screen > web forum). For WebScout, from §11 trust score. |
| `Consistency_q` | Agreement with other evidence for the same fact (1.0 if corroborated, lower if it stands alone or conflicts). |

**Abstention rule**: if `Confidence < θ_conf` (default 0.6) the system MUST NOT assert the
fact as certain. It surfaces it as *unverified* and, for documents, asks for a clearer scan;
for web facts, lowers trust or seeks a second source. This is the core anti-hallucination
guardrail — "never pretend certainty when confidence is low."

---

## 7. Offer Score (comparison)

```
OfferScore = 100 · (0.25·Price + 0.20·Scope + 0.15·Warranty + 0.15·Time
                    + 0.10·Payment + 0.10·Risk + 0.05·Service)
```

- `Price` is normalized **within the comparison set** (cheapest = 1.0 on the price axis) but
  the final recommendation is value-based, not just cheapest.
- Per-vertical weight overrides (examples): renovations weight `Scope`+`Time` higher; HVAC
  weights `Warranty`+`Service`; real estate weights legal `Risk`; auto workshop weights
  `Time`+parts/`Warranty`.
- Output is a table + a plain-language recommendation + explicit **hidden-risk flags**
  (missing service, shorter warranty, exclusions), each with an evidence ref to the source
  offer. See `10-offer-comparison-and-verification.md`.

---

## 8. Escalation Score (additive, thresholded)

```
EscalationScore = Risk + ValueCriticality + LowConfidence + ClientEmotion
                  + LegalSensitivity + UnusualRequest
```

Each term ∈ `[0,1]` (not required to sum to 1 — this is a severity accumulator):

| Term | Signal |
|---|---|
| Risk | Operational/compliance risk of proceeding autonomously |
| ValueCriticality | `min(1, value/high_value_threshold)` |
| LowConfidence | `1 − Confidence` on the deciding fact(s) |
| ClientEmotion | Negative-sentiment/anger/distress from voice or text |
| LegalSensitivity | Contract/notarial/legal content or promises |
| UnusualRequest | Out-of-distribution ask vs. playbook |

**Rule**: `EscalationScore ≥ θ_escalate` (default 1.5) → global interrupt edge to
`HUMAN_REVIEW_REQUIRED`. Certain terms are **hard overrides** (any LegalSensitivity=1 on a
signing decision, any safety emergency) that escalate regardless of the sum.

---

## 9. Case Stuck Score

```
StuckScore = DaysSinceProgress · LeadScore · MissingBlockerWeight
```

- `MissingBlockerWeight` = max `w_i` among blocking `MissingItem`s (or 1 if none but still
  stalled). High StuckScore on a high LeadScore case is the worst case — money left on the
  table — and is surfaced top of the "stuck cases" dashboard tile.
- Computed nightly by the stuck sweep; crossing `θ_stuck` triggers a follow-up or an owner
  alert (whichever the autonomy level allows).

---

## 10. Promise Breach Score

```
PromiseBreachScore = Importance · Delay · DependencyImpact
```

| Term | Meaning |
|---|---|
| Importance | Business weight of the promised item (e.g. "send signed contract" ≫ "send a photo") |
| Delay | How overdue: `max(0, now − promise.due_at)` normalized by an expected-fulfillment window |
| DependencyImpact | How many downstream steps/other promises are blocked by this one |

- Applies symmetrically to promises made by the **client** and by the **company/technician/
  notary/supplier**. A breached *company* promise is often more damaging (trust) and may
  escalate to the owner; a breached *client* promise triggers a Missing-Info follow-up.
- Crossing `θ_breach` → reminder (client side) or owner alert / escalation (company side).

---

## 10b. Case Risk Score

```
CaseRiskScore = 100 · max(0.6 · max_open(RiskFlag.severity),
                          0.4 · DocRisk_max / 100,
                          min(1, EscalationScore / θ_escalate))
```

A deterministic roll-up of the case's open `RiskFlag` severities, the highest `DocRisk`
among the case's documents (§5), and proximity to the escalation threshold (§8). Persisted
to `Case.risk_score`; recomputed with the other scores (§12). Like every score here it is
auditable: inputs + weight version persist to `AuditEvent`.

---

## 11. WebScout Source Trust Score

```
SourceTrust = 100 · (0.35·Authority + 0.25·Recency + 0.20·Corroboration
                    + 0.15·Directness + 0.05·Transparency)
```

| Term | Meaning |
|---|---|
| Authority | Official manufacturer/registry/gov = high; retailer = mid; forum/unknown = low |
| Recency | Freshness of the page vs. how time-sensitive the fact is (price ↔ recent) |
| Corroboration | Number of independent sources agreeing |
| Directness | Primary source (spec sheet PDF) > secondary (blog summarizing it) |
| Transparency | Named author/publisher, dated, verifiable vs. anonymous |

`SourceTrust` feeds `Source_q` in §6. Every WebScout fact is stored with URL, source type,
date checked, snippet, trust score, and relevance (see `08-webscout-web-research.md`).

---

## 12. Interaction of scores (the daily loop)

Nightly + on every inbound event, for each active case:

1. Recompute `LeadScore`, `MIS`, `StuckScore`, `PromiseBreachScore`, `EscalationScore`,
   and `CaseRiskScore` (persisted as `Case.risk_score`, §10b).
2. If `EscalationScore ≥ θ_escalate` → escalate (stop here).
3. Else enumerate candidate actions, compute `Utility(a)` (§3) with `FollowUpPriority`
   feeding the follow-up actions' `P(close|a)` and timing (§4).
4. Choose `a*`; if allowed by autonomy → execute + audit; else → `HumanApproval`.
5. Persist all scores + inputs + weight-version to `AuditEvent`.

This loop is why Finalis is a *worker* and not a chatbot: the scores turn a pile of open
cases into a prioritized, self-updating work queue.

---

## 13. Calibration, evaluation & safety of the scores

- **Start heuristic, then learn.** Ship the weighted models above; log outcomes; back-test
  weight changes on historical cases before rolling out (shadow scoring).
- **Calibrate probabilities.** `P(close|a)` and `Confidence` should be calibrated (reliability
  curves); a "0.8" must mean ~80% empirically. Track Brier score / ECE in the Evaluation Lab
  (`15-evaluation-lab.md`).
- **Guard against gaming & drift.** Monitor score distributions per tenant; alert on sudden
  shifts (often a broken upstream signal, e.g. OCR regression inflating `Q`).
- **Human overrides are training data.** Every time a human overrides a score-driven action,
  log it as a labeled example for future calibration.
- **Uncertainty is first-class.** Any score built on `Confidence < θ_conf` inputs is itself
  flagged low-confidence and cannot trigger an autonomous client-facing action.
