"""TOOL-B8: THE no-execution invariant. Across the clean path and every blocker
variant the local commit simulator NEVER commits, releases an effect, activates
a commitment, activates B9, grants B9 authority, or claims production/autonomy —
and exposes no endpoint that could. These are the load-bearing safety
invariants: they must hold regardless of which blocker fired."""
import pytest

from finalis.ai_employee.tool_commit_simulation import COMMIT_SIM_STATUSES
from tests import _b8_kernel as k


# Each variant is triggered IN ISOLATION; the invariants below must hold for all.
_VARIANTS = [
    {},  # clean B8_V5_ACCEPTED
    {"extra_claims": {"production_ready": True}},
    {"added_routes": [{"path": "/ai-tools/commit-simulations/x/commit",
                       "method": "POST"}]},
    {"attempt_markers": {"real_commit": True}},
    {"attempt_markers": {"effect_release": True}},
    {"attempt_markers": {"activate_b9": True}},
    {"attempt_markers": {"provider_call": True}},
    {"b9_authority_transfer": True},
    {"b9_activation": True},
    {"effect_release_attempts": 1},
    {"dropped_obligations": ["NO_REAL_COMMIT"]},
    {"force_unclosed_claims": ["NO_COMMIT_THEOREM"]},
    {"injected_mismatches": ["hash_mismatch"]},
    {"delegation_attempts": ["ASSURANCE_ENVELOPE->authority"]},
    {"theorem_refuted": True},
    {"dry_run_ok": False},
    {"b9_contract_present": False},
    {"unexpected_positive": True},
]

_FORBIDDEN_WORDS = ("COMMITTED", "EXECUTED", "RELEASED", "ACTIVATED", "SENT",
                    "MUTATED", "PRODUCTION_READY")


@pytest.mark.parametrize("over", _VARIANTS)
def test_outcome_never_executes(gate, over):
    o = k.clean_outcome(gate, **over)
    assert o["commit_executable_now"] is False
    assert o["is_real_commit"] is False
    assert o["is_execution"] is False
    assert o["produced_external_effect"] is False
    assert o["released_effect"] is False
    assert o["activated_commitment"] is False
    assert o["activated_b9"] is False
    assert o["granted_b9_authority"] is False
    assert o["production_ready"] is False
    assert o["autonomous_ready"] is False
    assert o["artifacts_are_authority"] is False
    assert o["b9_revalidation_required"] is True
    assert o["simulation_only"] is True


@pytest.mark.parametrize("over", _VARIANTS)
def test_assurance_envelope_is_not_authority(gate, over):
    e = k.clean_outcome(gate, **over)["assurance_envelope"]
    assert e["is_authority"] is False
    assert e["authorizes_b9"] is False
    assert e["executes"] is False
    assert e["b9_revalidation_required"] is True


@pytest.mark.parametrize("over", _VARIANTS)
def test_b9_firewall_sealed(gate, over):
    fw = k.clean_outcome(gate, **over)["b9_firewall"]
    assert fw["b8_can_activate_b9"] is False
    assert fw["b8_can_grant_b9_authority"] is False
    assert fw["b8_artifacts_are_b9_authority"] is False


@pytest.mark.parametrize("over", _VARIANTS)
def test_status_is_known_and_never_means_committed(gate, over):
    status = k.clean_outcome(gate, **over)["commit_simulation_status"]
    assert status in COMMIT_SIM_STATUSES
    upper = status.upper()
    for w in _FORBIDDEN_WORDS:
        assert w not in upper, (status, w)


@pytest.mark.parametrize("over", _VARIANTS)
def test_non_production_seal_holds(gate, over):
    seal = k.clean_outcome(gate, **over)["non_production_seal"]
    assert seal["production_ready"] is False
    assert seal["commit_executable_now"] is False
    assert seal["b9_ready_without_revalidation"] is False


def test_no_commit_or_activate_endpoints(gate):
    sid, _ = gate.prepared_commit_simulation()
    for bad in ("/commit", "/execute", "/release-effects",
                "/activate-commitment", "/activate-b9", "/grant-b9-authority",
                "/issue-commit-lease"):
        r = gate.c.post("/ai-tools/commit-simulations/" + sid + bad, json={},
                        headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_no_global_effect_endpoints(gate):
    for bad in ("/provider/call", "/mcp/call", "/payment/execute",
                "/crm/mutate", "/evidence/mutate", "/message/send", "/export"):
        r = gate.c.post(bad, json={}, headers=gate.h())
        assert r.status_code in (404, 405), bad
