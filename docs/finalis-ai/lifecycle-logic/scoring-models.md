# Lifecycle Scoring Models

**Status: Implemented and tested**, deterministic, all outputs clamped to
[0,1] (or flagged). No fake ML: `deal_win_probability` is labeled a
**heuristic estimate** in code and must be labeled so in any UI.

| Model | Formula (as coded) | Hard rules |
|---|---|---|
| CaseReadinessScore | `1 − min(1, Σ wᵢ·mᵢ)` | any hard-required missing ⇒ can_complete false regardless |
| DealWinProbability | stage_base + 0.1·resp + 0.1·compl + 0.05·fit + 0.05·urgency − 0.15·price_obj − 0.15·no_resp − 0.1·risk, clamped | heuristic until calibrated |
| ExpectedDealValue | `P_win · value · margin` | margin=None ⇒ factor 1.0 **flagged as assumption** |
| RecoveryScore | 0.25·value + 0.20·fit + 0.15·relationship + 0.15·timing + 0.10·engagement + 0.10·margin + 0.05·strategic − penalties | opt-out ⇒ 0 and blocked |
| UpsellScore | 0.25·need + 0.20·satisfaction + 0.15·adjacency + 0.15·timing + 0.10·CLV + 0.10·propensity + 0.05·margin − annoyance | complaint or overdue ⇒ **0** (blocker, not penalty) |
| CLV placeholder | AOV·freq·margin·retention − service_cost | partial data ⇒ partial value + confidence "low" |
| ChurnRisk | 0.25·staleness(180d) + 0.20·complaint + 0.15·no_resp + 0.15·payment + 0.10·satisfaction + 0.10·competitor + 0.05·decline | retention use only, never aggressive sales |
| OutcomeReasonConfidence | quality·reliability·explicitness·recency·consistency (multiplicative) | low ⇒ reason_candidate, not stored as certain |

Property tests (seeded, 200–300 samples each): bounds hold; blockers force 0;
blocked completions always carry reasons + next action.
