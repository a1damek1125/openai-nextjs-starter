# FINALIS Control Independence Model (SP0005 D-0005-36/37/38)

Two controls are NOT automatically independent barriers (INV-0005-12). Independence
is classified over shared failure domains — `model`, `provider`, `prompt`,
`policy_engine`, `data`, `human`, `code_path`:

| Classification | Condition |
|---|---|
| `INDEPENDENCE_ESTABLISHED` | no shared failure domain and no UNKNOWN domain |
| `INDEPENDENCE_NOT_ESTABLISHED` | at least one shared actual failure domain |
| `UNKNOWN` | a domain is UNKNOWN for either control (cannot prove independence) |

A control positively declaring `NONE` for a domain (it does not depend on it) is
neither a shared failure point nor unknown. **No naive probability multiplication**
(D-0005-38): `P(F1 ∩ F2) ≠ P(F1)·P(F2)` without established independence. Minimal
control cut-sets are enumerated structurally on bounded graphs and report
`ANALYSIS_LIMIT_REACHED` honestly (D-0005-39, AC-0005-084).
