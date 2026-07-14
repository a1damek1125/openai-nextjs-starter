# Evidence Bundle

**Status: Implemented and tested** (`evidence.py`).

Every state-changing decision produces an `EvidenceBundle{action_id, case_id,
tenant_id, actor, decision_type, pre_state, post_state, input_facts,
evidence_references, rule_or_playbook_version, confidence,
action_gate_result, human_approval_id?, audit_event_id}`.

`record_decision()` refuses the 10 evidence-required decision types
(close_won, close_lost, complete_case, issue_invoice, mark_payment_received,
schedule_fulfillment, send_high_risk_message, start_recovery_later,
create_upsell_opportunity, reopen_final_case) without evidence references or
a human approval — tested. Recording writes `LIFECYCLE_VECTOR_UPDATED` on the
shared hash chain with pre/post state, confidence, gate result, and playbook
version. Idempotency: duplicate `action_id`s are suppressed (tested).

`UpsellOpportunity` carries its own status machine (DETECTED → READY →
CONTACTED → ACCEPTED/REJECTED, with WAITING_COOLDOWN / BLOCKED_BY_ISSUE /
HUMAN_REVIEW_REQUIRED / EXPIRED); invalid statuses are rejected.
