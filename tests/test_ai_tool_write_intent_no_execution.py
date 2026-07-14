"""TOOL-B7: no-execution invariants (the most important file). Across the clean
path AND every blocker variant, the runtime NEVER writes, commits, releases an
effect, activates a commitment, or produces an external effect — and no endpoint
can make it. This holds regardless of the decision."""
import pytest

from finalis.ai_employee.tool_write_intent import WRITE_INTENT_STATUSES
from tests import _b7_kernel as k

_FORBIDDEN_SUBSTRINGS = ("COMMITTED", "EXECUTED", "RELEASED", "SENT", "MUTATED")

# Override variants that each drive a different decision path.
_VARIANTS = [
    {},
    {"escrow_mutable": True},
    {"observed_escrow_hash": "deadbeef"},
    {"compensation_gaps": 1},
    {"rollback_feasible": False},
    {"invariant_violations": 1},
    {"replay_consistent": False},
    {"attempt_markers": {"commit": True}},
    {"attempt_markers": {"payment": True}},
    {"attempt_markers": {"provider_call": True}},
    {"execution_markers": {"commit_executable_now": True}},
    {"execution_markers": {"resolve_escrow_and_commit": True}},
    {"effect_release_attempts": 1},
    {"commitment_activation_attempts": 1},
    {"debt_items": [{"debt_type": "CONSENT_RECHECK", "resolved": False}]},
    {"current_epoch": 9999, "escrow_expires_epoch": 1},
    {"risk_tier": "HIGH", "state_witnesses": []},
    {"detected_commit_endpoints": ["WRITE_INTENT_COMMIT_ENDPOINT"]},
    {"objections": [{"objection_id": "x", "resolved": False}]},
]


def _assert_never_executes(o):
    assert o["commit_executable_now"] is False
    assert o["is_write"] is False
    assert o["is_commit"] is False
    assert o["is_execution"] is False
    assert o["produced_external_effect"] is False
    assert o["released_effect"] is False
    assert o["activated_commitment"] is False
    acr = o["active_commitment_record"]
    assert acr["activated"] is False
    assert acr["can_activate"] is False
    assert o["staged_effect_outbox"]["any_released"] is False
    assert o["staged_effect_outbox"]["any_releasable"] is False
    assert o["transaction_escrow_capsule"]["escrow_executes"] is False
    assert o["transaction_escrow_capsule"]["escrow_can_commit"] is False
    assert o["escrowed_commit_readiness_certificate"][
        "commit_executable_now"] is False
    status = o["write_intent_status"]
    assert not any(s in status for s in _FORBIDDEN_SUBSTRINGS), status


@pytest.mark.parametrize("over", _VARIANTS)
def test_never_executes_across_variants(gate, over):
    o = k.prepare(gate, k.b6_outcome(gate), **over)
    _assert_never_executes(o)


def test_never_executes_when_approval_missing(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False)
    _assert_never_executes(o)
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_no_status_ever_means_committed_or_executed(gate):
    for status in WRITE_INTENT_STATUSES:
        assert not any(s in status for s in _FORBIDDEN_SUBSTRINGS), status


def test_ready_for_future_commit_only_on_clean_path(gate):
    b6 = k.b6_outcome(gate)
    assert k.prepare(gate, b6)["ready_for_future_commit_only"] is True
    # Any blocker forces ready_for_future_commit_only False.
    blocked = k.prepare(gate, b6, compensation_gaps=1)
    assert blocked["ready_for_future_commit_only"] is False


def test_clean_path_is_draft_only(gate):
    o = k.clean_outcome(gate)
    _assert_never_executes(o)
    assert o["draft_only"] is True and o["escrow_only"] is True


def test_no_commit_execute_endpoints_per_intent(gate):
    wid, _ = gate.prepared_write_intent()
    for bad in ("/commit", "/execute", "/release-effects",
                "/activate-commitment", "/resolve-escrow-and-commit"):
        r = gate.c.post("/ai-tools/write-intents/" + wid + bad, json={},
                        headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_no_global_commit_endpoints(gate):
    for bad in ("/ai-tools/write-intents/commit",
                "/ai-tools/write-intents/execute",
                "/ai-tools/write-intents/release-effects",
                "/ai-tools/write-intents/activate-commitment"):
        r = gate.c.post(bad, json={}, headers=gate.h())
        assert r.status_code in (404, 405), bad


def test_safe_and_outcome_agree_on_non_execution(gate):
    wid, _ = gate.prepared_write_intent()
    out = gate.wi(wid, "/outcome").json()
    _assert_never_executes(out)
