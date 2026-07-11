"""Intent, impact cone, duplication, envelope, context spine, drift, waivers.

Covers SP0001 AC-09/10/11 (intent), AC-15 (impact oracle), AC-27/28/29
(duplication), AC-30/31/32 (context spine), AC-33/34/35 (envelope),
AC-25/26 (drift), AC-36/37/38 (waivers).
"""
from __future__ import annotations

from tools.architecture.context_spine import generate as gen_spine, CRITICAL_INVARIANTS
from tools.architecture.drift import snapshot_vector, delta, append_history, ewma
from tools.architecture.duplication import candidates, WEIGHTS, similarity
from tools.architecture.envelope import build_envelope
from tools.architecture.impact import impact_cone
from tools.architecture.intent import (validate_intent, classify_delta,
                                        CHANGE_TYPES)
from tools.architecture.model import P0, P1, P2
from tools.architecture.waivers import (validate_waiver, active_scopes,
                                        expired_findings, status_report)
from tests._arch_helpers import cap, mini_twin, mini_observed


# ============================ INTENT (D-0001-03/04) =========================
def test_intent_valid():
    intent = {"change_id": "c1", "sp_id": "SP0002", "base_commit": "abc",
              "target_capabilities": ["crm"], "change_type": "CAPABILITY_EXTENSION"}
    assert validate_intent(intent) == []


def test_intent_missing_field_fails():
    assert any("missing required field" in e
               for e in validate_intent({"change_id": "c1"}))


def test_intent_invalid_change_type():
    intent = {"change_id": "c1", "sp_id": "s", "base_commit": "a",
              "target_capabilities": [], "change_type": "WILD"}
    assert any("invalid change_type" in e for e in validate_intent(intent))


def test_intent_cannot_waive_hard_invariant():
    intent = {"change_id": "c1", "sp_id": "s", "base_commit": "a",
              "target_capabilities": [], "change_type": "NEW_CAPABILITY",
              "waives": ["bypass_tenant_isolation"]}
    assert any("cannot waive hard invariant" in e for e in validate_intent(intent))


def test_declared_extension_is_clean():
    delta = {"new_capabilities": [], "new_routes": [], "new_tables": [],
             "new_capability_edges": []}
    intent = {"target_capabilities": ["crm"], "change_type": "CAPABILITY_EXTENSION"}
    assert classify_delta(intent, delta)["is_clean"]


def test_undeclared_new_capability_is_drift():
    delta = {"new_capabilities": ["crm2"], "new_routes": [], "new_tables": [],
             "new_capability_edges": []}
    out = classify_delta(None, delta)
    assert not out["is_clean"]
    assert any(d["type"] == "UNDECLARED_NEW_CAPABILITY" for d in out["undeclared_drift"])


def test_declared_new_capability_is_clean():
    delta = {"new_capabilities": ["reporting"], "new_routes": [], "new_tables": [],
             "new_capability_edges": []}
    intent = {"target_capabilities": ["reporting"], "new_capabilities": ["reporting"],
              "change_type": "NEW_CAPABILITY"}
    assert classify_delta(intent, delta)["is_clean"]


# ============================ IMPACT CONE (AC-15) ===========================
def _impact_world():
    caps = [cap("db", paths=["finalis/db/"], classification="foundation"),
            cap("crm", paths=["finalis/crm/"]),
            cap("app", paths=["finalis/app/"], classification="presentation")]
    twin = mini_twin(caps)
    obs = mini_observed(
        modules=["finalis.db.core", "finalis.crm.engine", "finalis.app.main"],
        import_edges=[["finalis.crm.engine", "finalis.db.core"],
                      ["finalis.app.main", "finalis.crm.engine"]])
    return twin, obs


def test_impact_cone_matches_reference():
    twin, obs = _impact_world()
    out = impact_cone(twin, obs, ["db"])
    # who depends (transitively) on db? crm and app
    assert set(out["full_cone"]) == {"db", "crm", "app"}
    assert out["direct_impact"] == ["crm"]
    assert out["downstream_impact"] == ["app", "crm"]


def test_impact_cone_unknown_capability_reported():
    twin, obs = _impact_world()
    out = impact_cone(twin, obs, ["nope"])
    assert out["unknown_capabilities"] == ["nope"]


# ============================ DUPLICATION (AC-27/28/29) =====================
def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_high_overlap_generates_candidate():
    caps = [cap("a", routes=["/x"], tables=["t_"], purpose="alpha beta gamma"),
            cap("b", routes=["/x"], tables=["t_"], purpose="alpha beta gamma")]
    twin = mini_twin(caps)
    c = candidates(twin, edges=[], threshold=0.5)
    assert c and c[0]["verdict"] == "DUPLICATION_CANDIDATE"


