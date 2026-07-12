"""FINALIS SP0007 — Compatibility, Migration & Versioning (AC-0007-126..190).

Migration graph + path selection, transformers + loss vectors, expand-migrate-
verify-contract, dual-read/dual-write + shadow, checkpointed backfill + lease +
barrier, last-safe-rollback-point + round-trip, deprecation + sunset gate,
fitness functions + debt registry + observatory, and change intent + impact
cone.

Imports ONLY from ``tools.compatibility.*`` (governance tooling). Each test
comment-maps to the AC id(s) it covers.
"""
from __future__ import annotations

from tools.compatibility import (migration, transformer, backfill, rollback,
                                 plan, deprecation, fitness, intent)
from tools.compatibility.backfill import committed_ids
from tools.compatibility.model import (
    LOSS_DIMENSIONS, MIGRATION_PATH_MISSING, ROLLBACK_NOT_AVAILABLE,
    LAST_SAFE_ROLLBACK_POINT_REACHED, MIGRATION_LOSS_UNDECLARED,
    ROUND_TRIP_FAILED, CROSS_TENANT_MIGRATION_DETECTED,
    MIGRATION_CONCURRENCY_CONFLICT, DUAL_WRITE_DIVERGENCE,
    DUAL_READ_DIVERGENCE, DEPRECATION_WITH_ACTIVE_CONSUMER, UNKNOWN_CONSUMER,
    CONSUMER_INCOMPATIBLE, CONTRACT_OWNER_MISSING, INVALID_COMPAT_SCHEMA)


def _k(fs) -> set:
    """Set of finding kinds from a findings list."""
    return {f.kind for f in fs}


def _sev(fs) -> set:
    """Set of severities from a findings list."""
    return {f.severity for f in fs}


def _ids(items) -> list:
    return [i.get("id") for i in items]


def _clean_edge(**over) -> dict:
    e = {
        "migration_edge_id": "E1",
        "contract_id": "C1",
        "from_version": "1.0.0",
        "to_version": "2.0.0",
        "transformer_ref": "T1",
        "inverse_transformer_ref": "T1_inv",
        "inverse_verified": True,
        "preconditions": [],
        "postconditions": [],
        "loss_vector": {d: "NONE" for d in LOSS_DIMENSIONS},
        "reversibility": "REVERSIBLE",
        "last_safe_rollback_point": "s1",
        "operational_risk": 0,
    }
    e.update(over)
    return e


# ---------------------------------------------------------------------------
# Migration edges — AC-0007-126..132
# ---------------------------------------------------------------------------
def test_validate_clean_reversible_edge_ac126():
    # AC-0007-126/131: a REVERSIBLE edge with a real inverse is well-formed.
    assert migration.validate_edge(_clean_edge()) == []


def test_reversible_without_inverse_is_rollback_not_available_ac131():
    # AC-0007-131: REVERSIBLE claim without inverse_transformer_ref => P0.
    fs = migration.validate_edge(_clean_edge(inverse_transformer_ref=None))
    assert ROLLBACK_NOT_AVAILABLE in _k(fs)
    assert any(f.severity == "P0" and f.kind == ROLLBACK_NOT_AVAILABLE
               for f in fs)


def test_one_way_without_rollback_point_is_p1_ac132():
    # AC-0007-132: a ONE_WAY edge must declare its last safe rollback point.
    fs = migration.validate_edge(
        _clean_edge(reversibility="ONE_WAY", last_safe_rollback_point=None))
    assert any(f.severity == "P1" and f.kind == INVALID_COMPAT_SCHEMA
               for f in fs)


# ---------------------------------------------------------------------------
# Loss vectors — AC-0007-133..141
# ---------------------------------------------------------------------------
def test_new_loss_vector_all_none_ac133():
    # AC-0007-133: a fresh loss vector declares every dimension NONE.
    assert transformer.new_loss_vector() == {d: "NONE" for d in LOSS_DIMENSIONS}


