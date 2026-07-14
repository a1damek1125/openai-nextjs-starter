# Finalis AI — Evaluation Lab (Continuous Evaluation)

> Finalis is a *worker*, not a demo. A worker that autonomously touches paying clients has to
> be measured the way a production system is measured — continuously, per tenant, against hard
> thresholds, with alerting on regression and drift. The **Evaluation Lab** is the standing
> apparatus that does this: golden datasets, regression suites, LLM-as-judge with human
> calibration, shadow/offline eval before rollout, A/B + canary for any weight or model change,
> and live per-tenant dashboards.
>
> **Design stance (honest):** the published agent benchmarks say general autonomy is still
> unreliable on long, realistic tasks — TheAgentCompany reports the best agent completing
> **~24%** of consequential tasks fully autonomously (arXiv:2412.14161), and OSWorld reports
> **~12.2%** best-model vs **~72.4%** human on real computer tasks (arXiv:2404.07972). Voice
> full-duplex systems degrade on multi-step reasoning and pause discipline
> (Full-Duplex-Bench, arXiv:2503.04721). Those results are *why our targets are conservative
> and why a human stays in the loop.* The Evaluation Lab exists to prove — with numbers, per
> tenant — that we stay inside the envelope where the architecture is trustworthy, and to gate
> any expansion of autonomy on measured evidence rather than optimism.

Conventions used throughout:
- Targets marked **(aspirational)** are goals we have not yet validated on production data;
  targets marked **(gate)** block a release or an autonomy-level increase if unmet.
- Every metric names a **data source** that already exists elsewhere in the system
  (`AuditEvent`, `Call`, `ExtractedField`, transcripts, human overrides) — the Lab reads, it
  does not invent new state.
- "Cadence" is how often the metric is computed/reported: **per-event** (streamed),
  **nightly** (batch with the Completion Loop), **per-release** (regression gate), or
  **weekly** (human-labeled samples).
- Scores and their weights are deterministic (`05`); the Lab evaluates the *inputs* to those
  scores (extractions, intents, confidences) and the *outcomes* of score-driven actions — it
  never asks an LLM to "re-rate" a score.

---

## 1. Purpose

The Evaluation Lab continuously tests, per tenant and per vertical:

1. **Voice quality** — latency (time-to-first-audio), call completion, ASR accuracy, barge-in.
2. **Intent recognition** and **slot-filling** accuracy.
3. **Lead qualification** accuracy (vs human labels) and false-qualify rate.
4. **Data / field extraction** — OCR field F1 per field type, OCR quality, confidence
   calibration.
5. **Missing-information detection** recall.
6. **Follow-up appropriateness** — reply-per-attempt, opt-out rate, anti-spam guardrail
   adherence.
7. **Offer comparison** accuracy vs expert labels.
8. **Hallucination rate** — unsupported-claim rate (claims lacking a valid
   `EvidenceReference`), measured by the Quality Worker + human spot-check.
9. **Escalation precision & recall** — did it escalate when it should, and not when it
   shouldn't.
10. **Human approval rate** and **decision reversal rate**.
11. **Close-assist rate** — share of closed cases the AI materially advanced.

Everything below is grounded in the metrics and scores defined in `05` (scoring), `06`
(voice/latency), `07` (document intelligence / field F1 / calibration), and the **Quality
Worker** in `02`.

---

## 2. Metrics — definitions, measurement, targets, source, cadence

### 2.1 Voice quality (see `06`)

