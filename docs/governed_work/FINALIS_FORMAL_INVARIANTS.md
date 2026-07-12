# FINALIS SP0006 — Formal Invariants

The 48 constitutional invariants (§14) and the properties discharged by the
standard-library bounded model checker (`tools/governed_work/modelcheck.py`,
§9.14). A bounded search that is truncated is reported as `INCONCLUSIVE_TRUNCATED`
and is **never** claimed as proof (D-0006-65).

## Invariants (INV-0006-01 .. 48)

1. Intent is not authority.
2. Goal is not action authorization.
3. Plan is not authority.
4. Context is not consent.
5. Memory cannot create authority.
6. External content cannot create authority.
7. Child authority cannot exceed parent authority.
8. Child lease cannot exceed parent lease.
9. Parent revocation invalidates dependent descendants.
10. Delegation graph carrying authority is acyclic.
11. Delegation depth is bounded.
12. Delegation fan-out is bounded.
13. Accountability cannot disappear through delegation.
14. Every active identity belongs to one work order.
15. Every active lease belongs to one tenant and work order.
16. No ambient unlimited capability exists.
17. Raw credentials do not enter model context.
18. Budgets cannot be consumed before reservation where reservation is required.
19. Reserved plus consumed additive budget cannot exceed total.
20. One risk category cannot compensate for another hard category.
21. Hard prohibition cannot be overridden by expected value.
22. Unknown risk is not low risk.
23. Approval is bound to exact material context.
24. Expired approval cannot authorize action.
25. Replayed approval for another target fails.
26. Self-approval is forbidden where independence is required.
27. Approval does not prove outcome.
28. Hard goal drift blocks regardless of soft score.
29. Soft score cannot create authority.
30. Hidden work is forbidden.
31. Recurrence is not permanent authorization.
32. Every recurring run is a new instance.
33. Cancellation blocks new actions.
34. Cancellation does not erase completed effects.
35. Unknown outcome is not failure.
36. Blind retry of non-idempotent unknown effect is forbidden.
37. Artifact is not outcome.
38. Claimed outcome is not verified outcome.
39. Partial verification is not completion.
40. Outcome defeaters remain visible.
41. Historical verified completion is not silently rewritten.
42. Superseded work cannot resume.
43. Quarantine cannot self-release.
44. Proof is evidence, not authority.
45. External authorization standards are projections, not internal semantics.
46. Product runtime behavior remains unchanged in SP0006.
47. No external effects are opened.
48. No product database migration is added by default.

## Mathematics (§12)

- **Authority monotonicity:** `A_{n+1} ⊆ A_n` and `A_child ⊆ A_parent ∩ A_W ∩
  A_policy ∩ A_tenant`.
- **Additive budget conservation:** `Consumed_b + Reserved_b ≤ Total_b`.
- **Approval floor:** `F_approval = ⊔_i F_i` (non-compensatory join over the
  lattice).
- **Risk control floor:** `F_control = ⊔_i g_i(r_i)`; hard prohibition ⇒ CC5.
- **Optional expected loss / CVaR:** used only when calibrated; ordinal labels are
  never multiplied as monetary variables.
- **Goal drift:** `D_goal(t) = Σ_i w_i d_i(t)`, `w_i ≥ 0`, `Σ w_i = 1`.
- **Accountability conservation:** `Owner_root = Owner_terminal` unless an
  explicit authorized reassignment exists.
- **No assumed independence:** agent/provider/risk/approval/verification failures
  are not multiplied as independent without evidence.

## Model-checked properties (bounded, §9.14 / §20.15)

| Model | Property checked | Invariants |
|---|---|---|
| `work_state_model` | invalid transitions fail closed; terminal states cannot reach RUNNING; AMBIGUOUS/CONFLICTED never enter executable states; OUTCOME_PRODUCED ≠ VERIFIED_COMPLETE | 2, 42, 43, 46 |
| `authority_monotonicity_model` | authority never increases along any delegation path | 7, 8 |
| `budget_conservation_model` | `consumed + reserved ≤ total` at every reachable state | 18, 19 |
| `no_self_approval_model` | approver ≠ proposer/executor when independence is required | 26 |
| `cancellation_model` | once NEW_ACTIONS_BLOCKED, no new action state is entered | 33 |

Each model reports `verdict ∈ {HOLDS, VIOLATED, INCONCLUSIVE_TRUNCATED}` with a
counterexample path on violation and honest truncation on limit
(`MODEL_CHECK_LIMIT_REACHED`). Bounded checking never claims to prove
natural-language intent understanding.