def test_critical_loss_is_non_compensatory_p0_ac139():
    # AC-0007-139: a critical dimension (authority_loss) above NONE is P0.
    lv = transformer.new_loss_vector()
    lv["authority_loss"] = "HIGH"
    fs = transformer.critical_loss_findings(lv)
    assert MIGRATION_LOSS_UNDECLARED in _k(fs)
    assert all(f.severity == "P0" for f in fs)
    assert any(f.details.get("non_compensatory") for f in fs)


def test_observed_loss_beyond_declared_is_undeclared_ac137():
    # AC-0007-137: observed loss exceeding declared loss => P0.
    declared = transformer.new_loss_vector()
    observed = transformer.new_loss_vector()
    observed["field_loss"] = "HIGH"
    fs = transformer.observed_loss_findings(declared, observed)
    assert MIGRATION_LOSS_UNDECLARED in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_one_way_declaration_requires_explicit_flag_ac141():
    # AC-0007-141: ONE_WAY without irreversible_declared=True is P0.
    edge = _clean_edge(reversibility="ONE_WAY",
                       last_safe_rollback_point="s1",
                       forward_fix_plan_ref="FF1")
    fs = transformer.one_way_declaration_findings(edge)
    assert fs and all(f.severity == "P0" for f in fs)
    assert INVALID_COMPAT_SCHEMA in _k(fs)


# ---------------------------------------------------------------------------
# Path finding / selection — AC-0007-144/145
# ---------------------------------------------------------------------------
def _abc_edges():
    return [
        _clean_edge(migration_edge_id="AB", from_version="A", to_version="B"),
        _clean_edge(migration_edge_id="BC", from_version="B", to_version="C"),
    ]


def test_find_path_reachable_and_unreachable_ac144():
    # AC-0007-144: BFS finds a reachable target and reports the miss otherwise.
    edges = _abc_edges()
    assert migration.find_path(edges, "A", "C")["found"] is True
    assert migration.find_path(edges, "A", "Z")["found"] is False


def test_path_findings_missing_path_ac126():
    # AC-0007-126: no declared path => MIGRATION_PATH_MISSING.
    fs = migration.path_findings(_abc_edges(), "A", "Z")
    assert MIGRATION_PATH_MISSING in _k(fs)


def test_select_path_prefers_reversible_multi_hop_ac145():
    # AC-0007-145: lexicographic selection — fewer irreversible edges wins,
    # so a REVERSIBLE 2-hop beats a ONE_WAY direct edge.
    edges = [
        _clean_edge(migration_edge_id="DIRECT", from_version="A",
                    to_version="C", reversibility="ONE_WAY",
                    inverse_transformer_ref=None,
                    last_safe_rollback_point="s0"),
        _clean_edge(migration_edge_id="P1", from_version="A", to_version="B"),
        _clean_edge(migration_edge_id="P2", from_version="B", to_version="C"),
    ]
    res = migration.select_path(edges, "A", "C")
    assert res["found"] is True
    assert res["edge_ids"] == ["P1", "P2"]
    assert res["criteria"]["irreversible_edges"] == 0


def test_no_transitive_edge_when_only_multi_hop_ac145():
    # AC-0007-145: a composite path is never a direct edge (no transitivity).
    assert migration.no_transitive_edge(_abc_edges(), "A", "C") is False


# ---------------------------------------------------------------------------
# Expand-migrate-verify-contract plan — AC-0007-146..152
# ---------------------------------------------------------------------------
def _clean_plan(**over) -> dict:
    p = {
        "migration_plan_id": "MP1",
        "source_versions": ["1.0.0"],
        "target_version": "2.0.0",
        "expand_phase": {},
        "migrate_phase": {},
        "verify_phase": {},
        "contract_phase": {},
        "status": "DRAFT",
        "steps": [{"step_id": "s1", "idempotency_key": "k1",
                   "phase": "EXPAND"}],
    }
    p.update(over)
    return p


def test_validate_plan_clean_ac146():
    # AC-0007-146..150: a full four-phase plan with idempotent steps is clean.
    assert plan.validate_plan(_clean_plan()) == []


def test_validate_plan_missing_phase_is_p1_ac147():
    # AC-0007-147: a plan missing a phase dict => P1.
    p = _clean_plan()
    del p["contract_phase"]
    fs = plan.validate_plan(p)
    assert any(f.severity == "P1" and f.kind == INVALID_COMPAT_SCHEMA
               for f in fs)


