"""TOOL-B5 portal UI: the broker section renders with its wiring + honest
NULL-effect labelling."""
from tests.conftest import OWNER


def test_portal_serves_broker_section(gate):
    r = gate.c.get("/portal", headers=gate.h())
    assert r.status_code == 200
    html = r.text
    assert "tool-broker-section" in html


def test_portal_has_broker_wiring(gate):
    html = gate.c.get("/portal", headers=gate.h()).text
    assert "loadBrokerSection" in html
    assert "openBrokerOutcome" in html


def test_portal_shows_null_broker_honesty(gate):
    html = gate.c.get("/portal", headers=gate.h()).text
    assert "Four-Plane Proof-Carrying Null Broker" in html
    assert "NULL_EFFECT_ONLY" in html
