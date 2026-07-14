# Action & Communication Engine — LGGT / ProofGate Placeholder

> Consistent with `32-lggt-certainty-core-integration-plan.md` (normative plan) and
> `44-lggt-integration-decision.md` (Option B decision record: placeholder now, runtime
> later; LGGT can only tighten, never loosen; one seam — `CertaintyCoreAdapter`; no MVP
> dependency on LGGT availability). This file maps that plan onto the Action &
> Communication Engine as coded on branch `claude/finalis-action-communication-engine`.

---

## 1. What exists here today (Phase 1)

### Rule-based ActionGate — Implemented and tested

`finalis/case_services.py::ActionGateService` ("Rule-based gate (Phase-1; LGGT ProofGate
strengthens it later)" — the docstring is the contract). The ACE calls it on **every
client-facing action** at `engine.handle` step 3:

```python
gate_action = ("send_out_of_rule_price"
               if request.action_type in HIGH_RISK_ACTION_TYPES
               else "send_follow_up")
decision = self.gate.evaluate(case, gate_action,
                              confidence=request.payload.get("confidence", 1.0),
                              audit=self.audit)
```

Phase-1 rules, in order: opted-out case blocks all `send_/call_/ask_` (tested `test_3`);
`HIGH_RISK`/`ALWAYS_HITL` → `REQUIRE_HUMAN_APPROVAL` (tested `test_4`, `test_19`);
`confidence < 0.5` → `ABSTAIN_MISSING_DATA`; autonomy ≤ L2 → approval; `AUTO_OK`
allowlist → `ALLOW` (tested `test_2`); unknown action → conservative approval default.
Every evaluation writes its own audit event and **`GateDecision.audit_id` is already
returned** — set to the id of that event on the tamper-evident chain. This is exactly
the `audit_id` join LGGT certificates bind to (`32` §2.8): the certifiable identifier
space exists in the ACE today, for free.

### Shared certainty seam — available (from the case-graph scaffold)

`finalis/certainty_core.py` (Phase 1 already executed, per `44` §2) provides the
**`CertaintyCoreAdapter` protocol**, the **`NullAdapter`** (stamps `mode=heuristic` +
`audit_id`, ~40 lines, calls nothing external), **`Fact`/FactBuilder** (entity →
fact-record mapping), and the **`Certificate`** schema (decision_ref, facts,
policy_version, verdict `certified|heuristic|abstained`, confidence, audit_id,
proof_blob). The ACE does not import any of it yet — correct per the one-seam guardrail;
wiring happens at the gate, below.

### ActionFactBuilder — Designed mapping

The ACE-specific fact builder (Phase 2 prerequisite): build `Fact` records from
`ActionRequest` + `MessageDraft` + engine state so a certifier can check outbound
actions. Designed mapping (no code yet):

| Fact predicate | From (as coded) |
|---|---|
| `action.type` / `action.risk_level` / `action.reason` / `action.source` | `ActionRequest` fields |
| `action.confidence` | `request.payload["confidence"]` (the value the gate already consumes) |
| `contact.opted_out[channel]` | `ConsentPreference` rows + `Case.opted_out` |
| `contact.do_not_contact` / `contact.time_window` | `ChannelPreference` |
| `rate.attempts` / `rate.last_touch_at` / `rate.paused_client_replied` | `RateLimitSpamGuard._history` / `_paused_cases` |
| `draft.text_hash` / `draft.forbidden_scan=pass` | `MessageDraft` + composer guard result |
| `upload.purpose` / `upload.expires_at` | `UploadLink` |
| `case.state` / `case.autonomy_level` / `case.missing_items[*]` | `Case` aggregate |

Provenance/confidence/timestamp discipline follows `32` §2.2; every field above already
exists on a coded entity, so the mapping is lossless (the Option-B "no data-shape drift"
obligation is satisfied).

---

## 2. Phase 2 — certify selected ACE actions

Per `32`/`44` Phase 2 (real adapter + PolicyCompiler + gate enforcing verdicts;
fail → HumanApproval, never silent; outage degrades to heuristic + alert, never blocks
the loop; P95 ≤ 250 ms off the voice path; per-tenant kill switch). The certified
classes, **each mapped to the exact code hook in this engine**:

