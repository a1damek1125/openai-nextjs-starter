# Decision Tables (DMN-style)

**Status: Implemented and tested** (`decisions.py`). Safe default everywhere:
an unknown action/combination returns **REQUIRE_HUMAN_REVIEW** — ambiguity
never auto-executes.

| Table | Inputs | Outcomes | Key rules (tested) |
|---|---|---|---|
| `can_ai_send` | action, playbook, vector | ALLOW/BLOCK/RHR | opt-out or no-consent → BLOCK; prohibited list → BLOCK; allowed list → ALLOW; else RHR |
| `requires_human_approval` | decision type + flags | bool | playbook rule list; low confidence or angry client → always; close_lost + high value → yes |
| `can_complete` | CaseFacts, playbook | ok + reasons + NBA | see math-and-invariants |
| `upsell_allowed` | vector, playbook, days | ALLOW/BLOCK/RHR | complaint → BLOCK; overdue payment → BLOCK; value not delivered → BLOCK; cooldown → BLOCK; high-value rule → RHR |
| `recovery_eligible` | reason, playbook, vector | bool | opt-out/consent-expired/anger/refusal → false; else reason ∈ playbook eligible list |
| `followup_allowed` | vector, attempts | ALLOW/BLOCK | opt-out → BLOCK; attempts ≥ max → BLOCK |
| `outcome_reason_required` | outcome type | bool | the 5 reason-required types |
| payment/fulfillment required | playbook flags | bool | explicit per playbook; contradiction (payment w/o invoice) refused at validation |
