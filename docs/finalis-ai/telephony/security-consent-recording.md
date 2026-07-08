# Telephony Security, Consent & Overrides

All **Implemented and tested** unless marked otherwise.

- **Consent is three separate decisions**: recording / transcription /
  analytics. Declined recording ⇒ no audio stored (recording_uri stays
  null); declined_all ⇒ no transcript processing either.
- **AI self-identification**: outbound answered calls emit an AI_DISCLOSURE
  event with the transparent Polish greeting; the AI never poses as human.
- **Emergency**: never continues intake/sales — immediate escalation
  disposition + handoff (tested: analysis is NOT run).
- **Voicemail hygiene**: short, no invoices/contracts/sensitive details
  (tested against the message text).
- **Identity verification gate**: sensitive topics (payment/contract/...)
  without verified identity are hard-blocked; verified ⇒ still
  REQUIRE_HUMAN_APPROVAL.
- **Anti-harassment guard**: 2 calls/contact/day, 3/sequence, 4h cooldown,
  2 voicemails max, stop after repeated no-answer; every block audited.
- **Bulk campaigns disabled** unless compliance setup + human approval exist.
- **Human overrides** (3 levels): SOFT (manager+), HARD (owner/admin/
  compliance), NON_OVERRIDEABLE (opt-out, DNC, refusal, wrong-number
  auto-call, recording-without-consent, emergency-to-sales, sensitive-
  without-identity, bulk-without-compliance — cannot be bypassed in product
  UI, parameterized-tested). Overrides need real user + role + reason, are
  one-time by default, fully audited (REQUESTED/APPROVED/REJECTED/APPLIED/
  NON_OVERRIDEABLE_CONFIRMED events). AI cannot approve its own actions.