| # | Certified claim | Code hook (as implemented today) |
|---|---|---|
| 1 | **Follow-up permission** — this outbound touch violates no hard guarantee (quiet hours, min interval, max attempts, opt-out) | The `gate.evaluate` call site in `engine.handle` (step 3), evaluated over facts from `ConsentPermissionService.check` + `RateLimitSpamGuard.check` (steps 5–6). Phase 2 wraps steps 3–6 in one certified verdict; the heuristic checks remain as the floor (LGGT only tightens). |
| 2 | **Safe message sending** — the draft contains no invented price/over-promise/legal content and matches an approved template | `MessageComposer.compose` result, certified immediately before `engine._send` dispatches `novu.send` — the last point the text can change (`draft.final_text`, i.e. after any human edit). A `fail` verdict routes to the approval queue, exactly the existing `pending_approval` path. |
| 3 | **Missing-info request validity** — the `ask_for_missing_info` / `send_photo_request` is playbook-justified and not already satisfied by held evidence | The same `gate.evaluate` site, with facts from `Case.missing_items` (the `MissingItem` rows that `MissingInfoService.resolve` clears — see `test_17`). Certifies "this item is still open and blocks the quote" before asking the client. |
| 4 | **Human approval requirement** — the decision to require (or not require) approval matches policy | The branch in `engine.handle` step 9 (`decision.outcome == "REQUIRE_HUMAN_APPROVAL" or request.risk_level == "high"`) plus `decide_approval` — certifies both that high-risk actions were queued and that an approval grant came from an authorized human (joins the RBAC rule in `enterprise-controls.md` §2). |
| 5 | **Action blocking** — every block was justified and every justified block happened | The three block emitters: gate `BLOCK`/`ABSTAIN` (step 3), `ACTION_GATE_BLOCK` (steps 4–5: no channel / consent), `FOLLOW_UP_RATE_LIMITED` (step 6). Certificates over blocks make "the AI never contacted an opted-out client" externally provable, not just tested. |
| 6 | **Case transition after client response** — the state change triggered by a reply/upload is legal and evidence-backed | `engine.record_delivery` on `status="replied"` (which also pauses cadence via `rate.client_replied`) and the `UploadLinkGenerator.use` → `MissingInfoService.resolve` chain (`test_17`). Certifies the transition the Case Graph makes in response, per `03` §4 legality. |

Classes 1, 3 and 6 correspond directly to `32` §3 Phase-2 classes (follow-up permission,
missing-info validity, case transitions); 2, 4 and 5 are the ACE-specific projections of
the same certified-outbound principle. Every certificate binds to the `audit_id` the
gate already returns; no new identifier machinery is needed.

Wiring plan: the adapter is injected into `ActionCommunicationEngine.__init__` next to
the other services (`self.certainty = adapter or NullAdapter(audit)`), called at the
hooks above; `NullAdapter` keeps Phase-1 behavior bit-identical (stamp only), which is
the regression gate for the swap.

---

## 3. Phase 3 — full ProofGate for all critical outbound actions

Per `32`/`44` Phase 3: certification becomes **mandatory** for the critical set — in ACE
terms, everything in `HIGH_RISK_ACTION_TYPES` (`close_case_won`, `close_case_lost`,
`send_quote_status_update_with_price`, `send_price_negotiation`,
`send_contract_response`) plus any L4/L5 autonomous send. **No `pass` certificate ⇒
automatic HumanApproval** — the engine already has that exact degradation path coded
(the `pending_approval` branch), so "LGGT outage converts critical autonomy to HITL,
never to unsafe execution and never to a dropped case" is a one-line routing change,
not new machinery. Acceptance criteria as in `32` §3 Phase 3: zero uncertified critical
sends, external auditor re-verifies a sampled month from AuditEvents + certificates +
policy versions, certified reversal rate ≤ heuristic, tenant-facing "why + proof"
rendering.

## 4. Guardrails (restated, binding on this engine)

- **No MVP dependency**: the ACE ships and passes all 25 tests with LGGT nonexistent.
- **One seam**: only `CertaintyCoreAdapter` may be imported; a second import path in
  `finalis/actions/` is a defect.
- **Tighten-only**: a certificate may add approvals/abstentions; it may never authorize
  a send that the gate, consent stack, or rate limiter would block.
- **Honest labeling**: `mode: heuristic` vs `certified` surfaces wherever the draft or
  decision is shown.
