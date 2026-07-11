"""Mutation Testing Campaign (SP0001 §20.13, AC-0001-43).

Each injected forbidden pattern must produce the exact finding — nothing silently
passes. Uses synthetic twins/observations so the real tree is never mutated.
"""
from __future__ import annotations

from tools.architecture.conformance import evaluate
from tools.architecture.duplication import candidates
from tools.architecture.waivers import expired_findings, active_scopes
from tests._arch_helpers import (cap, mini_twin, mini_observed, net_effect,
                                 dyn_effect)


def _kinds(rep):
    return {f.kind for f in rep.findings}


def _sev(rep, kind):
    return [f.severity for f in rep.findings if f.kind == kind]


# --- baseline of the synthetic world is clean ------------------------------
def _clean_world():
    caps = [
        cap("crm", paths=["finalis/crm/"], routes=["/crm"], tables=["crm_"],
            forbidden=["finalis.ai_employee"]),
        cap("run_ledger", paths=["finalis/ai_employee/run_ledger.py"],
            routes=["/ai-runs"], tables=["ai_runs"], classification="governance_core"),
        cap("portal_shell", paths=["finalis/portal/"], routes=["/"],
            classification="presentation"),
    ]
    migs = [["1", "h1"], ["2", "h2"]]
    twin = mini_twin(caps, migrations=migs,
                     route_baseline=["/crm", "/ai-runs", "/"],
                     table_baseline=["crm_", "ai_runs"])
    obs = mini_observed(
        modules=["finalis.crm.engine", "finalis.ai_employee.run_ledger",
                 "finalis.portal.app"],
        import_edges=[["finalis.portal.app", "finalis.crm.engine"]],
        routes=["/crm", "/ai-runs"], tables=["crm_data"],
        migrations=[list(m) for m in migs])
    return twin, obs


def test_clean_synthetic_world_is_valid():
    twin, obs = _clean_world()
    rep = evaluate(twin, obs)
    assert rep.valid, [f.to_dict() for f in rep.findings]


# --- M1: CRM2 duplicate module (unowned) -----------------------------------
def test_mutation_crm2_unowned():
    twin, obs = _clean_world()
    obs.modules.append("finalis.crm2.engine")
    rep = evaluate(twin, obs)
    assert "UNOWNED_NODE" in _kinds(rep)
    assert not rep.valid


# --- M2: customer_platform duplicating CRM (ownership conflict) -------------
def test_mutation_customer_platform_route_table_conflict():
    twin, obs = _clean_world()
    twin["capabilities"].append(
        cap("customer_platform", paths=["finalis/customer_platform/"],
            routes=["/crm"], tables=["crm_"]))   # claims CRM's namespaces
    rep = evaluate(twin, obs)
    assert "CAPABILITY_OWNERSHIP_CONFLICT" in _kinds(rep)
    assert "P0" in _sev(rep, "CAPABILITY_OWNERSHIP_CONFLICT")


# --- M3: second run ledger (module ownership conflict) ---------------------
def test_mutation_second_run_ledger_conflict():
    twin, obs = _clean_world()
    twin["capabilities"].append(
        cap("run_ledger_2", paths=["finalis/ai_employee/run_ledger.py"],
            classification="governance_core"))  # same file, two owners
    obs.modules.append("finalis.ai_employee.run_ledger")  # already present
    rep = evaluate(twin, obs)
    assert "CAPABILITY_OWNERSHIP_CONFLICT" in _kinds(rep)


# --- M4: route ownership conflict ------------------------------------------
def test_mutation_route_conflict():
    twin, obs = _clean_world()
    twin["capabilities"][1]["route_namespaces"].append("/crm")  # run_ledger grabs /crm
    rep = evaluate(twin, obs)
    conflicts = [f for f in rep.findings
                 if f.kind == "CAPABILITY_OWNERSHIP_CONFLICT"
                 and f.detail.get("kind") == "route"]
    assert conflicts and conflicts[0].severity == "P0"


# --- M5: table ownership conflict ------------------------------------------
def test_mutation_table_conflict():
    twin, obs = _clean_world()
    twin["capabilities"][2]["table_namespaces"].append("crm_")  # portal grabs crm_
    rep = evaluate(twin, obs)
    conflicts = [f for f in rep.findings
                 if f.kind == "CAPABILITY_OWNERSHIP_CONFLICT"
                 and f.detail.get("kind") == "table"]
    assert conflicts and conflicts[0].severity == "P0"


# --- M6: historical migration mutation -------------------------------------
def test_mutation_historical_migration_edit():
    twin, obs = _clean_world()
    obs.migration_digests = [["1", "TAMPERED"], ["2", "h2"]]
    rep = evaluate(twin, obs)
    assert "MIGRATION_MUTATION" in _kinds(rep)
    assert "P0" in _sev(rep, "MIGRATION_MUTATION")


def test_mutation_historical_migration_delete():
    twin, obs = _clean_world()
    obs.migration_digests = [["2", "h2"]]   # v1 removed
    rep = evaluate(twin, obs)
    assert any(f.kind == "MIGRATION_MUTATION" and "removed" in f.message
               for f in rep.findings)


