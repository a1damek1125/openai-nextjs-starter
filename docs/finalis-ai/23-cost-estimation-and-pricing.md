# Finalis AI — Cost Estimation Logic & Pricing Model

> This doc defines the **unit cost model** (what a case costs us to run), a **worked example**
> (typical HVAC case), **per-tenant COGS and gross margin** vs. the pricing tiers of `00` §8,
> the **cost-control mechanisms**, and the **pricing recap**.
>
> **Honesty rule for this entire document**: every vendor rate below is an **[ESTIMATE]** —
> a plausible mid-2026 range, *not* a quoted price. Token, STT, TTS, telephony, and WhatsApp
> prices change quarterly (often faster). **All rates must be refreshed against current vendor
> price lists at build time**, and then kept live in a `CostRateCard` config (see §4), not
> hard-coded. Vendor prices are typically in USD while our tiers are in EUR; for planning we
> assume rough parity (≈1 USD ≈ 0.9–1.0 EUR) and treat FX as another rate-card entry.

## 1. Unit cost model — cost drivers per case

A case's marginal cost is the sum of six drivers. Each has a formula with parametrized rates
(`R_*`), so the same model runs in planning spreadsheets *and* in the runtime metering service
(`CostEvent` rows per tenant/case, §4).

### 1.1 Voice (the dominant driver)

Cascaded pipeline (`06`): telephony + streaming STT + LLM turns + streaming TTS.

```
Cost_voice_per_min = R_telephony + R_stt + Cost_llm_per_min + Cost_tts_per_min

Cost_llm_per_min  = turns_per_min × (tok_in_per_turn × R_llm_in + tok_out_per_turn × R_llm_out)
Cost_tts_per_min  = agent_talk_ratio × chars_per_spoken_min × R_tts_per_char
```

| Parameter | Value / range | Status |
|---|---|---|
| `R_telephony` (inbound PSTN/SIP, per min) | $0.005–0.02 | [ESTIMATE] |
| `R_stt` (streaming STT, per audio min) | $0.004–0.015 | [ESTIMATE] |
| `turns_per_min` (agent turns) | 2–3 | assumption (short-answer policy, `06` §2) |
| `tok_in_per_turn` (context + transcript + tools) | 1,500–3,000 | assumption; grows with call length unless context is windowed |
| `tok_out_per_turn` | 50–120 | assumption (1–2 sentence answers) |
| `R_llm_in` / `R_llm_out` (mid-tier model, per 1M tok) | $0.1–1 / $0.5–5 | [ESTIMATE] — tier-dependent, changes fast |
| `agent_talk_ratio` | 0.4–0.5 | assumption |
| `chars_per_spoken_min` | ~750–900 | ≈150–180 wpm × ~5 chars/word |
| `R_tts_per_char` | $0.000015–0.00015 (i.e. $15–150 / 1M chars) | [ESTIMATE] — commodity vs. premium voices span ~10× |

**Resulting band**: `Cost_voice_per_min ≈ $0.03–0.20`, with a realistic mid-market build at
**~$0.05–0.10/min**. The ~7× spread is real: premium TTS + frontier LLM lands near the top;
commodity TTS + mid-tier LLM + self-hosted STT lands near the bottom. This single parameter
dominates all margin math (§3.3), so it gets the tightest metering and the most routing
attention (§4).

*(Realtime speech-to-speech models, the `06` fallback adapter, are priced per audio+text token
and were historically **more** expensive per minute than a tuned cascade — re-verify at build
time before routing any volume there.)*

### 1.2 Messaging (WhatsApp / SMS)

```
Cost_msg = Meta/carrier fees + LLM handling
         = (n_template × R_wa_template) + (n_session_windows × R_wa_service)
         + (n_sms_segments × R_sms)
         + n_inbound × (tok_classify × R_llm_small + tok_reply × R_llm_mid)
```

| Parameter | Value / range | Status |
|---|---|---|
| `R_wa_template` (utility/marketing template msg, EU) | €0.01–0.08 each | [ESTIMATE] — Meta pricing is per-message, category- and country-tiered, and has been restructured more than once; **must** be re-read at build time |
| `R_wa_service` (service conversation, user-initiated 24 h window) | €0.00–0.03 | [ESTIMATE] — service conversations have been free in many regions, but verify |
| `R_sms` (per 160-char segment, EU) | €0.01–0.10 | [ESTIMATE] — highly country-dependent; long messages multi-segment |
| LLM handling per inbound message (classify + draft reply) | 500–2,000 tok → $0.0005–0.005 | [ESTIMATE] |

