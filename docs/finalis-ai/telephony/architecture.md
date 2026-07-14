# Telephony Architecture

```
INBOUND:  number/trunk → provider (LiveKit SIP later | Mock now)
          → CallSession → consent gates → AI_ACTIVE (Voice Engine)
          → Conversation Intelligence → Case Graph → Completion Loop
          → disposition + audit
OUTBOUND: Completion Loop / Action Engine → CallPermissionGate (hard
          blockers) → AntiHarassmentGuard → provider.dial(scenario)
          → disposition + retry decision → case update + audit
```

Components (finalis/telephony/): `models.py` (CallSession/Event/Consent/
ContactCallState/HumanOverride), `gates.py` (CallPermissionGate,
CallPriorityScore, RetryDecision+RetryScore, HumanHandoffScore,
DispositionConfidence, CallQualityScore, AntiHarassmentGuard, campaign
gate), `engine.py` (CallControlEngine + MockTelephonyProvider behind the
TelephonyProvider protocol). Portal endpoints in finalis/portal/app.py;
call_sessions persisted via migration v2.

Scores never override gates (property-tested: perfect CallPriorityScore
still BLOCKs on any hard blocker).