def test_expand_breaking_old_consumers_p0_ac151():
    # AC-0007-151: EXPAND that breaks old consumers => P0.
    p = _clean_plan(expand_phase={"breaks_old_consumers": True})
    fs = plan.expand_phase_findings(p)
    assert CONSUMER_INCOMPATIBLE in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_contract_gated_on_unmigrated_critical_consumer_p0_ac152():
    # AC-0007-152: CONTRACT with an unmigrated C3 consumer => P0.
    fs = plan.contract_phase_findings(
        _clean_plan(),
        bindings=[{"consumer_id": "c3", "criticality": "C3",
                   "migrated": False}])
    assert CONSUMER_INCOMPATIBLE in _k(fs)
    assert any(f.severity == "P0" for f in fs)


# ---------------------------------------------------------------------------
# Shadow modes — AC-0007-153/154
# ---------------------------------------------------------------------------
def test_shadow_authoritative_state_p0_ac153():
    # AC-0007-153: a shadow that creates authoritative state => P0.
    fs = plan.shadow_findings({"shadow_id": "sh",
                               "creates_authoritative_state": True})
    assert fs and all(f.severity == "P0" for f in fs)


def test_shadow_externally_visible_p0_ac154():
    # AC-0007-154: a shadow with externally visible effects => P0.
    fs = plan.shadow_findings({"shadow_id": "sh", "externally_visible": True})
    assert fs and all(f.severity == "P0" for f in fs)


# ---------------------------------------------------------------------------
# Dual read / dual write — AC-0007-155..157
# ---------------------------------------------------------------------------
def test_dual_read_divergence_p1_ac155():
    # AC-0007-155: readers that differ => DUAL_READ_DIVERGENCE (P1).
    result = plan.dual_read(
        lambda p: p,
        lambda p: {**p, "extra": 1},
        [{"fixture_id": "f1", "payload": {"a": 1}}])
    assert result["differences"]
    fs = plan.dual_read_findings(result)
    assert DUAL_READ_DIVERGENCE in _k(fs)
    assert any(f.severity == "P1" for f in fs)


def test_dual_write_missing_controls_and_divergence_ac156():
    # AC-0007-156/157: missing controls => P1; observed divergence with no
    # reconciliation => DUAL_WRITE_DIVERGENCE (P0).
    fs = plan.dual_write_findings({"contract_id": "c1",
                                   "divergence": [{"x": 1}]})
    assert DUAL_WRITE_DIVERGENCE in _k(fs)
    assert any(f.severity == "P0" and f.kind == DUAL_WRITE_DIVERGENCE
               for f in fs)
    assert any(f.severity == "P1" and f.kind == INVALID_COMPAT_SCHEMA
               for f in fs)


# ---------------------------------------------------------------------------
# Checkpointed backfill / lease / barrier — AC-0007-158..165
# ---------------------------------------------------------------------------
def _tx(item):
    return {"id": item["id"], "v": 1}


def test_backfill_commits_and_seals_checkpoint_ac158():
    # AC-0007-158: run_batch commits a deterministic batch and seals a
    # checkpoint.
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    state = backfill.new_backfill(items, batch_size=2)
    s1 = backfill.run_batch(state, _tx)
    assert len(s1["checkpoints"]) == 1
    assert len(s1["processed"]) == 2
    assert committed_ids(s1) == {"a", "b"}


def test_backfill_batch_is_idempotent_ac159():
    # AC-0007-159: re-submitting the same batch never duplicates commits.
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    s1 = backfill.run_batch(backfill.new_backfill(items, batch_size=2), _tx)
    replay = {**s1, "pending": [{"id": "a"}, {"id": "b"}]}
    s2 = backfill.run_batch(replay, _tx)
    assert committed_ids(s2) == committed_ids(s1) == {"a", "b"}
    assert len(s2["processed"]) == 2
    assert len(s2["checkpoints"]) == 1


