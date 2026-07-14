# Lifecycle Logic — Math & Invariants

**Status: Implemented and tested** (`finalis/lifecycle/`, 63 tests in
`tests/test_lifecycle_logic.py`; 291 repo-wide).

## The LifecycleVector

A case is a vector, not a flat enum (`vector.py`):
`{lead, deal, transaction, fulfillment, customer, support, post_sale}` +
`opted_out`, `consent_valid`. The tested 17-state machine remains the
**case/operational dimension**; outcome states are **derived views**, never
stored:

| deal | payment settled | fulfillment settled | derived view |
|---|---|---|---|
| WON/ACCEPTED | yes | yes | `WON_COMPLETED` |
| WON/ACCEPTED | yes | no | `WON_PAID_NOT_DELIVERED` |
| WON/ACCEPTED | no | — | `WON_NOT_FULFILLED` |
| DECLINED/LOST/EXPIRED | — | — | `LOST_WITH_REASON` (reason enforced) |

`payment settled` ⇔ transaction ∈ {PAID, WAIVED_BY_HUMAN, NO_INVOICE_REQUIRED};
`fulfillment settled` ⇔ fulfillment ∈ {COMPLETED, DELIVERED,
SERVICE_COMPLETED, NOT_REQUIRED}.

## The formal completion rule (`completion.py::can_complete`)

`WON_COMPLETED` requires the conjunction of ALL: deal positive · no blocking
missing items · required documents attached or waived · invoice issued if
required · payment settled if required · fulfillment settled if required ·
contract signed if playbook demands · completion confirmed if playbook
demands · no pending high-risk approval · no open complaint · closure
evidence present. A failed check always returns `blocked_reasons`,
`missing_conditions`, and a `next_best_action` — never a bare "no".

## Hard blockers (override every score)

opt-out · missing consent · open complaint · pending high-risk approval ·
hard-required information missing. Property-tested over 300 random vectors:
a hard blocker ⇒ `can_complete` is false, always.

## Invariants (all tested)

1. **Active-case invariant**: every non-final case has next_action OR
   blocked_reason OR waiting_condition OR human_review_required.
2. **Outcome-reason invariant**: LOST/CANCELLED/DISQUALIFIED/ABANDONED/
   RECOVERY_LATER require reason + category from the taxonomy + evidence or
   human override. No silent closure (randomized over all outcome types).
3. **Evidence invariant**: the 10 state-changing decision types refuse to
   record without evidence references or a human approval.
4. **Idempotency**: duplicate action_ids are suppressed; the audit chain
   stays intact and single.
