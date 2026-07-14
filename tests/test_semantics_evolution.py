"""Transaction, shadow eval, historical replay, quarantine, envelope, intent, drift.

Covers SP0002 AC 40,42-50,70-74.
"""
from __future__ import annotations

from tools.semantics.drift import snapshot_vector, delta
from tools.semantics.envelope import build_envelope
from tools.semantics.intent import validate_intent, is_breaking
from tools.semantics.quarantine import (quarantine_item, resolve_item,
                                        creates_authority)
from tools.semantics.replay import replay
from tools.semantics.shadow import shadow_evaluate
from tools.semantics.transaction import evaluate_change
from tests._sem_helpers import concept, registry


# ============================ CHANGE INTENT (AC-40) ========================
def test_intent_valid():
    assert validate_intent({"change_id": "c1", "base_epoch": "e1",
                            "target_concepts": ["work.task"],
                            "change_classes": ["NARROWING"]}) == []


def test_intent_invalid_class():
    errs = validate_intent({"change_id": "c1", "base_epoch": "e1",
                            "target_concepts": [], "change_classes": ["WILD"]})
    assert any("invalid change_class" in e for e in errs)


def test_breaking_intent_detected():
    assert is_breaking({"change_classes": ["WIDENING"]})
    assert not is_breaking({"change_classes": ["EDITORIAL"]})


# ============================ TRANSACTION (AC-42,43) =======================
def _base():
    return registry([concept("c-0001", "outcome.business_outcome", world="CLOSED_WORLD",
                             models=["won_verified"]),
                     concept("c-0002", "lifecycle.completion", world="CLOSED_WORLD")])


def test_clean_atomic_change_passes():
    base = _base()
    cand = _base()  # identical -> no change
    intent = {"change_id": "c1", "base_epoch": "e1",
              "target_concepts": [], "change_classes": ["EDITORIAL"]}
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert rep.valid


