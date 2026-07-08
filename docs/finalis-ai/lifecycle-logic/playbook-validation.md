# Vertical Playbook Contract & Validation

**Status: Implemented and tested** (`playbooks.py`).

The `VerticalPlaybook` dataclass is the machine-readable contract: case
types, required information (with weights + hard_required), documents,
invoice/payment/fulfillment/appointment/contract/confirmation requirements,
human-approval rules, allowed/prohibited AI actions, loss-reason taxonomy,
recovery/upsell/post-sale rules, cadence, retention, evidence requirements,
version.

`validate_playbook()` machine-checks 15 rule classes: completeness,
weight bounds, taxonomy membership, **contradictions** (payment without
invoice; actions both allowed and prohibited), **spam guards** (cadence
attempts ≤ 10), explicit consent policy, evidence requirements.
`activate_playbook()` **refuses** an invalid playbook (raises) — tested.

Five base playbooks ship validated: `hvac_home_services` (detailed:
appointment + confirmation + maintenance/seasonal post-sale),
`generic_service_business`, `product_sale` (delivery, no appointment),
`b2b_sales` (signed contract required), `property_management` (no
invoice/payment, tenant confirmation required).