def test_low_overlap_no_candidate():
    caps = [cap("a", routes=["/x"], tables=["t_"], purpose="alpha"),
            cap("b", routes=["/y"], tables=["u_"], purpose="omega")]
    twin = mini_twin(caps)
    assert candidates(twin, edges=[], threshold=0.5) == []


def test_same_name_tokens_different_semantics_low_score():
    # deliberately different routes/tables -> even similar words stay low
    a = cap("billing", routes=["/billing"], tables=["invoice_"], purpose="charge card")
    b = cap("blogging", routes=["/blog"], tables=["post_"], purpose="write article")
    s = similarity(a, b, [])
    assert s["score"] < 0.3


def test_similarity_is_advisory_never_identity():
    a = cap("a", routes=["/x"], tables=["t_"], purpose="same words here")
    b = cap("b", routes=["/x"], tables=["t_"], purpose="same words here")
    s = similarity(a, b, [])
    assert s["score"] < 1.0 or s["a"] != s["b"]  # never asserts a == b


# ============================ ENVELOPE (AC-33/34/35) ========================
def _env_inputs():
    twin = mini_twin([cap("crm")])
    observed = mini_observed(modules=["finalis.crm.engine"]).to_dict()
    delta = {"new_capabilities": []}
    conf = {"counts": {P0: 0, P1: 0, P2: 0}, "findings": [], "metrics": {}}
    return twin, observed, delta, conf


def test_envelope_deterministic():
    twin, observed, delta, conf = _env_inputs()
    e1 = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                        observed=observed, architecture_delta=delta, conformance=conf)
    e2 = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                        observed=observed, architecture_delta=delta, conformance=conf)
    assert e1["envelope_hash"] == e2["envelope_hash"]


def test_envelope_changes_when_manifest_changes():
    twin, observed, delta, conf = _env_inputs()
    base = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                          observed=observed, architecture_delta=delta, conformance=conf)
    twin2 = mini_twin([cap("crm"), cap("evidence")])
    changed = build_envelope(base_commit="b", source_commit="s", declared_twin=twin2,
                             observed=observed, architecture_delta=delta, conformance=conf)
    assert base["envelope_hash"] != changed["envelope_hash"]


def test_envelope_changes_when_delta_changes():
    twin, observed, delta, conf = _env_inputs()
    base = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                          observed=observed, architecture_delta=delta, conformance=conf)
    changed = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                             observed=observed,
                             architecture_delta={"new_capabilities": ["z"]},
                             conformance=conf)
    assert base["architecture_delta_hash"] != changed["architecture_delta_hash"]


def test_envelope_volatile_metadata_excluded():
    twin, observed, delta, conf = _env_inputs()
    base = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                          observed=observed, architecture_delta=delta, conformance=conf)
    obs2 = dict(observed)
    obs2["generated_at"] = "2099-01-01T00:00:00Z"  # volatile
    withvol = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                             observed=obs2, architecture_delta=delta, conformance=conf)
    assert base["observed_architecture_hash"] == withvol["observed_architecture_hash"]


def test_envelope_is_evidence_not_authority():
    twin, observed, delta, conf = _env_inputs()
    e = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                       observed=observed, architecture_delta=delta, conformance=conf)
    assert e["classification"] == "EVIDENCE_NOT_AUTHORITY"


def test_envelope_reports_p0_p1_and_invalid():
    twin, observed, delta, _ = _env_inputs()
    conf = {"counts": {P0: 1, P1: 0, P2: 0},
            "findings": [{"kind": "FORBIDDEN_DEPENDENCY", "severity": "P0"}],
            "metrics": {}}
    e = build_envelope(base_commit="b", source_commit="s", declared_twin=twin,
                       observed=observed, architecture_delta=delta, conformance=conf)
    assert e["p0_findings"] == 1 and e["architecture_valid"] is False


# ============================ CONTEXT SPINE (AC-30/31/32) ===================
def _spine_twin():
    caps = [cap("crm", routes=["/crm"], tables=["crm_"], tests=["tests/test_crm.py"]),
            cap("evidence", routes=["/evidence"]),
            cap("unrelated", routes=["/zzz"])]
    return mini_twin(caps, edges=[["crm", "evidence"], ["portal", "crm"]])


