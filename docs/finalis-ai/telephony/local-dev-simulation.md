# Local Telephony Simulation

No phone number, trunk, or provider needed.

API (portal, auth required):
- `POST /telephony/inbound/simulate` — body: caller_number, segments
  (diarized), recording_consent (granted|declined|declined_all),
  emergency, asks_for_human. Creates CallSession + NEW_CONTACT case (or
  attaches to the known caller's case), runs Conversation Intelligence +
  Completion Loop, returns disposition.
- `POST /telephony/outbound/request` — body: case_id, destination, reason,
  scenario (answered|busy|no_answer|voicemail|failed|answered_then_human|
  answered_wrong_number|abandoned), urgent, contact_state. Runs the
  permission gate + anti-harassment guard first; returns permission,
  disposition, retry plan.
- `GET /telephony/calls` — tenant call history.

Demo (after `python3 -m finalis.portal.serve` + login):
`python3 -m pytest tests/test_local_demo_flow.py -q` exercises the full
founder scenario end to end, including WON_NOT_FULFILLED → WON_COMPLETED.