def test_backfill_resume_skips_committed_ac160():
    # AC-0007-160: resume after a restart does not reprocess committed ids.
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    s1 = backfill.run_batch(backfill.new_backfill(items, batch_size=2), _tx)
    crashed = {**s1, "pending": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    resumed = backfill.resume(crashed)
    assert _ids(resumed["pending"]) == ["c"]


def test_checkpoint_findings_clean_on_good_state_ac161():
    # AC-0007-161: a well-formed checkpointed state has no findings.
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    s1 = backfill.run_batch(backfill.new_backfill(items, batch_size=2), _tx)
    assert backfill.checkpoint_findings(s1) == []


def test_lease_single_owner_per_scope_ac163():
    # AC-0007-163/164: one owner per scope; a second owner is P0 and acquires
    # nothing.
    l1, f1 = backfill.acquire_lease({}, "scope", "o1")
    assert f1 == [] and l1["scope"] == "o1"
    l2, f2 = backfill.acquire_lease(l1, "scope", "o2")
    assert MIGRATION_CONCURRENCY_CONFLICT in _k(f2)
    assert any(f.severity == "P0" for f in f2)
    assert l2["scope"] == "o1"


def test_barrier_blocks_incompatible_write_ac165():
    # AC-0007-165: an active barrier blocks an incompatible concurrent write.
    fs = backfill.barrier_findings(
        {"active": True, "scope": "s1"},
        {"scope": "s1", "writer": "w", "compatible": False})
    assert MIGRATION_CONCURRENCY_CONFLICT in _k(fs)
    assert any(f.severity == "P0" for f in fs)


# ---------------------------------------------------------------------------
# Round-trip / rollback boundary — AC-0007-166..170
# ---------------------------------------------------------------------------
def test_round_trip_passes_ac166():
    # AC-0007-166: a genuine inverse round-trips.
    res = transformer.round_trip(
        {"a": 1},
        lambda d: {**d, "m": 1},
        lambda d: {k: v for k, v in d.items() if k != "m"})
    assert res["passed"] is True


def test_round_trip_failure_is_p0_ac167():
    # AC-0007-167: a lossy pair (down != inverse) => ROUND_TRIP_FAILED (P0).
    res = transformer.round_trip(
        {"a": 1},
        lambda d: {**d, "m": 1},
        lambda d: d)  # fails to strip 'm' — not the true inverse
    assert res["passed"] is False
    fs = transformer.round_trip_findings(
        {"migration_edge_id": "E", "reversibility": "REVERSIBLE"}, res)
    assert ROUND_TRIP_FAILED in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_rollback_plan_requires_verified_inverse_ac169():
    # AC-0007-169: rollback plan on an edge without a verified inverse => P0.
    edge = _clean_edge(inverse_verified=False)
    fs = rollback.validate_rollback_plan(
        {"plan_id": "P", "edge_ids": ["E1"]}, {"E1": edge})
    assert ROLLBACK_NOT_AVAILABLE in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_boundary_after_last_safe_point_ac170():
    # AC-0007-170: past the last safe rollback point => rollback blocked (P0).
    fs = rollback.boundary_findings(
        {"plan_id": "P", "step_order": ["s1", "s2", "s3"],
         "last_safe_rollback_point": "s1"},
        current_position="s3")
    assert LAST_SAFE_ROLLBACK_POINT_REACHED in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_cross_tenant_migration_detected():
    # INV-0007-50: a record changing tenant during migration => P0.
    fs = transformer.tenant_findings(
        [{"id": "r1", "tenant_id": "t1"}],
        [{"id": "r1", "tenant_id": "t2"}])
    assert CROSS_TENANT_MIGRATION_DETECTED in _k(fs)
    assert any(f.severity == "P0" for f in fs)


# ---------------------------------------------------------------------------
# Deprecation / sunset — AC-0007-171..182
# ---------------------------------------------------------------------------
def _clean_notice(**over) -> dict:
    n = {
        "deprecation_id": "DEP1",
        "contract_id": "C1",
        "version": "1.0.0",
        "surface": "api.v1",
        "reason": "superseded",
        "replacement": "C1@2.0.0",
        "support_until": "2027-01-01",
        "status": "ANNOUNCED",
    }
    n.update(over)
    return n


def test_validate_notice_clean_ac171():
    # AC-0007-171..174: a full deprecation notice is clean.
    assert deprecation.validate_notice(_clean_notice()) == []


def test_notice_missing_replacement_p1_ac173():
    # AC-0007-173: a deprecated surface with no replacement => P1.
    n = _clean_notice()
    del n["replacement"]
    fs = deprecation.validate_notice(n)
    assert any(f.severity == "P1" and f.kind == INVALID_COMPAT_SCHEMA
               for f in fs)


def test_retired_with_active_consumer_p0_ac176():
    # AC-0007-176: retirement with an active unmigrated consumer => P0.
    fs = deprecation.removal_findings(
        _clean_notice(status="RETIRED"),
        [{"contract_id": "C1", "consumer_id": "cons1", "active": True,
          "migrated": False}])
    assert DEPRECATION_WITH_ACTIVE_CONSUMER in _k(fs)
    assert any(f.severity == "P0" for f in fs)


def test_sunset_gate_blocked_by_unknown_consumers_ac180():
    # AC-0007-180: unknown critical consumers => not ready, UNKNOWN_CONSUMER P0.
    res = deprecation.sunset_gate(
        _clean_notice(),
        bindings=[],
        support_window={"satisfied": True},
        historical_readers_ok=True,
        rollback_or_forward_fix_ready=True,
        unknown_critical_consumers=True)
    assert res["sunset_ready"] is False
    assert res["blockers"]
    assert UNKNOWN_CONSUMER in _k(res["findings"])
    assert any(f.severity == "P0" and f.kind == UNKNOWN_CONSUMER
               for f in res["findings"])


def test_support_window_waiver_needs_expiry_p1_ac182():
    # AC-0007-182: EXTENDED_WITH_WAIVER without waiver_expires_at => P1.
    fs = deprecation.validate_support_window(
        {"window_id": "w1", "status": "EXTENDED_WITH_WAIVER"})
    assert any(f.severity == "P1" and f.kind == INVALID_COMPAT_SCHEMA
               for f in fs)


# ---------------------------------------------------------------------------
# Fitness / debt / observatory / intent — AC-0007-183..190
# ---------------------------------------------------------------------------
def test_fitness_ownerless_protected_contract_ac184():
    # AC-0007-184: an ownerless STABLE C3 descriptor => CONTRACT_OWNER_MISSING.
    fs = fitness.fitness_findings(
        {"descriptors": [{"contract_id": "C1", "stability": "STABLE",
                          "criticality": "C3"}]})
    assert CONTRACT_OWNER_MISSING in _k(fs)


def test_debt_registry_count_keys_ac183():
    # AC-0007-183: migration debt is named and counted explicitly.
    debt = fitness.debt_registry({})
    expected = {"supported_old_versions", "retained_adapters",
                "dual_write_active", "unmigrated_consumers", "stale_claims",
                "one_way_edges", "replay_gaps", "unowned_contracts"}
    assert expected <= set(debt)
    assert all(isinstance(debt[k], int) for k in expected)


def test_observatory_is_advisory_ac188():
    # AC-0007-188: the observatory dashboard is advisory, never a gate.
    assert fitness.observatory({})["classification"] == "ADVISORY_NOT_A_GATE"


def test_intent_missing_directions_p1_ac189():
    # AC-0007-189: a change intent with no compatibility directions => P1.
    ci = {"intent_id": "CI1", "surface": "api.v1", "old_version": "1.0.0",
          "new_version": "2.0.0", "consumers": [],
          "migration_plan_ref": "MP1", "proof_impact": "none",
          "security_impact": "none", "deprecation_ref": None,
          "rollback_ref": "RB1"}
    fs = intent.validate_intent(ci)
    assert any("compatibility direction" in f.message and f.severity == "P1"
               for f in fs)


def test_impact_cone_is_advisory_ac190():
    # AC-0007-190: the impact cone is advisory reach analysis.
    cone = intent.impact_cone({"contract_id": "C1"}, graph={}, bindings=[])
    assert cone["classification"] == "ADVISORY"
