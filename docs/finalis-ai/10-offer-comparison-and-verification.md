# Finalis AI — Offer Comparison & Document Verification

> Two tightly-linked capabilities: **Offer Comparator** (compare multiple offers and
> recommend) and **Contract Reality Check** (does this document make business sense?). Both are
> **evidence-based** and **never give final legal advice** — legal/notarial content is flagged
> for human review.

## 1. Offer Comparator

### Inputs
- Two or more `Offer` records (ours, competitors', client-provided), each ideally backed by a
  `Document` (`07`) so fields carry evidence refs and confidence.
- The vertical's `OfferScore` weights from `IndustryPlaybook`.
- Case context + prior agreements (Case Graph) for consistency checks.
- Optional WebScout market data (`08`) for "is this price reasonable?".

### Scoring
`OfferScore = 100·(0.25·Price + 0.20·Scope + 0.15·Warranty + 0.15·Time + 0.10·Payment +
0.10·Risk + 0.05·Service)` (`05` §7), with per-vertical weight overrides:

| Vertical | Emphasis |
|---|---|
| Renovation | Scope, Time |
| HVAC | Warranty, Service |
| Real estate | legal Risk, document completeness |
| Auto workshop | Time, parts/Warranty |

- `Price` is normalized **within the comparison set** (cheapest = 1.0 on that axis), but the
  final recommendation is **value-based**, not "cheapest wins".
- Each axis score is explainable (which fields drove it) and every extracted term links to an
  `EvidenceReference` (page/bbox/snippet) so the owner can verify.

### Output (`Comparison` entity)
1. **Comparison table**: offers × axes (price, scope, warranty, timeline, payment terms,
   exclusions, hidden costs, service, risk, consistency-with-agreement).
2. **Per-offer OfferScore** + per-axis breakdown.
3. **Pros/cons** in plain language.
4. **Hidden-risk flags** (missing service, shorter warranty, exclusions, large upfront
   payment) — each an evidence-linked `RiskFlag`.
5. **Recommendation** with rationale and confidence.

Example:
> "Offer A is 11% cheaper but **excludes service** and has a **shorter warranty (12 vs 24
> mo)** (A p.2 §Warranty; B p.3 §Warranty). Offer B includes install + commissioning +
> inspection (B p.1 §Scope). Before deciding, ask vendor A about service and call-out cost.
> **Recommend B on value; confidence 0.82.**"

### Consistency with earlier agreements
Uses Case Graph edges (e.g. `OFFER_CONTRADICTS_AGREEMENT`): if a new offer changes a price,
deadline, or warranty that was agreed earlier on a call/message, it's flagged with refs to
both the offer and the transcript segment.

## 2. Contract Reality Check (business review, not legal advice)

### What it checks
- **Price** matches the offer/agreement.
- **Deadlines** match what was discussed; are they defined at all?
- **Penalties / liability** — present, symmetric, capped?
- **Payment terms** — safe? (large upfront, no milestones, unclear currency = risk).
- **Warranty** — present and clear?
- **Obligations symmetry** — one-sided terms?
- **Hidden costs** — call-out fees, disposal, materials excluded?
- **Missing attachments / annexes**.
- **Changes vs. earlier terms** — does the contract silently alter what was agreed?

### Scoring
`DocRisk = 100·(0.25·A + 0.20·M + 0.20·C + 0.15·P + 0.10·L + 0.10·Q)` (`05` §5): asymmetry,
missing elements, contradictions, risky payment, risky clauses, and an OCR/scan quality
penalty. `DocRisk ≥ θ_docrisk` → `HUMAN_REVIEW_REQUIRED` with label **"requires human before
signing."**

### Output
For each document:
- Structured fields + confidence + evidence refs (`07`).
- Plain-language summary.
- **Missing elements** (expected but absent).
- **Contradictions** (vs. agreement / other offers / transcript).
- **Risk flags** with severity + evidence.
- **Questions for human/legal/notarial review** when sensitive.
- **Confidence**; if low → request a clearer scan (abstain), never bluff.

Example (evidence-linked):
> "The offer promises a **24-month warranty** (offer p.2) but the draft contract has **no
> warranty clause** (contract pp.1–4; not found). Payment is **80% upfront** (contract §4) —
> higher risk than the milestone schedule discussed on the 3 July call (call 00:41–00:58).
> **DocRisk 68 → human review recommended before signing. Not legal advice.**"

## 3. The hard boundary: never final legal advice

- All contract/notarial/insurance/property analysis is labeled **assistive business review**.
- Legal-sensitivity raises `EscalationScore` (`05` §8); signing decisions are hard-escalated.
- The output format always separates **what we found (with evidence)** from **what we could
  not verify** and **what needs a professional** — supporting, never replacing, human/legal/
  notarial judgment.

## 4. How it plugs into the case

Offer comparison and contract review run in `DOCUMENT_ANALYSIS`/`NEGOTIATION` (`03`), feed the
`DecisionBrief` (`09`) and the Offer Comparison + Document Analysis UI views (`11`), and their
outputs are consumable by the Objection Handler (turn a competitor's weaknesses into a
suggested response) and Quote Builder (position our variant).