def test_append_next_migration_is_allowed():
    twin, obs = _clean_world()
    obs.migration_digests = [["1", "h1"], ["2", "h2"], ["3", "h3_new"]]
    rep = evaluate(twin, obs)
    assert rep.valid, [f.to_dict() for f in rep.findings]
    assert rep.metrics.get("appended_migrations") == [3]


def test_noncontiguous_append_is_p1():
    twin, obs = _clean_world()
    obs.migration_digests = [["1", "h1"], ["2", "h2"], ["5", "h5"]]
    rep = evaluate(twin, obs)
    assert not rep.valid
    assert any(f.kind == "MIGRATION_MUTATION" and f.severity == "P1"
               for f in rep.findings)


# --- M7: outbound HTTP primitive (effect gate) -----------------------------
def test_mutation_outbound_http():
    twin, obs = _clean_world()
    obs.effect_observations = [net_effect("finalis.crm.engine", "requests")]
    rep = evaluate(twin, obs)
    assert "EFFECT_GATE_VIOLATION" in _kinds(rep)
    assert "P0" in _sev(rep, "EFFECT_GATE_VIOLATION")


def test_mutation_outbound_socket_and_smtplib():
    for target in ("socket", "smtplib", "httpx", "urllib.request"):
        twin, obs = _clean_world()
        obs.effect_observations = [net_effect("finalis.crm.engine", target)]
        rep = evaluate(twin, obs)
        assert "EFFECT_GATE_VIOLATION" in _kinds(rep), target


# --- M8: dynamic import (advisory, not hard fail) --------------------------
def test_mutation_dynamic_import_is_advisory():
    twin, obs = _clean_world()
    obs.effect_observations = [dyn_effect("finalis.crm.engine")]
    rep = evaluate(twin, obs)
    assert "DYNAMIC_IMPORT_ADVISORY" in _kinds(rep)
    assert rep.valid   # P2 only, does not block


# --- M9: forbidden dependency (product -> governance) ----------------------
def test_mutation_forbidden_dependency():
    twin, obs = _clean_world()
    obs.import_edges.append(
        ["finalis.crm.engine", "finalis.ai_employee.run_ledger"])
    rep = evaluate(twin, obs)
    assert "FORBIDDEN_DEPENDENCY" in _kinds(rep)
    assert "P0" in _sev(rep, "FORBIDDEN_DEPENDENCY")


# --- M10: undeclared package (unowned) -------------------------------------
def test_mutation_undeclared_package():
    twin, obs = _clean_world()
    obs.modules.append("finalis.secret_new_domain.core")
    rep = evaluate(twin, obs)
    assert "UNOWNED_NODE" in _kinds(rep)


# --- M11: expired waiver ----------------------------------------------------
def test_mutation_expired_waiver():
    waivers = [{"waiver_id": "w1", "scope": "forbidden:crm->x", "reason": "temp",
                "owner": "eng", "created_at": "2026-01-01",
                "expires_at": "2026-06-01", "status": "ACTIVE"}]
    findings = expired_findings(waivers, "2026-07-11")
    assert findings and findings[0].kind == "WAIVER_EXPIRED"
    assert findings[0].severity == "P1"
    # not yet expired
    assert not expired_findings(waivers, "2026-05-01")


def test_active_waiver_suppresses_effect_violation():
    twin, obs = _clean_world()
    obs.effect_observations = [net_effect("finalis.crm.engine", "requests")]
    scope = "effect:finalis.crm.engine:requests"
    rep = evaluate(twin, obs, active_waivers={scope})
    assert "EFFECT_GATE_VIOLATION" not in _kinds(rep)


# --- M12: scan error is fail-closed ----------------------------------------
def test_mutation_scan_error_fail_closed():
    twin, obs = _clean_world()
    obs.scan_errors = [{"path": "finalis/crm/broken.py", "error": "SyntaxError: x"}]
    rep = evaluate(twin, obs)
    assert "SCAN_ERROR" in _kinds(rep)
    assert not rep.valid


def test_mutation_unsupported_language_surfaced():
    twin, obs = _clean_world()
    obs.scan_errors = [{"path": "finalis/portal/ui.tsx",
                        "error": "UNSUPPORTED_LANGUAGE (.tsx): no ScannerAdapter"}]
    rep = evaluate(twin, obs)
    assert "UNSUPPORTED_LANGUAGE_ARCHITECTURE_SCAN" in _kinds(rep)
    assert not rep.valid


# --- M13: spec-code drift (structural duplicate, diff name) ----------------
def test_mutation_structural_duplicate_generates_candidate():
    # different name, strong route/table/purpose overlap -> candidate
    caps = [
        cap("crm", routes=["/crm"], tables=["crm_"],
            purpose="relationship customer party record system of record"),
        cap("relationship_hub", routes=["/relationships"], tables=["crm_"],
            purpose="relationship customer party record system of record"),
    ]
    twin = mini_twin(caps)
    cands = candidates(twin, edges=[], threshold=0.3)
    assert any({c["a"], c["b"]} == {"crm", "relationship_hub"} for c in cands)
    # advisory only — never proven
    assert all(c["verdict"] == "DUPLICATION_CANDIDATE" for c in cands)