**Rule of thumb**: a WhatsApp-mediated case exchange of ~10–15 messages costs **€0.02–0.20**
in fees + LLM — messaging is cheap relative to voice; the design should *prefer* async
messaging for follow-ups wherever the playbook allows.

### 1.3 Documents (OCR + analysis)

```
Cost_doc = pages × R_ocr_per_page + pages × tok_analysis_per_page × R_llm_analysis
```

| Parameter | Value / range | Status |
|---|---|---|
| `R_ocr_per_page` — **self-hosted olmOCR** | **~$0.0002/page** (paper reports ~1M PDF pages for ~$190) | [snippet-sourced] (`07` §2 cost anchor); assumes amortized GPU at volume — at low volume the per-page cost is dominated by idle GPU time |
| `R_ocr_per_page` — managed VLM / cloud OCR API | $0.001–0.01/page | [ESTIMATE] — frontier VLM OCR was reported >$6/1k pages (>$6,240/M, `07`), managed doc-AI APIs sit between |
| `tok_analysis_per_page` (extraction + risk/contradiction pass) | 1,500–3,000 in + 200–500 out | assumption |
| Analysis model | mid-tier for field extraction; **frontier only** for contract/offer risk analysis | routing policy (§4) |
| `Cost_analysis_per_page` | $0.002–0.02 | [ESTIMATE], model-tier-dependent |

**Net**: a typical page costs **$0.002–0.03 all-in**; OCR itself is a rounding error once
self-hosted — **LLM analysis tokens, not OCR, are the document cost driver**. Photos (boiler
labels, site photos) count as 1 "page" each through the VLM path.

### 1.4 WebScout

```
Cost_webscout = pages_fetched × (R_fetch + tok_extract_per_page × R_llm_mid)
```

- `pages_fetched`: 5–15 per research task (assumption; capped by policy, `08`).
- `R_fetch`: ~$0 self-fetched, or $0.001–0.01/page via a search/scrape API [ESTIMATE].
- `tok_extract_per_page`: 2,000–5,000 → $0.002–0.01/page on a mid-tier model [ESTIMATE].
- **Per research task: ~$0.02–0.15** [ESTIMATE]. Business-tier only, so low blast radius.

### 1.5 Scoring / orchestration overhead

Every case event (message in, call ended, doc arrived, timer fired) triggers small-model work:
intent classification, NBA utility scoring inputs, escalation scoring, promise/missing-item
extraction deltas (`05`, `09`).

```
Cost_orchestration = events_per_case × tok_per_event × R_llm_small
```

- `events_per_case`: 20–60 (assumption); `tok_per_event`: 300–1,500.
- `R_llm_small` (cheap/fast tier): $0.02–0.20 per 1M in [ESTIMATE].
- **Per case: ~$0.005–0.05.** Individually negligible — but it's the driver that silently
  explodes if an event loop misfires, hence the anomaly alerts in §4.

### 1.6 Infra baseline (per tenant, amortized)

Postgres + pgvector, S3 storage, workers/queues, observability, self-hosted OCR GPU share:

```
Cost_infra_per_tenant_month ≈ (shared_infra_month / active_tenants) + tenant_storage × R_s3
```