The Voice Worker already emits latency + `barge_in` metrics post-call for the Evaluation Lab
(`06` §5.6). The Lab aggregates them per tenant and per telephony/vendor config, because
`06` §3 warns that time-to-first-audio (TTFA) is highly **config-sensitive**.

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **TTFA P50** (simple turn) | Median time from end-of-utterance to first audio byte out | Timestamp `end_of_utterance → first_tts_frame` per turn; percentile over turns | **P50 ≤ 800 ms** (gate) | `Call` turn timings | per-event + nightly |
| **TTFA P95** | 95th percentile of the same | Same distribution, P95 | **P95 ≤ 1500 ms** (gate); repeated breach → shorten/scripted turns | `Call` turn timings | nightly |
| **Barge-in stop latency** | Time from detected speech onset (VAD) to TTS actually stopping | `barge_in_onset → tts_stop` per barge-in event | **≤ 200 ms** | `Call.barge_in_events` | per-event + nightly |
| **Tool-augmented TTFA P50** | TTFA for calendar/price/status tool turns | Same as TTFA but filtered to tool turns | **≤ 1200 ms P50** (aspirational) | `Call` turn timings | nightly |
| **Call completion rate** | Share of calls that reach a clean end state (goal met or clean handoff) vs dropped/dead-air/error | Classify each `Call` end reason; completion = {resolved, scheduled, warm-handoff}; failure = {dropped, timeout, error} | **≥ 90%** (aspirational) | `Call` end reason | nightly |
| **ASR WER** | Word Error Rate of the streaming STT final transcript vs a human reference transcript | On a sampled set, human-transcribe; WER = (S+D+I)/N | **≤ 12%** overall, **≤ 20%** on accented/noisy (aspirational) | sampled `Call` audio + human transcript | weekly (sample) |
| **Barge-in correctness** | Of detected barge-ins, share that were true user turns (not backchannel/noise false-triggers), and share of *real* interruptions we missed | Human-label a sample of barge-in events: {true-interrupt, false-trigger, missed}; report precision & recall | precision **≥ 0.9**, recall **≥ 0.85** (aspirational) | `Call.barge_in_events` + human label | weekly (sample) |

> **Voice honesty note (`06` §6):** we do **not** claim human-parity full-duplex. TTFA
> targets are "feels natural," not the ~200 ms human turn-taking modal gap. Full-Duplex-Bench
> (arXiv:2503.04721) shows pause discipline and self-correction remain hard; the Lab tracks
> barge-in correctness and completion rate precisely because these are the known weak points.

### 2.2 Intent recognition & slot-filling

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Intent accuracy** | Correct intent label vs human/gold label | Confusion matrix over a labeled turn set; report accuracy + macro-F1 (imbalanced classes) | accuracy **≥ 92%**, macro-F1 **≥ 0.85** (aspirational) | golden intent set + prod sample | per-release + weekly |
| **Slot-filling accuracy** | Correct value for each required slot (address, date, price, appliance, etc.) | Per-slot exact/normalized match vs gold; report per-slot precision/recall; critical slots (address, date, price, amount) reported separately | critical slots **≥ 95%** exact, others **≥ 88%** (aspirational) | golden slot set + prod sample | per-release + weekly |

