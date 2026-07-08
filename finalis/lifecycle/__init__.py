"""Finalis Universal Lifecycle Logic — the multi-dimensional business kernel.

A case is not one flat state. It is a LifecycleVector:
  {lead, deal, transaction, fulfillment, customer, support, post_sale}
The existing 17-state machine remains the CASE/operational dimension;
derived outcome views (WON_NOT_FULFILLED, ...) are computed, never stored.

Grounding (design references): Agentic BPM manifesto & formal foundations
(arXiv 2603.18916, 2604.17347) — framed autonomy inside formal process rules;
CMMN — dynamic case management vs. linear workflow; DMN — decision tables
with safe defaults; customer-lifecycle-management — the relationship
outlives the case; win-loss analysis — no silent losses.
"""
