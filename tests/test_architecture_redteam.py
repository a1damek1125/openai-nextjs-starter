"""Regression tests for SWARM-I red-team findings (SP0001 repair round).

Each test pins a fix so the bypass cannot silently reopen.
"""
from __future__ import annotations

from tools.architecture.conformance import evaluate
from tools.architecture.manifest import validate_twin
from tools.architecture.observe import build_observed, _effect_observations
from tools.architecture.waivers import (active_scopes, invalid_waiver_findings,
                                        is_valid_active)
from tests._arch_helpers import cap, mini_twin, mini_observed, net_effect
import ast
import os


# ---- GAP-1: anonymous / permanent waivers must NOT suppress P0/P1 ----------
def _anon_waiver():
    return {"waiver_id": "w", "scope": "effect:finalis.crm.engine:requests",
            "status": "ACTIVE", "expires_at": "2099-01-01"}  # no owner/reason/created


def test_anonymous_waiver_does_not_suppress():
    w = _anon_waiver()
    # not a valid active waiver -> scope not returned -> cannot suppress
    assert active_scopes([w], "2026-07-11") == set()
    assert not is_valid_active(w, "2026-07-11", 90)


def test_anonymous_active_waiver_is_flagged_p1():
    findings = invalid_waiver_findings([_anon_waiver()], "2026-07-11", 90)
    assert findings and findings[0].kind == "INVALID_WAIVER"
    assert findings[0].severity == "P1"


def test_over_lifetime_waiver_rejected():
    w = {"waiver_id": "w", "scope": "s", "reason": "r", "owner": "eng",
         "created_at": "2026-01-01", "expires_at": "2026-12-31",  # ~364 days
         "status": "ACTIVE"}
    assert not is_valid_active(w, "2026-07-11", 90)   # exceeds 90-day cap
    assert invalid_waiver_findings([w], "2026-07-11", 90)


def test_well_formed_short_waiver_still_works():
    w = {"waiver_id": "w", "scope": "effect:m:requests", "reason": "temp fix",
         "owner": "eng", "created_at": "2026-07-01", "expires_at": "2026-08-01",
         "status": "ACTIVE"}
    assert is_valid_active(w, "2026-07-11", 90)
    assert "effect:m:requests" in active_scopes([w], "2026-07-11")


# ---- GAP-2: twin self-contradiction (emptied forbidden list) detected ------
def test_twin_self_contradiction_detected():
    twin = mini_twin([cap("crm", forbidden=[])])
    twin["dependency_rules"] = [{"rule": "FORBIDDEN", "capability": "crm",
                                 "forbidden_import_prefix": "finalis.ai_employee"}]
    errs = validate_twin(twin)
    assert any("self-contradiction" in e for e in errs)


def test_twin_consistent_forbidden_ok():
    twin = mini_twin([cap("crm", forbidden=["finalis.ai_employee"])])
    twin["dependency_rules"] = [{"rule": "FORBIDDEN", "capability": "crm",
                                 "forbidden_import_prefix": "finalis.ai_employee"}]
    assert not any("self-contradiction" in e for e in validate_twin(twin))


# ---- B1: observed route/table ownership enforced in the gate ---------------
def test_undeclared_route_is_advisory_in_gate():
    twin = mini_twin([cap("crm", routes=["/crm"])],
                     route_baseline=["/crm"], table_baseline=[])
    obs = mini_observed(modules=["finalis.crm.engine"], routes=["/crm", "/foo_new"])
    rep = evaluate(twin, obs)
    assert any(f.kind == "UNOWNED_ROUTE" and f.severity == "P2" for f in rep.findings)
    assert rep.valid   # advisory, does not block


def test_observed_route_collision_is_p0():
    twin = mini_twin([cap("crm", routes=["/x"]), cap("y", routes=["/x"])])
    # declared overlap already flagged; also observed route resolves to conflict
    obs = mini_observed(modules=["finalis.crm.e", "finalis.y.e"], routes=["/x"])
    rep = evaluate(twin, obs)
    assert any(f.kind == "CAPABILITY_OWNERSHIP_CONFLICT" and f.severity == "P0"
               for f in rep.findings)


# ---- B6: intra-governance cycle caught via induced subgraph ----------------
def test_governance_cycle_is_p1_via_induced_subgraph():
    caps = [
        cap("gov_a", paths=["finalis/ai_employee/a.py"], classification="governance_tool"),
        cap("gov_b", paths=["finalis/ai_employee/b.py"], classification="governance_tool"),
        cap("portal_shell", paths=["finalis/portal/"], classification="presentation"),
    ]
    twin = mini_twin(caps, acyclic_required=[["gov_a", "gov_b"]])
    obs = mini_observed(
        modules=["finalis.ai_employee.a", "finalis.ai_employee.b", "finalis.portal.app"],
        import_edges=[["finalis.ai_employee.a", "finalis.ai_employee.b"],
                      ["finalis.ai_employee.b", "finalis.ai_employee.a"]])  # cycle
    rep = evaluate(twin, obs)
    assert any(f.kind == "ARCHITECTURE_DEPENDENCY_CYCLE" and f.severity == "P1"
               for f in rep.findings)
    assert not rep.valid


def test_governance_acyclic_baseline_ok():
    caps = [
        cap("gov_a", paths=["finalis/ai_employee/a.py"], classification="governance_tool"),
        cap("gov_b", paths=["finalis/ai_employee/b.py"], classification="governance_tool"),
    ]
    twin = mini_twin(caps, acyclic_required=[["gov_a", "gov_b"]])
    obs = mini_observed(
        modules=["finalis.ai_employee.a", "finalis.ai_employee.b"],
        import_edges=[["finalis.ai_employee.a", "finalis.ai_employee.b"]])  # DAG
    rep = evaluate(twin, obs)
    assert not any(f.kind == "ARCHITECTURE_DEPENDENCY_CYCLE" and f.severity == "P1"
                   for f in rep.findings)


# ---- GAP-3: dynamic/subprocess egress is at least detected (advisory) ------
def _obs_of(src: str):
    tree = ast.parse(src)
    return _effect_observations("finalis.crm.engine", "finalis/crm/engine.py", tree)


def test_importlib_import_module_detected():
    obs = _obs_of("import importlib\nx = importlib.import_module('requests')\n")
    assert any(o["target"] == "importlib.import_module" for o in obs)


def test_subprocess_exec_detected():
    obs = _obs_of("import subprocess\nsubprocess.run(['curl','http://x'])\n")
    assert any(o["kind"] == "subprocess_exec" and o["target"] == "subprocess.run"
               for o in obs)


def test_os_system_detected():
    obs = _obs_of("import os\nos.system('curl http://x')\n")
    assert any(o["target"] == "os.system" for o in obs)


def test_effect_gate_honesty_disclosed_in_docs():
    """GAP-3: the static-analysis blind spot must be honestly disclosed."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    doc = open(os.path.join(root, "docs/architecture",
                            "FINALIS_1000_ARCHITECTURE_GUARD_RULES.md")).read()
    assert "cannot" in doc.lower() and "network" in doc.lower()
    assert "importlib" in doc or "subprocess" in doc
