# Edge Cases — Covered Battery

All tested in `tests/test_lifecycle_logic.py` (TestEdgeCases + related):

accepted-but-never-pays (→ await_payment) · deposit-paid-then-cancelled
(CANCELLED with reason+evidence) · paid-but-not-delivered blocks completion ·
service-done-but-unpaid blocks completion · payment-failed → retry_payment ·
competitor-chosen with reason (not recovery-eligible by default taxonomy) ·
reason-refused → LOST unknown_reason with human override · no-response →
followup_allowed BLOCK at max attempts · opt-out kills recovery + follow-up +
upsell (three separate tests) · open complaint blocks upsell AND closure;
resolved complaint re-evaluates · product sale (delivery, no appointment)
completes · B2B requires signed contract · property management requires
tenant confirmation, no payment · playbook version recorded in closure audit
· refund and reopen-final-case require human approval · partial data CLV →
low confidence · duplicate decision suppressed (idempotency).

Property-tested (seeded randomized, 700 total samples): hard blockers always
block; blocked checks always explain; ok ⇒ WON_COMPLETED view; reason-required
outcomes never close silently; upsell never fires with blockers.

Remaining heuristic (not enforced math): win-probability calibration,
CLV inputs, churn-signal extraction — all labeled as such in code.