- At early scale (≤50 tenants): **€8–20/tenant/month** [ESTIMATE] (fixed costs poorly amortized).
- At ≥200 tenants: **€3–8/tenant/month** [ESTIMATE].
- Storage itself is trivial (a case's docs+audio ≈ tens of MB; S3 ≈ $0.02/GB-month [ESTIMATE]).

## 2. Worked example — "typical HVAC case"

**Case profile**: 1× 6-min inbound call + 12 WhatsApp messages (6 inbound / 6 outbound, ~2
conversation windows, 2 template sends) + 3 photos analyzed + 1 PDF offer (5 pages) analyzed +
3 follow-ups (2 WhatsApp templates + 1 SMS) + 1 decision brief + orchestration.

| Driver | Arithmetic (low) | Arithmetic (high) | Low | High |
|---|---|---|---|---|
| Voice: 6 min | 6 × $0.03 | 6 × $0.20 | $0.18 | $1.20 |
| WhatsApp fees: 2 templates + 2 windows | 2×€0.01 + 2×€0.00 | 2×€0.08 + 2×€0.03 | $0.02 | $0.22 |
| Msg LLM handling: 6 inbound | 6 × $0.0005 | 6 × $0.005 | $0.003 | $0.03 |
| Photos: 3 × VLM analysis | 3 × $0.002 | 3 × $0.02 | $0.006 | $0.06 |
| PDF offer: 5 pg OCR + analysis (frontier risk pass) | 5×$0.0002 + $0.02 | 5×$0.01 + $0.10 | $0.02 | $0.15 |
| Follow-ups: 2 templates + 1 SMS + drafting | 2×€0.01 + €0.01 + $0.002 | 2×€0.08 + €0.10 + $0.01 | $0.03 | $0.27 |
| Decision brief (frontier: ~8k in / 1k out) | ~$0.03 | ~$0.12 | $0.03 | $0.12 |
| Orchestration/scoring (~40 events) | $0.005 | $0.05 | $0.005 | $0.05 |
| **Total per case** | | | **≈ $0.30** | **≈ $2.10** |

**Estimated cost band: ~€0.30–2.00 per typical case**, realistic mid ≈ **€0.60–0.90**.
Voice is 55–60% of it; the brief + offer analysis (the frontier-model calls) are the next
block. A messaging-only case (no call) costs **~€0.10–0.60**. All figures inherit the
[ESTIMATE] rates above — re-run this table when the rate card is filled in.

## 3. Cost per tenant per month vs. pricing tiers (`00` §8)

### 3.1 Usage assumptions per tier (planning hypotheses — validate in beta)

| Assumption | Start | Pro | Business |
|---|---|---|---|
| Cases / month | 30 | 120 | 400 |
| Voice minutes / month | 100 | 500 | 2,000 |
| WhatsApp/SMS messages / month | 300 | 1,500 | 5,000 |
| Doc pages + photos / month | 30 | 200 | 800 |
| Decision briefs / month | 15 | 100 | 400 |
| WebScout tasks / month | 0 | 0 (WebScout is Business-tier — `00` §8) | 80 |
| Infra baseline | €8 | €10 | €15 |

### 3.2 COGS and gross margin (using §1 rate bands)

| Cost line | Start (low–high) | Pro (low–high) | Business (low–high) |
|---|---|---|---|
| Voice (min × $0.03–0.20) | €3–20 | €15–100 | €60–400 |
| Messaging (fees + LLM) | €2–8 | €8–35 | €25–110 |
| Documents | €0.1–1 | €1–6 | €3–24 |
| Briefs (× $0.03–0.12) | €0.5–2 | €3–12 | €12–48 |
| WebScout | — | — (Business-tier only, `00` §8) | €2–12 |
| Orchestration | €0.2–1.5 | €1–6 | €2–20 |
| Infra | €8 | €10 | €15 |
| **COGS / tenant / month** | **€14–41** | **€38–170** | **€119–629** |
| Tier price (`00` §8) | €99–149 | €299–499 | €799–1,499 |
| **Gross margin** | **59–91%** | **43–92%** | **21–92%** |
| Margin at mid COGS / mid price | **~78%** | **~74%** | **~67%** |

*(Adjustment note: Pro WebScout was previously budgeted at 10 tasks/€0.2–1.5; zeroed to match
`00` §8 tier gating — Pro COGS high end drops €171 → €170, margins unchanged at this rounding.)*

Read: at mid-band rates every tier clears the **~70% gross margin** a SaaS needs; only the
worst case (top-of-band voice rates *and* bottom-of-tier price *and* heavy usage) dips below,
and only in Business — which is exactly why overages exist (§5).

### 3.3 Margin sensitivity to voice minutes (the dominant driver)

Gross margin at **mid-tier price** as `Cost_voice_per_min` moves (all other lines at mid):

| Voice cost/min | Start (€124, 100 min) | Pro (€399, 500 min) | Business (€1,149, 2,000 min) |
|---|---|---|---|
| $0.05 | ~83% | ~83% | ~83% |
| $0.10 | ~79% | ~77% | ~74% |
| $0.15 | ~75% | ~71% | ~66% |
| $0.20 | ~71% | ~64% | ~57% |

Two conclusions: **(a)** getting the voice stack from $0.20 → $0.05/min is worth ~15–25 margin
points at Business scale — component choice (commodity TTS, mid-tier LLM, self-hosted STT at
volume) is a first-order business decision, not a tech detail; **(b)** included-minutes caps
per tier + metered overage (§5) are mandatory, or a single call-heavy tenant at $0.20/min can
push its account to near-zero margin.

## 4. Cost controls

1. **Per-tenant metering + budgets.** Every LLM call, minute, message, and page writes a
   `CostEvent{tenant, case, driver, units, rate_version, cost}`; a live `CostRateCard` (the
   §1 rates, versioned, refreshed from vendor price lists) converts units → money. Tenant
   budgets: soft cap → alert; hard cap → degrade gracefully (queue non-urgent work, shorten
   calls, defer WebScout) — never silently drop a client-facing obligation.
2. **Model routing (biggest lever after voice stack choice).** Cheap/small models for intent
   classification, routing, scoring, message drafting; mid-tier for extraction and voice
   turns; **frontier only** for decision briefs, offer risk/contradiction analysis, and
   escalation-grade reasoning. Mirrors the OCR routing policy of `07` §2.
3. **Caching.** Prompt/context caching for the per-turn voice context (the same
   `BusinessProfile` + playbook prefix repeats every turn — cache-read pricing is typically a
   fraction of input pricing [ESTIMATE, verify]); memoize document analyses (hash the file —
   the same PDF re-sent costs €0); cache WebScout page extractions per URL+day.
4. **Self-hosted OCR at volume.** The olmOCR anchor (~$0.0002/page [snippet-sourced], `07`)
   vs. managed VLM ($0.001–0.01 [ESTIMATE]) says: start managed for simplicity, move OCR
   in-house once page volume amortizes a GPU — also a privacy selling point (`07` §7).
5. **Call-length + token budgets.** Per-tier max call minutes and per-call soft limit (e.g.
   wrap-up prompt at 8 min, offer callback at 12 — thresholds per playbook); token budget per
   worker invocation (a brief gets N tokens, a classifier gets M); context windowing on long
   calls so `tok_in_per_turn` doesn't grow unboundedly.
6. **Anomaly alerts (ties to Evaluation Lab, `15`).** Alert on: cost/case > p95 baseline,
   event-loop storms (orchestration events/case spiking), retry storms on a vendor, a tenant's
   daily burn > k× its trailing average, and rate-card drift (vendor invoice ≠ metered
   estimate). Cost-per-case and margin-per-tenant become standing Evaluation Lab dashboards
   next to quality metrics.

## 5. Pricing model recap + rationale

- **Value-based, not token-based** (`00` §8): buyers are owners of HVAC/plumbing/renovation
  firms; they buy *recovered leads and closed cases*, and reject token math. Price on
  outcomes/capacity (tier + included usage), meter internally.
- **Tier table** — unchanged from `00` §8 (indicative, validate in beta): Start €99–149 ·
  Pro €299–499 · Business €799–1,499 · Enterprise €2,500+.
- **Included usage + overage (suggestion)**: each tier includes the §3.1 usage profile
  (headline: included voice minutes — e.g. Start 100 / Pro 500 / Business 2,000). Overage
  sold as **bundles, not per-token**: e.g. **+€25 per extra 100 voice minutes** [suggestion —
  ~2–8× marginal cost at §1 bands, keeps overage margin-positive at any rate realization];
  analogous small bundles for messages and doc pages. Bundles keep the invoice legible and
  protect margin from the §3.3 tail without ever surprising a customer mid-case.
- **Annual discount**: ~15–20% for annual prepay [suggestion] — funds CAC payback and locks in
  the usage-learning period.
- **Pilot pricing (Phase 2 beta)**: design partners at **~50% of target tier for 3 months**
  (or free month 1 + 50% months 2–3) in exchange for case data access (anonymized), weekly
  feedback, and a case study — explicitly framed as pilot pricing that steps up to list, so
  the discount doesn't anchor the market price. Beta's job is to measure **realized ROI
  (€ recovered pipeline per tenant)** and reprice tiers against it (`00` §8 caveat).

## 6. Honesty & maintenance

- **Every vendor rate in this document is an [ESTIMATE] range**, except the olmOCR
  ~$190/M-pages figure which is [snippet-sourced] from the paper abstract (`07` §2) and should
  itself be re-validated on our own hardware. No number here is a quoted price.
- Token/STT/TTS/telephony/WhatsApp prices change quickly (sometimes monthly) and vary by
  region, currency, and volume commitments. **At build time**: fill the `CostRateCard` from
  current vendor price lists, re-run §2 and §3, and re-check the §3.3 sensitivity before
  committing to included-usage numbers in contracts.
- The usage profiles in §3.1 are hypotheses; replace them with observed beta telemetry
  (Evaluation Lab) before Phase 3 pricing is finalized.
- FX (USD vendor costs vs. EUR pricing) is treated as ≈ parity here; carry it as an explicit
  rate-card entry, not an assumption.
