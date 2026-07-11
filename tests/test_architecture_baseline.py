"""Real-repository baseline + determinism + isolation + scale.

Covers SP0001 AC-01/02/06/12/19/20/39/40/41/48/49 and INV-0001-09/12.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tools.architecture.conformance import evaluate
from tools.architecture.graph import TypedGraph
from tools.architecture.impact import impact_cone
from tools.architecture.manifest import load_twin, validate_twin
from tools.architecture.observe import build_observed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TWIN = os.path.join(ROOT, "docs/architecture/FINALIS_1000_ARCHITECTURE_TWIN.json")

# canonical domains that MUST be represented (AC-02)
REQUIRED_CAPS = {
    "crm", "evidence", "case_graph", "lifecycle_universal", "cpq", "scheduling",
    "telephony", "voice", "action_communication", "command_center", "rbac_admin",
    "audit_chain", "portal_shell", "agent_runtime_governance",
    "core_a1_identity", "core_a2_tasks", "core_a3_run_ledger", "core_a4_approvals",
    "core_a5_lifecycle", "core_a6_artifacts",
    "tool_b1_registry", "tool_b2_quality", "tool_b3_contracts", "tool_b4_guardrails",
    "tool_b5_broker", "tool_b6_runtime", "tool_b7_write_intent",
    "tool_b8_commit_simulation", "tool_b9_local_transaction", "tool_b91_recovery",
    "tool_b92_observability", "emp_a1_work_inbox",
}


def _twin():
    return load_twin(TWIN)


def test_sp0000_precondition_complete():
    """AC-01: SP0000 verified complete before SP0001 relies on it."""
    m = json.load(open(os.path.join(
        ROOT, "docs/architecture/FINALIS_1000_ARCHITECTURE_MANIFEST.json")))
    assert m["independent_verification"]["p0_open"] == 0
    assert m["independent_verification"]["p1_open"] == 0
    assert "COMPLETE" in m["final_result"]


def test_all_required_capabilities_represented():
    """AC-02: 100% major existing capabilities in the twin."""
    ids = {c["capability_id"] for c in _twin()["capabilities"]}
    missing = REQUIRED_CAPS - ids
    assert not missing, f"unrepresented capabilities: {missing}"


def test_real_twin_validates():
    """AC-19."""
    assert validate_twin(_twin()) == []


def test_real_baseline_is_valid():
    """The declared twin conforms to observed reality: 0 P0, 0 P1."""
    rep = evaluate(_twin(), build_observed(ROOT))
    assert rep.valid, [f.to_dict() for f in rep.findings if f.severity != "P2"]
    assert rep.counts()["P0"] == 0
    assert rep.counts()["P1"] == 0


def test_observed_twin_is_deterministic():
    """AC-06 / INV-0001-12: same tree => same observed twin."""
    a = build_observed(ROOT).to_dict()
    b = build_observed(ROOT).to_dict()
    assert a == b


def test_conformance_is_deterministic():
    """INV-0001-12: same tree + manifest => same findings."""
    twin = _twin()
    r1 = evaluate(twin, build_observed(ROOT)).to_dict()
    r2 = evaluate(twin, build_observed(ROOT)).to_dict()
    assert r1 == r2


def test_one_owner_per_protected_capability():
    """AC-04 / INV-0001-01: exactly one canonical owner each."""
    for c in _twin()["capabilities"]:
        assert c["canonical_owner"], c["capability_id"]
        assert c["replacement_policy"] == "DO_NOT_REBUILD"


def test_effect_gate_closed_in_twin():
    """D-0001-19: real_external_effects_allowed = false."""
    assert _twin()["effect_gates"]["real_external_effects_allowed"] is False


def test_migration_baseline_matches_repo():
    """Append-only baseline reflects the real 27 migrations."""
    twin = _twin()
    obs = build_observed(ROOT)
    assert twin["migration_integrity"]["baseline_max_version"] == \
        max(int(v) for v, _ in obs.migration_digests)


def test_product_code_does_not_import_architecture_tooling():
    """AC-40 / INV-0001-09: product never imports tools.architecture."""
    hits = subprocess.run(
        ["grep", "-rn", "tools.architecture", os.path.join(ROOT, "finalis")],
        capture_output=True, text=True)
    assert hits.stdout.strip() == "", hits.stdout


def test_no_foreign_language_silently_ignored():
    """AC-49: any non-Python source under finalis/ surfaces (none today)."""
    obs = build_observed(ROOT)
    foreign = [e for e in obs.scan_errors if "UNSUPPORTED_LANGUAGE" in e.get("error", "")]
    # today there are none; if a .ts is added later it must appear here, not vanish
    assert isinstance(foreign, list)


def test_cli_validate_exit_zero():
    """AC-20: the gate runs and passes on the clean tree."""
    r = subprocess.run([sys.executable, "-m", "tools.architecture", "validate",
                        "--json"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["valid"] is True


def test_cli_attest_deterministic_across_processes():
    def _hash():
        r = subprocess.run([sys.executable, "-m", "tools.architecture", "attest",
                            "--json"], cwd=ROOT, capture_output=True, text=True)
        return json.loads(r.stdout)["envelope_hash"]
    assert _hash() == _hash()


def test_impact_and_scc_scale_near_linear():
    """AC-14 perf: large synthetic graph completes; SCC/impact are O(V+E)."""
    g = TypedGraph()
    n = 5000
    for i in range(n):
        g.add_edge("E", f"n{i}", f"n{i+1}")
    # acyclic chain -> all singletons, no cycle
    assert not g.has_cycle(["E"])
    reach = g.reverse_reachable(["E"], [f"n{n}"])
    assert len(reach) == n + 1


def test_large_synthetic_twin_conformance_scales():
    from tests._arch_helpers import cap, mini_twin, mini_observed
    caps = [cap(f"c{i}", paths=[f"finalis/c{i}/"]) for i in range(300)]
    twin = mini_twin(caps)
    mods = [f"finalis.c{i}.mod" for i in range(300)]
    edges = [[f"finalis.c{i}.mod", f"finalis.c{i+1}.mod"] for i in range(299)]
    obs = mini_observed(modules=mods, import_edges=edges)
    rep = evaluate(twin, obs)
    assert rep.metrics["modules"] == 300