def test_context_spine_includes_critical_invariants():
    out = gen_spine(_spine_twin(), "crm")
    for inv in CRITICAL_INVARIANTS:
        assert inv in out["critical_invariants"]


def test_context_spine_correct_capability():
    out = gen_spine(_spine_twin(), "crm")
    assert out["capability_id"] == "crm"
    assert out["route_namespaces"] == ["/crm"]
    assert out["do_not_rebuild"] is True
    assert "crm" in out["canonical_owner"]


def test_context_spine_excludes_unrelated_bulk():
    out = gen_spine(_spine_twin(), "crm")
    blob = str(out)
    assert "unrelated" not in blob and "/zzz" not in blob


def test_context_spine_retains_source_paths():
    out = gen_spine(_spine_twin(), "crm")
    assert out["canonical_paths"]  # source paths for deeper inspection


def test_context_spine_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        gen_spine(_spine_twin(), "does_not_exist")


# ============================ DRIFT (AC-25/26) ==============================
def test_drift_snapshot_deterministic():
    conf = {"metrics": {"capabilities": 3, "capability_edges": 2, "sccs": 3,
                        "cyclic_sccs": 0, "routes": 5, "tables": 4,
                        "migrations": 2, "effect_observations": 0},
            "counts": {P0: 0, P1: 0, P2: 1}, "findings": []}
    observed = {"commit": "c1"}
    v1 = snapshot_vector(conf, observed)
    v2 = snapshot_vector(conf, observed)
    assert v1 == v2


def test_drift_delta_detects_change():
    prev = {"commit": "a", "capability_edges": 2, "cyclic_sccs": 0}
    cur = {"commit": "b", "capability_edges": 5, "cyclic_sccs": 1}
    d = delta(prev, cur)
    assert d["changes"]["capability_edges"]["delta"] == 3
    assert d["changes"]["cyclic_sccs"]["delta"] == 1


def test_drift_metric_alone_is_not_hard_failure():
    # advisory metrics live outside the P0/P1 gate; a P2-only report is valid
    conf = {"metrics": {}, "counts": {P0: 0, P1: 0, P2: 9}, "findings": []}
    v = snapshot_vector(conf, {"commit": "c"})
    assert v["p2_findings"] == 9  # recorded, not a gate


def test_ewma_smoothing():
    assert ewma([]) == 0.0
    assert ewma([1.0, 1.0, 1.0]) == 1.0


def test_append_history_replaces_same_commit():
    h = append_history([], {"commit": "c1", "x": 1})
    h = append_history(h, {"commit": "c1", "x": 2})
    assert len(h) == 1 and h[0]["x"] == 2


# ============================ WAIVERS (AC-36/37/38) =========================
def test_waiver_requires_owner():
    w = {"waiver_id": "w", "scope": "s", "reason": "r", "created_at": "2026-01-01",
         "expires_at": "2026-02-01", "status": "ACTIVE"}
    assert any("owner" in e for e in validate_waiver(w))


def test_active_scope_only_when_unexpired():
    w = [{"waiver_id": "w", "scope": "effect:x:requests", "reason": "r",
          "owner": "e", "created_at": "2026-06-01", "expires_at": "2026-08-01",
          "status": "ACTIVE"}]  # 61-day lifetime, within the 90-day cap
    assert "effect:x:requests" in active_scopes(w, "2026-07-11")
    assert active_scopes(w, "2026-09-01") == set()


def test_expired_waiver_is_p1():
    w = [{"waiver_id": "w", "scope": "s", "reason": "r", "owner": "e",
          "created_at": "2026-01-01", "expires_at": "2026-06-01",
          "status": "ACTIVE"}]
    f = expired_findings(w, "2026-07-11")
    assert f and f[0].severity == P1


def test_p0_p1_cannot_be_hidden_by_scores():
    # a P2-heavy report with one P1 is still INVALID (score can't override)
    from tools.architecture.conformance import ConformanceReport
    from tools.architecture.model import Finding, UNOWNED_NODE
    rep = ConformanceReport()
    for _ in range(50):
        rep.add(Finding("DYNAMIC_IMPORT_ADVISORY", P2, "x", "advisory"))
    rep.add(Finding(UNOWNED_NODE, P1, "x", "one real problem"))
    assert rep.valid is False


def test_waiver_status_report():
    w = [{"waiver_id": "w", "scope": "s", "reason": "r", "owner": "e",
          "created_at": "2026-06-01", "expires_at": "2026-08-01", "status": "ACTIVE"}]
    r = status_report(w, "2026-07-11")
    assert r["total"] == 1 and r["active"] == 1 and r["expired"] == 0
