"""TOOL-B6: no external effect, no escalation, honest self-description.

Across clean and adverse (fail-closed) outcomes the runtime remains read-only,
local, non-external, non-executing. The no-effect proofs, effect ledger, escape
sentinel and non-escalation proof all confirm zero effect, and the public policy
endpoint plus HONESTY_LABELS never claim a capability the runtime lacks.
"""
import pytest

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k
from tests.conftest import OWNER


def _outcome(gate, **over):
    b5, b5r, snap = k.setup(gate)
    return k.prepare(gate, b5, b5r, snap, **over)


# clean plus a few fail-closed variants; all must stay effect-free.
_VARIANTS = [
    {},
    {"adapter_kind": "weird"},
    {"adapter_caps": {"write": True}},
    {"adapter_caps": {"network": True}},
    {"sealed_adapter_hash": "WRONG"},
]


@pytest.mark.parametrize("over", _VARIANTS)
def test_outcome_is_read_only_and_non_external(gate, over):
    o = _outcome(gate, **over)
    assert o["read_only"] is True
    assert o["local_only"] is True
    assert o["is_external"] is False
    assert o["is_execution"] is False
    assert o["produced_external_effect"] is False


def test_no_effect_proofs_all_hold(gate):
    o = k.clean_outcome(gate)
    proofs = o["no_effect_proofs"]
    for name in ("no_write_proof", "no_network_proof", "no_secret_proof",
                 "no_credential_proof", "no_token_proof", "no_provider_proof",
                 "no_mcp_proof", "no_llm_proof"):
        assert proofs[name]["holds"] is True
        assert proofs[name]["signal"] is None
    assert proofs["signals"] == []


def test_effect_ledger_read_only_zero_effects(gate):
    o = k.clean_outcome(gate)
    ledger = o["runtime_effect_ledger"]
    assert ledger["read_only"] is True
    assert ledger["effect_count"] == 0
    assert ledger["effect_operations"] == []


def test_escape_sentinel_detects_no_escape(gate):
    o = k.clean_outcome(gate)
    sentinel = o["runtime_escape_sentinel"]
    assert sentinel["escape_detected"] is False
    assert sentinel["escape_findings"] == []
    assert sentinel["signal"] is None


def test_non_escalation_proof_authority_frozen(gate):
    o = k.clean_outcome(gate)
    proof = o["runtime_non_escalation_proof"]
    assert proof["status"] == "NON_ESCALATED"
    assert proof["authority_frozen"] is True
    assert proof["b5_authorizes_execution"] is False


def test_policy_endpoint_reports_no_dangerous_capability(gate):
    r = gate.c.get("/ai-tools/runtime/policy", headers=gate.h(OWNER))
    assert r.status_code == 200
    p = r.json()
    for key in ("writes", "calls_network", "calls_provider", "reads_secrets",
                "reads_credentials", "issues_tokens", "has_write_endpoint",
                "claims_os_level_sandbox", "claims_differential_privacy"):
        assert p[key] is False
    assert p["read_only"] is True


def test_honesty_labels_include_required_read_only_labels(gate):
    required = {
        "READ_ONLY_INTERNAL_RUNTIME_ONLY", "SNAPSHOT_BOUND_ONLY",
        "CANARY_NON_LEAKAGE_PROVED", "OUTPUT_PROVENANCE_BISIMULATED",
        "NO_NETWORK", "NO_EXTERNAL_PROVIDER", "NO_TOKEN", "NO_CREDENTIAL",
        "NO_SECRET_READ", "NO_WRITE_EFFECT", "NO_MUTABLE_PRODUCTION_READ",
        "NOT_PRODUCTION_AUTONOMOUS_EXECUTION",
    }
    assert required <= set(rt.HONESTY_LABELS)


def test_outcome_carries_honesty_labels(gate):
    o = k.clean_outcome(gate)
    assert o["honesty_labels"] == rt.HONESTY_LABELS