Critical slots are exactly the ones `06` §4 confirms explicitly ("was that *fifteen* or
*fifty*?"). A repair-confirmed slot counts as correct only if the final confirmed value
matches gold.

### 2.3 Lead qualification (see `05` §1 LeadScore)

We do **not** evaluate the LeadScore number directly (it is deterministic). We evaluate the
**qualify decision** it drives — the band assignment (`Hot/Warm/Cool/Cold`, `05` §1) and any
autonomous qualify/route action — against human labels.

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Qualification precision** | Of leads the system marks qualified (e.g. Hot/Warm → pursue), share humans agree are genuinely qualified | Human relabels a sample; precision = TP/(TP+FP) | **≥ 0.85** (aspirational) | human labels vs band decision | weekly |
| **Qualification recall** | Of genuinely qualified leads, share the system caught | recall = TP/(TP+FN) on the same sample | **≥ 0.80** (aspirational) | human labels vs band decision | weekly |
| **False-qualify rate** | Share of pursued leads that a human judges should have been dropped/out-of-scope (drives wasted outreach + annoyance) | FP / all pursued | **≤ 10%** (gate for raising follow-up autonomy) | human labels + `Action` log | weekly |

Cold-start `low_confidence` leads (`05` §1) are reported as a separate cohort so their
higher error rate does not mask steady-state quality.

### 2.4 Document / field extraction (see `07`)

`07` §4 fixes field-level **F1 (precision/recall)** as the IDP standard metric, tracked **per
field type**, and mandates confidence calibration monitoring here.

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Field extraction F1 (per field type)** | Precision/recall of each extracted field vs a gold-labeled document set, per field type (supplier, date, total, VAT, warranty, parties, price, …) | Match extracted `ExtractedField` value to gold (normalized: dates, currency, numbers); F1 per type | numeric/structured **F1 ≥ 0.95**; free-text **F1 ≥ 0.85**; critical financial fields (amount, IBAN, total) **≥ 0.97** (aspirational) | golden doc set (`07`) + prod sample | per-release + weekly |
| **OCR quality (`OCR_q`)** | Recognition quality of the region a field came from | Distribution of per-region `OCR_q` (`05` §6 / `07` §3); watch for downward drift | monitor; **alert** on tenant median `OCR_q` drop > 0.1 week-over-week | `ExtractedField` region confidence | nightly |
| **Confidence calibration** | Does a stated `Confidence` of *x* mean ~*x* empirically? | Bin extractions by predicted `Confidence`; plot **reliability curve** (predicted vs observed-correct); compute **ECE** and **Brier score** | **ECE ≤ 0.05**; reliability curve within ±0.1 of diagonal per bin (aspirational) | `ExtractedField.Confidence` + gold correctness | weekly + per-release |
| **Abstention correctness** | When `Confidence < θ_conf` we abstain (`05` §6, `07` §4). Are abstentions justified? | Of abstained fields, share a human confirms were genuinely unreliable; of *non*-abstained, share that were wrong (missed abstentions) | abstain precision **≥ 0.8**; missed-abstention (confident-but-wrong) **≤ 3%** (gate) | abstain log + human label | weekly |

**Calibration is a first-class metric here.** The idea (a probabilistic forecast is
*calibrated* when events assigned probability *p* occur a fraction ≈*p* of the time) is
measured with **reliability diagrams** and summarized by **Expected Calibration Error (ECE)**
and the **Brier score** (mean squared error between predicted probability and outcome). `07`
§4 notes numeric fields are typically well-calibrated while free-text is overconfident, and
prescribes **Platt/isotonic** recalibration — the Lab both measures ECE/Brier and validates
that recalibration actually moved the reliability curve toward the diagonal. `05` §13 applies
the same discipline to `P(close|a)` and evidence `Confidence`.

### 2.5 Missing-information detection (see `05` §2 MIS)

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Missing-info recall** | Of fields a human says were genuinely missing/needed, share the system flagged as a `MissingItem` | Human labels required-but-absent fields on a case sample; recall = flagged / truly-missing | **≥ 0.90** (aspirational) — missing a blocker is worse than a false request | `MissingItem` rows vs human label | weekly |
| **Missing-info precision** | Of items the system requested, share that were genuinely needed (avoid nagging for irrelevant fields) | precision = valid-requests / all-requests | **≥ 0.85** (aspirational) | `MissingItem` rows vs human label | weekly |
| **Blocker detection** | Did we correctly refuse to enter `QUOTE_PREPARATION` when a `blocks_quote` field was missing? | Check cases that reached quote prep against blocking-field completeness | **0** quotes prepared with a missing `blocks_quote` field (gate) | case state + `MissingItem` | nightly |

### 2.6 Follow-up appropriateness (see `05` §4 Follow-up Priority)

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Follow-up success rate** | Reply-per-attempt: share of follow-up touches that get a client reply | replies / outbound follow-up `Action`s, by channel | **≥ 25%** blended (aspirational; channel-dependent) | `Action` log + inbound events | nightly |
| **Opt-out rate** | Share of contacts who opt out / STOP after a follow-up | opt-outs / contacts touched | **≤ 2%** (gate — rising opt-out = over-contacting) | `Action` log + opt-out events | nightly |
| **Anti-spam guardrail adherence** | Adherence to the hard guarantees in `05` §4: no quiet-hours contact, honored opt-outs/STOP, min inter-touch interval, max attempts | Audit every outbound `Action` against the guarantees; count violations | **0 violations** (hard gate — these are "never violated regardless of score") | `Action` log + quiet-hours/interval config | per-event + nightly |
| **Annoyance-risk realism** | Does high `AnnoyanceRisk` actually predict opt-out/negative reply? | Correlate `AnnoyanceRisk` at send time with subsequent opt-out/negative sentiment | monitor; recalibrate if AUC < 0.65 | `Action` log + outcomes | weekly |

Guardrail adherence is measured as a **hard invariant**, not a rate to optimize: any violation
is a P1 alert because `05` §4 lists these as inviolable.

### 2.7 Offer comparison (see `05` §7 OfferScore, `10`)

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Comparison accuracy** | Does the AI's recommended offer / ranking match an expert's on the same offer set? | Experts label the best offer + hidden-risk flags on a gold offer set; compare top-1 pick and ranking (Kendall τ) | top-1 agreement **≥ 0.85**; τ **≥ 0.7** (aspirational) | golden offer set + expert labels | per-release + weekly |
| **Hidden-risk flag recall** | Of genuine hidden risks (missing service, shorter warranty, exclusions) experts identify, share the AI flagged | recall on expert-labeled risks; each AI flag must carry an `EvidenceReference` to the source offer | **≥ 0.90** (aspirational — missing a hidden risk is the costly error) | `Comparison` output + expert labels | weekly |

Value-based (not just cheapest) recommendation is the correctness criterion, matching `05` §7
("the final recommendation is value-based, not just cheapest").

### 2.8 Hallucination rate (Quality Worker + human spot-check)

**Definition:** the **unsupported-claim rate** — the share of AI-asserted claims in
client-facing or owner-facing output that lack a valid `EvidenceReference` (`07` §1.3) or
assert certainty on a fact whose `Confidence < θ_conf` (`05` §6 abstention rule).

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Unsupported-claim rate (machine)** | % of claims with no valid `EvidenceReference` / asserting-certainty-below-θ_conf | The **Quality Worker** (`02` §4) runs after high-stakes outputs (doc analysis, offer comparison, decision briefs): "is every claim evidence-linked? is confidence honest?" — counts unsupported claims / total claims | **≤ 1%** on client-facing output (gate); **0** on any signing/legal/financial assertion (hard gate) | Quality Worker output + `AuditEvent` | per-event |
| **Unsupported-claim rate (human)** | Same, on a human-audited sample (catches claims the Quality Worker itself missed) | Weekly human spot-check of a stratified sample; humans mark each claim supported/unsupported | **≤ 2%** (aspirational); tracked as the ground-truth check on the machine metric | human spot-check | weekly |
| **Quality Worker agreement** | Does the machine hallucination check agree with human auditors? | Compare Quality Worker verdicts to human verdicts on the sample; report precision/recall of the machine detector | detector recall **≥ 0.9** (must not under-count hallucinations) | Quality Worker vs human | weekly |

The Quality Worker is the internal analogue of adversarial verification / the "secondary LLM
critic" pattern (`02` §4). Because an LLM critic can share the generator's blind spots, the
**human spot-check is mandatory and calibrates the machine metric** — we never trust the
machine number alone (see §3 LLM-judge caveats).

### 2.9 Escalation precision & recall (see `05` §8 EscalationScore)

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Escalation recall** | Of cases that a human says *should* have escalated (`≥ θ_escalate` situations, legal/safety/anger), share the system did escalate | Human labels a case sample for should-escalate; recall = escalated∩should / should | **≥ 0.95** (gate — missing a required escalation is the dangerous error) | `HumanApproval`/escalation events + human label | weekly |
| **Escalation precision** | Of escalations raised, share a human agrees were warranted (avoid escalation fatigue) | precision = warranted / all escalations | **≥ 0.70** (aspirational — bias toward over-escalation is acceptable) | escalation events + human label | weekly |
| **Hard-override adherence** | Every hard override (`LegalSensitivity=1` on a signing decision, safety emergency) escalated regardless of the sum | Audit hard-override conditions against actual escalation | **0 misses** (hard gate) | `AuditEvent` + escalation events | per-event |

We deliberately prioritize **recall over precision** for escalation — consistent with the
architecture's human-in-the-loop stance justified by TheAgentCompany / OSWorld (`02` §0).

### 2.10 Human approval & decision reversal

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Human approval rate** | Of `HumanApproval` proposals surfaced (`05` §3 autonomy gate), share humans approve as-is | approved / total `HumanApproval`s, by action type | monitor — *very* high (>98%) may mean under-gating; very low (<70%) means the AI's proposals aren't trustworthy | `HumanApproval` outcomes | nightly |
| **Decision reversal rate** | Share of AI-taken (autonomous) actions a human later reverses/corrects | reversals / autonomous `Action`s | **≤ 5%** (gate for keeping/raising autonomy level) | `Action` log + override events | nightly |
| **Override-as-training-data capture** | Every human override logged as a labeled example (`05` §13) | Verify each override produces a labeled record for calibration | **100%** capture | override events → label store | nightly |

Approval rate is a **calibration** signal on our autonomy levels (`13`), not a "make it go
up" metric — both extremes are problems.

### 2.11 Close-assist rate

| Metric | Definition | Measurement | Target | Source | Cadence |
|---|---|---|---|---|---|
| **Close-assist rate** | Of closed/won cases, share where the AI *materially advanced* the case (qualified it, extracted a blocking field, ran the comparison that led to the decision, or drove a follow-up that got the reply that unblocked it) | For each closed case, attribute the pivotal advancing step(s) from the `AuditEvent` trail; human-validate a sample of attributions | **≥ 60%** (aspirational — headline "is the worker doing real work" metric) | `AuditEvent` trail + case outcome + human validation | nightly + weekly (validation) |
| **Time-to-first-action / stuck reduction** | Does AI involvement reduce `StuckScore` accrual and time-to-first-response vs a baseline? | Compare AI-handled vs baseline cohort on time-to-first-response and `StuckScore` (`05` §9) | monitor; report lift | `AuditEvent` + `StuckScore` | nightly |

"Materially advanced" is deliberately attribution-based and human-validated so this cannot be
gamed by counting trivial AI touches.

---

## 3. Methodology

### 3.1 Golden datasets per vertical
- A curated, versioned **golden set per vertical** (HVAC/home-services first per the MVP
  profile in `05`): labeled calls (audio + reference transcript + gold intents/slots), labeled
  documents (gold fields + bboxes + correctness), labeled offer sets (expert best-pick + hidden
  risks), and labeled cases (should-qualify, should-escalate, truly-missing fields).
- Golden sets are **frozen and versioned**; each row carries provenance and a label author.
  Regenerating a set is a reviewed change (it moves the goalposts).
- Golden sets seed the reliability curves and F1/precision/recall numbers above; production
  samples supplement them so we track the real tenant document/call mix (`07` §2 warns to
  evaluate on the tenant's *real* mix before locking OCR engine defaults).

### 3.2 Regression suites (per-release gate)
- Every release runs the golden sets through the changed workers and compares against the
  previous baseline. Any **(gate)** metric regressing beyond tolerance **blocks the release**.
- Deterministic scores (`05`) get exact-reproduction tests: replay the stored **input vector +
  weight-set version** from `AuditEvent` and assert the score reproduces bit-for-bit
  (guarantees "any number can be reproduced and back-tested," `05` §0).

### 3.3 LLM-as-judge with human calibration (and its caveats)
- For open-ended outputs (summaries, recommendations, follow-up phrasing, hallucination
  checks) we use an **LLM-as-judge** to scale evaluation — the same critic pattern as the
  Quality Worker (`02` §4).
- **Caveats we actively control for (honesty):**
  - **Self/family bias** — an LLM judge tends to favor outputs from the same model family; use
    a *different* model as judge than the generator where feasible.
  - **Position & verbosity bias** — judges favor the first option and longer answers; randomize
    order, control for length, use pairwise + rubric prompts.
  - **Blind spots shared with the generator** — a judge can miss exactly the hallucination the
    generator made. Therefore every LLM-judge metric is **calibrated against a human-labeled
    sample** (§2.8 Quality-Worker-vs-human agreement), and human labels are the ground truth of
    record. If judge-vs-human agreement drifts, the judge is re-prompted or replaced, not
    trusted.
- LLM-judge scores are reported **with** their human-agreement number attached, never alone.

### 3.4 Shadow / offline eval before rollout
- New models, prompts, OCR engines, or score weights first run in **shadow mode**: they process
  real traffic and produce proposals that are logged and scored **but not executed**
  (client-facing behavior unchanged). This is the `05` §13 "shadow scoring / back-test before
  rollout" discipline generalized to every worker.
- A change graduates from shadow only when its offline metrics meet the gates on both golden
  and shadow-production data.

### 3.5 A/B and canary for weight/model changes
- Any change to `scoring_weights` (`IndustryPlaybook`), model choice, or prompt ships behind a
  **canary** (small % of tenants/cases) then a controlled **A/B**, comparing the outcome
  metrics (close-assist, reversal rate, opt-out, hallucination) — not just offline proxies.
- Canary auto-rolls-back on any **(gate)** or **hard gate** breach or a significant adverse
  move in reversal/opt-out/hallucination.

### 3.6 Back-testing score-weight changes on historical cases
- Because every score persists its **input vector + weight-set version** (`05` §0, §13),
  proposed weight changes are **re-scored over historical cases** offline to estimate the
  effect (which cases change band, which actions flip) *before* any canary. This is the
  quantitative gate on tuning `LeadScore`, `OfferScore`, `DocRisk`, etc.

### 3.7 Red-teaming
- **Prompt injection via WebScout content** (`08`): adversarial web pages that try to hijack
  the agent through fetched content. The Lab maintains an injection corpus and asserts the
  guardrails (`02` §5 injection filters) neutralize it and that WebScout facts still carry
  honest `SourceTrust` (`05` §11). Structured accessibility-tree browsing (not pixel GUI
  agents, `02` §6) is part of the mitigation and is tested.
- **Jailbreaks** — attempts to make a worker bypass abstention, fabricate an
  `EvidenceReference`, exceed its autonomy level, or violate the anti-spam hard guarantees.
- **Document adversarial inputs** — malicious/misleading document content trying to force a
  wrong extraction or an unsupported claim.
- Red-team suites run per-release and on a rotating schedule; any successful attack is a P1 and
  becomes a permanent regression test.

### 3.8 Why the targets are conservative (benchmark context)
- **TheAgentCompany (arXiv:2412.14161, ~24% fully autonomous)** and **OSWorld
  (arXiv:2404.07972, ~12.2% best model vs ~72.4% human)** are the reason autonomy is gated on
  measured reversal/approval rates and escalation recall is prioritized — we assume the agent
  is *not* reliably autonomous on long tasks and design the Lab to prove where it *is* safe.
- **Full-Duplex-Bench (arXiv:2503.04721)** is the reason voice targets are "natural, not
  human-parity" and why barge-in correctness and completion rate are explicit gates.

---

## 4. Tooling

### 4.1 Internal eval harness
- A single harness runs a metric suite against a data source (golden set, shadow log, or live
  sample), writes results with the **model/prompt/weight versions** under test, and diffs
  against a stored baseline. Regression gates are expressed declaratively (metric, threshold,
  tolerance, gate|monitor).
- Reuses production plumbing: reads `AuditEvent`, `Call` timings, `ExtractedField`,
  `MissingItem`, `Action`, escalation/override events — no shadow schema. (NeMo Agent Toolkit
  is a *reference* for later multi-agent profiling, `02` §6, not an MVP dependency.)

### 4.2 Per-tenant live dashboards
- Each tenant gets a live dashboard of the §2 metrics (voice latency percentiles, F1 by field
  type, reliability curves + ECE/Brier, follow-up/opt-out, hallucination rate, escalation P/R,
  approval/reversal, close-assist), surfaced in the Case Command Center (`11`) alongside SLAs.
- Score-**distribution** panels per tenant (`LeadScore`, `Confidence`, `OCR_q`,
  `EscalationScore` histograms) implement the `05` §13 "monitor score distributions per tenant"
  requirement.

### 4.3 Alerting on regression & drift
- **Regression alerts**: any (gate) metric crossing its threshold on nightly batch or canary.
- **Drift alerts**: sudden shifts in a score distribution (`05` §13 — e.g. an OCR regression
  inflating the `Q`/`OCR_q` term, or a follow-up config change spiking opt-outs). Detected via
  distribution-distance tests week-over-week and by watching `OCR_q`/`Confidence` medians.
- **Hard-invariant alerts (P1)**: any anti-spam guardrail violation (§2.6), missed
  hard-override escalation (§2.9), quote prepared with a missing `blocks_quote` field (§2.5),
  or an unsupported claim on a signing/legal/financial assertion (§2.8).

---

## 5. Summary metrics table

| Metric | Target | Data source | Cadence |
|---|---|---|---|
| Voice TTFA P50 (simple turn) | ≤ 800 ms (gate) | `Call` turn timings | per-event + nightly |
| Voice TTFA P95 | ≤ 1500 ms (gate) | `Call` turn timings | nightly |
| Barge-in stop latency | ≤ 200 ms | `Call.barge_in_events` | per-event + nightly |
| Tool-augmented TTFA P50 | ≤ 1200 ms (asp.) | `Call` turn timings | nightly |
| Call completion rate | ≥ 90% (asp.) | `Call` end reason | nightly |
| ASR WER | ≤ 12% (asp.) | sampled audio + human transcript | weekly |
| Barge-in correctness (P/R) | P ≥ 0.9 / R ≥ 0.85 (asp.) | `Call.barge_in_events` + human | weekly |
| Intent accuracy | ≥ 92% acc / 0.85 macro-F1 (asp.) | golden + prod sample | per-release + weekly |
| Slot-filling (critical slots) | ≥ 95% exact (asp.) | golden + prod sample | per-release + weekly |
| Lead qualification precision / recall | P ≥ 0.85 / R ≥ 0.80 (asp.) | human labels vs band | weekly |
| False-qualify rate | ≤ 10% (gate) | human labels + `Action` log | weekly |
| Field extraction F1 (numeric/critical) | ≥ 0.95 / ≥ 0.97 (asp.) | golden doc set + prod | per-release + weekly |
| Confidence calibration (ECE) | ECE ≤ 0.05 (asp.) | `ExtractedField.Confidence` + gold | weekly + per-release |
| Missed-abstention (confident-but-wrong) | ≤ 3% (gate) | abstain log + human | weekly |
| Missing-info recall | ≥ 0.90 (asp.) | `MissingItem` vs human | weekly |
| Blocker detection (blocks_quote) | 0 violations (gate) | case state + `MissingItem` | nightly |
| Follow-up success (reply/attempt) | ≥ 25% blended (asp.) | `Action` + inbound | nightly |
| Opt-out rate | ≤ 2% (gate) | `Action` + opt-out events | nightly |
| Anti-spam guardrail adherence | 0 violations (hard gate) | `Action` log + config | per-event + nightly |
| Offer comparison top-1 agreement | ≥ 0.85 (asp.) | golden offers + expert | per-release + weekly |
| Hidden-risk flag recall | ≥ 0.90 (asp.) | `Comparison` + expert | weekly |
| Hallucination (unsupported-claim, machine) | ≤ 1% client-facing; 0 on signing/legal/financial (gate) | Quality Worker + `AuditEvent` | per-event |
| Hallucination (human spot-check) | ≤ 2% (asp.) | human spot-check | weekly |
| Escalation recall | ≥ 0.95 (gate) | escalation events + human | weekly |
| Escalation precision | ≥ 0.70 (asp.) | escalation events + human | weekly |
| Hard-override adherence | 0 misses (hard gate) | `AuditEvent` + escalation | per-event |
| Human approval rate | monitor (70–98% healthy band) | `HumanApproval` outcomes | nightly |
| Decision reversal rate | ≤ 5% (gate for autonomy) | `Action` log + overrides | nightly |
| Close-assist rate | ≥ 60% (asp.) | `AuditEvent` + outcome + human | nightly + weekly |

**Legend:** *(gate)* blocks a release or an autonomy increase; *(hard gate)* is an inviolable
invariant whose breach is a P1; *(asp.)* is aspirational — a goal not yet validated on
production data. Targets without a stated benchmark are engineering goals, marked accordingly,
and are expected to be re-tuned per vertical as golden sets and production data accumulate.
