"""TOOL-B8 v1-v3 base: staged-effect release simulation — every staged effect is
simulated only, never actually released; any release attempt is a leak."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_simulated_only(gate):
    r = k.clean_outcome(gate)["effect_simulation"]
    assert r["effect_status"] == "SIMULATED_ONLY"
    assert r["any_actually_released"] is False
    assert r["simulation_only"] is True
    assert r["signal"] is None


def test_clean_effects_not_released(gate):
    r = k.clean_outcome(gate)["effect_simulation"]
    for e in r["simulated_effects"]:
        assert e["actually_released"] is False
        assert e["simulated_release"] is True


def test_release_attempt_is_leak(gate):
    o = k.clean_outcome(gate, effect_release_attempts=1)
    assert o["dominant_signal"] == "EFFECT_SIMULATION_LEAK"
    r = o["effect_simulation"]
    assert r["effect_status"] == "LEAK"
    assert r["release_attempts_detected"] == 1


def test_leak_never_releases(gate):
    o = k.clean_outcome(gate, effect_release_attempts=1)
    assert o["effect_simulation"]["any_actually_released"] is False
    assert o["released_effect"] is False
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_leak_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    leak = k.prepare(gate, b7, effect_release_attempts=1)[
        "commit_simulation_decision_hash"]
    assert clean != leak


def test_effect_simulation_hash_recomputes(gate):
    r = k.clean_outcome(gate)["effect_simulation"]
    assert _core_hash(r, "effect_simulation_hash", "signal") == \
        r["effect_simulation_hash"]


def test_leak_hash_recomputes(gate):
    r = k.clean_outcome(gate, effect_release_attempts=1)["effect_simulation"]
    assert _core_hash(r, "effect_simulation_hash", "signal") == \
        r["effect_simulation_hash"]


def test_effect_count_matches(gate):
    r = k.clean_outcome(gate)["effect_simulation"]
    assert r["effect_count"] == len(r["simulated_effects"])


def test_effect_simulation_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/effect-simulation").json()["effect_simulation"]
    assert r["effect_status"] == "SIMULATED_ONLY"
    assert r["any_actually_released"] is False