def test_breaking_change_without_epoch_fails():
    base = _base()
    cand = registry([concept("c-0001", "outcome.business_outcome", world="CLOSED_WORLD",
                             models=["won_verified", "won_unverified"]),  # WIDENING
                     concept("c-0002", "lifecycle.completion", world="CLOSED_WORLD")])
    intent = {"change_id": "c1", "base_epoch": "e1",
              "target_concepts": ["outcome.business_outcome"],
              "change_classes": ["WIDENING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert any(f.kind == "BREAKING_CHANGE_WITHOUT_EPOCH" and f.severity == "P0"
               for f in rep.findings)


def test_breaking_change_with_new_epoch_ok():
    base = _base()
    cand = registry([concept("c-0001", "outcome.business_outcome", world="CLOSED_WORLD",
                             models=["won_verified", "won_unverified"]),
                     concept("c-0002", "lifecycle.completion", world="CLOSED_WORLD")])
    intent = {"change_id": "c1", "base_epoch": "e1",
              "target_concepts": ["outcome.business_outcome"],
              "change_classes": ["WIDENING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=True, check_owner=False)
    assert not any(f.kind == "BREAKING_CHANGE_WITHOUT_EPOCH" for f in rep.findings)


def test_partial_rollout_fails():
    base = registry([concept("c-0001", "x.y", definition="A",
                             projections={"openapi": "ref", "lggt": "ref"})])
    cand = registry([concept("c-0001", "x.y", definition="B changed",
                             projections={"openapi": "ref", "lggt": "ref"})])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["NARROWING"]}
    # updated_projections empty -> partial rollout
    rep = evaluate_change(base, cand, intent, new_epoch=True,
                          updated_projections=set(), check_owner=False)
    assert any(f.kind == "PARTIAL_SEMANTIC_TRANSACTION" and f.severity == "P0"
               for f in rep.findings)


def test_full_rollout_passes():
    base = registry([concept("c-0001", "x.y", definition="A",
                             projections={"openapi": "ref"})])
    cand = registry([concept("c-0001", "x.y", definition="B changed",
                             projections={"openapi": "ref"})])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["NARROWING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=True,
                          updated_projections={"openapi"}, check_owner=False)
    assert not any(f.kind == "PARTIAL_SEMANTIC_TRANSACTION" for f in rep.findings)


# ============================ SHADOW (AC-44,46) ============================
def test_shadow_expected_divergence_accepted():
    scen = [{"id": 1}, {"id": 2}]
    out = shadow_evaluate(scen, lambda x: "old", lambda x: "new" if x["id"] == 1 else "old",
                          expected_changed={1})
    assert out["counts"]["EXPECTED_CHANGED"] == 1
    assert not out["has_unexpected"]
    assert out["side_effects"] is False


def test_shadow_unexpected_divergence_detected():
    scen = [{"id": 1}]
    out = shadow_evaluate(scen, lambda x: "old", lambda x: "new", expected_changed=set())
    assert out["has_unexpected"]


# ============================ REPLAY (AC-45,46) ============================
def test_replay_reproduces_old_results():
    fx = [{"id": "h1"}, {"id": "h2"}]
    out = replay(fx, lambda r: "R", lambda r: "R")
    assert out["unexplained"] == 0
    assert all(r["status"] == "REPRODUCED" for r in out["rows"])


def test_replay_documented_delta_ok():
    fx = [{"id": "h1"}]
    out = replay(fx, lambda r: "old", lambda r: "new", documented_deltas={"h1": "new"})
    assert out["unexplained"] == 0
    assert out["rows"][0]["status"] == "DOCUMENTED_DELTA"


def test_replay_unexplained_divergence_is_finding():
    fx = [{"id": "h1"}]
    out = replay(fx, lambda r: "old", lambda r: "new")
    assert out["unexplained"] == 1
    assert out["findings"][0]["kind"] == "HISTORICAL_REPLAY_DIVERGENCE"


# ============================ QUARANTINE (AC-47..50) =======================
def test_unknown_quarantined_no_authority():
    item = quarantine_item("mysteryterm", "UNKNOWN_SEMANTIC")
    assert item["state"] == "QUARANTINED"
    assert creates_authority(item) is False


def test_ambiguous_quarantined():
    item = quarantine_item("bank", "AMBIGUOUS_SEMANTIC")
    assert item["reason"] == "AMBIGUOUS_SEMANTIC"


def test_resolved_item_leaves_quarantine_without_authority():
    item = quarantine_item("x", "UNKNOWN_SEMANTIC")
    resolved = resolve_item(item, "RESOLVED_EXISTING_CONCEPT", concept_key="work.task")
    assert resolved["state"] == "RESOLVED_EXISTING_CONCEPT"
    assert creates_authority(resolved) is False   # never creates authority


# ============================ ENVELOPE (AC-70..72) =========================
def _env(**over):
    base = registry([concept("c-0001", "x.y")])
    cand = over.get("cand", registry([concept("c-0001", "x.y")]))
    return build_envelope(base_epoch="e1", candidate_epoch="e2",
                          base_registry=base, candidate_registry=cand,
                          change_intent={"change_id": "c1"}, compatibility={},
                          impact={}, shadow={}, replay={}, lggt_result={},
                          translation_result={},
                          conformance={"counts": {"P0": 0, "P1": 0, "P2": 0}})


def test_envelope_deterministic():
    assert _env()["envelope_hash"] == _env()["envelope_hash"]


def test_envelope_changes_when_registry_changes():
    a = _env()
    b = _env(cand=registry([concept("c-0001", "x.y", definition="changed")]))
    assert a["new_registry_hash"] != b["new_registry_hash"]


def test_envelope_is_evidence_not_authority():
    assert _env()["classification"] == "EVIDENCE_NOT_AUTHORITY"


def test_envelope_reports_validity():
    assert _env()["semantic_valid"] is True


# ============================ DRIFT (AC-73,74) =============================
def test_drift_snapshot_deterministic():
    reg = registry([concept("c-0001", "work.task")])
    conf = {"findings": [], "counts": {"P0": 0, "P1": 0, "P2": 1}}
    assert snapshot_vector(reg, conf) == snapshot_vector(reg, conf)


def test_drift_delta_detects_change():
    prev = {"concepts": 30, "ambiguities": 0}
    cur = {"concepts": 33, "ambiguities": 1}
    d = delta(prev, cur)
    assert d["changes"]["concepts"]["delta"] == 3
    assert d["changes"]["ambiguities"]["delta"] == 1


def test_drift_metric_is_advisory_not_gate():
    reg = registry([concept("c-0001", "work.task")])
    conf = {"findings": [], "counts": {"P0": 0, "P1": 0, "P2": 9}}
    v = snapshot_vector(reg, conf)
    assert v["p2_findings"] == 9   # recorded, not a hard gate
