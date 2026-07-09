"""TOOL-B4: the portal UI surfaces the pre-action monitor section honestly."""


def test_portal_serves_actions_section(gate):
    r = gate.c.get("/portal")
    assert r.status_code == 200
    for token in ("tool-actions-section", "loadActionsSection", "openDecision"):
        assert token in r.text, token


def test_portal_titles_the_monitor(gate):
    r = gate.c.get("/portal")
    assert "Pre-Action Reference Monitor" in r.text


def test_portal_shows_honesty_labels(gate):
    r = gate.c.get("/portal")
    assert "executes nothing" in r.text
    assert "not a token" in r.text
