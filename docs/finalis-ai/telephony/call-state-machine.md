# Call State Machine

Inbound: INBOUND_RINGING → INBOUND_ACCEPTED → CONSENT_REQUESTED →
CONSENT_GRANTED/DECLINED → AI_ACTIVE → (HUMAN_TRANSFER_REQUESTED →
HUMAN_TRANSFERRED | VOICEMAIL_DETECTED) → CALL_COMPLETED/ABANDONED/FAILED.

Outbound: OUTBOUND_REQUESTED → PERMISSION_CHECKED → (SCHEDULED | DIALING) →
RINGING → ANSWERED/VOICEMAIL/BUSY/NO_ANSWER/FAILED → AI_ACTIVE →
(HUMAN_TRANSFERRED) → COMPLETED/RETRY_SCHEDULED/CANCELLED.

**Rules (all tested)**: no call without PERMISSION_CHECKED passing; every
call ends with a disposition from the 16-value set (property-tested across
all scenarios); disposition confidence < 0.70 ⇒ UNKNOWN_REQUIRES_REVIEW +
human review, never silent case updates; every state change writes an audit
event on the shared hash chain.
