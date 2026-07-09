"""TOOL-B6 read-path runtime: portal UI section renders + wires."""


def test_portal_serves_runtime_section(gate):
    r = gate.c.get("/portal", headers=gate.h())
    assert r.status_code == 200
    html = r.text
    assert "tool-runtime-section" in html
    assert "Verifiable Read-Path Runtime Microkernel" in html


def test_portal_has_runtime_wiring(gate):
    html = gate.c.get("/portal", headers=gate.h()).text
    assert "loadRuntimeSection" in html
    assert "openRuntimeOutcome" in html


def test_portal_shows_read_only_honesty(gate):
    html = gate.c.get("/portal", headers=gate.h()).text
    assert "READ_ONLY_INTERNAL_RUNTIME_ONLY" in html
