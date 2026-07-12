"""SP0007 adversarial mutation campaign (§20.35, AC-0007-197) + bounded model
checking + proof envelopes (AC-0007-191..196).

Each mutation injects one compatibility violation and asserts the kernel KILLS
it — the dual of the green baseline, proving the gates are not vacuous. 20
mutants, one per §20.35 row.
"""
from __future__ import annotations

import pytest

from tools.compatibility.contracts import (release, mutation_findings,
                                            semver_declaration_findings)
from tools.compatibility.diff import breaking_findings, classify, diff_contracts
from tools.compatibility.policies import (reserved_identifier_findings,
                                          preservation_findings, enum_evolution,
                                          default_change_findings,
                                          event_identity_findings,
                                          idempotency_findings)
from tools.compatibility.negotiation import (pinning_findings, downgrade_findings,
                                             validate_adapter)
from tools.compatibility.transformer import (observed_loss_findings,
                                             tenant_findings)
from tools.compatibility.backfill import new_backfill, run_batch, duplicate_findings
from tools.compatibility.rollback import boundary_findings, validate_rollback_plan
from tools.compatibility.replay import (replay_findings,
                                        proof_interpretability_findings)
from tools.compatibility.deprecation import removal_findings
from tools.compatibility.vector import transitive_inference_findings, build_claim
from tools.compatibility import modelcheck as MC, envelope as ENV
from tools.compatibility.model import (
    SEMVER_MISMATCH, BREAKING_CHANGE_DETECTED, ENUM_EVOLUTION_BREAKING,
    RESERVED_IDENTIFIER_REUSED, UNKNOWN_FIELD_LOSS, VERSION_DOWNGRADE_DETECTED,
    SECURITY_DOWNGRADE_BLOCKED, EVENT_IDENTITY_CHANGED,
    IDEMPOTENCY_CONTRACT_CHANGED, MIGRATION_LOSS_UNDECLARED,
    CROSS_TENANT_MIGRATION_DETECTED, LAST_SAFE_ROLLBACK_POINT_REACHED,
    ROLLBACK_NOT_AVAILABLE, WORKFLOW_REPLAY_FAILED, PROOF_VERSION_UNREADABLE,
    DEPRECATION_WITH_ACTIVE_CONSUMER, CONTRACT_VERSION_MUTATED,
    TRANSITIVITY_ASSUMED, DEFAULT_VALUE_BEHAVIOR_CHANGED, PROOF_ENVELOPE_MISMATCH)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _field(**kw):
    base = {"type": "string", "required": False, "nullable": False,
            "default": None, "enum": None, "constraints": {},
            "field_number": 1, "security_relevant": False}
    base.update(kw)
    return base


def _schema(fields=None, **extra):
    s = {"fields": fields or {}, "temporal": {}, "event_identity": {},
         "idempotency": {}, "ordering": []}
    s.update(extra)
    return {"schema": s}   # diff_contracts reads version["schema"]


# M1 — breaking change labeled patch
def test_m1_breaking_labeled_patch_killed():
    assert SEMVER_MISMATCH in _k(semver_declaration_findings("1.0.0", "1.0.1",
                                                             True))


# M2 — required field added
def test_m2_required_field_added_killed():
    old = _schema({"a": _field(required=True)})
    new = _schema({"a": _field(required=True), "b": _field(required=True)})
    assert classify(diff_contracts(old, new))["is_breaking"]
    assert BREAKING_CHANGE_DETECTED in _k(breaking_findings(old, new))


# M3 — enum value added to closed consumer
def test_m3_enum_added_closed_world_killed():
    assert enum_evolution(["A"], ["A", "B"], "CLOSED")["classification"] \
        == "BREAKING"
    old = _schema({"s": _field(enum=["A"])})
    new = _schema({"s": _field(enum=["A", "B"])})
    assert ENUM_EVOLUTION_BREAKING in _k(breaking_findings(
        old, new, consumer={"enum_world": "CLOSED"}))


# M4 — field number reused
def test_m4_field_number_reused_killed():
    reg = {"reserved_field_numbers": [7], "reserved_enum_codes": [],
           "reserved_event_ids": [], "reserved_field_names": []}
    cand = {"contract_id": "CT",
            "schema": {"fields": {"newf": _field(field_number=7)}}}
    assert RESERVED_IDENTIFIER_REUSED in _k(reserved_identifier_findings(reg,
                                                                        cand))


# M5 — unknown field dropped under PRESERVE
def test_m5_unknown_field_dropped_killed():
    orig = {"a": 1, "x_unknown": 9}
    roundtripped = {"a": 1}
    assert UNKNOWN_FIELD_LOSS in _k(preservation_findings(
        orig, roundtripped, {"a"}, "PRESERVE"))


# M6 — security default weakened
def test_m6_security_default_weakened_killed():
    old = _field(default="STRICT", security_relevant=True)
    new = _field(default="OFF", security_relevant=True)
    f = default_change_findings(old, new, name="tls_mode")
    assert DEFAULT_VALUE_BEHAVIOR_CHANGED in _k(f)
    assert any(x.severity == "P0" for x in f)


# M7 — provider version floats to latest
def test_m7_floating_latest_killed():
    assert VERSION_DOWNGRADE_DETECTED in _k(pinning_findings(
        {"contract_id": "CT", "protected": True, "version": "latest"}))


# M8 — event identity changed
def test_m8_event_identity_changed_killed():
    old = {"dedup_key": "event_id"}
    new = {"dedup_key": "run_id"}
    assert EVENT_IDENTITY_CHANGED in _k(event_identity_findings(old, new))


# M9 — idempotency scope changed
def test_m9_idempotency_scope_changed_killed():
    assert IDEMPOTENCY_CONTRACT_CHANGED in _k(idempotency_findings(
        {"scope": "run"}, {"scope": "global"}))


# M10 — migration rerun duplicates state
def test_m10_duplicate_batch_killed():
    st = new_backfill(list(range(4)), batch_size=2)
    st = run_batch(st, lambda x: x)
    committed = list(st["processed"])
    assert duplicate_findings(st, committed)   # re-committing sealed ids


# M11 — dual writes diverge / undeclared loss
def test_m11_undeclared_loss_killed():
    declared = {d: "NONE" for d in
                ("field_loss", "semantic_loss", "precision_loss", "history_loss",
                 "provenance_loss", "authority_loss", "evidence_loss",
                 "ordering_loss", "referential_loss")}
    observed = dict(declared, field_loss="HIGH")
    assert MIGRATION_LOSS_UNDECLARED in _k(observed_loss_findings(declared,
                                                                 observed))


# M12 — rollback loses new data (rollback after boundary)
def test_m12_rollback_after_boundary_killed():
    plan = {"rollback_plan_id": "RB", "step_order": ["s1", "s2", "s3"],
            "last_safe_rollback_point": "s2"}
    assert LAST_SAFE_ROLLBACK_POINT_REACHED in _k(
        boundary_findings(plan, current_position="s3"))


# M13 — workflow replay diverges
def test_m13_workflow_replay_diverges_killed():
    table = {"A": {"go": "B"}}   # missing B->done
    histories = [[{"event": "go", "to_state": "B"},
                  {"event": "finish", "to_state": "DONE"}]]
    assert WORKFLOW_REPLAY_FAILED in _k(replay_findings(histories, table,
                                                        initial="A"))


# M14 — semantic meaning changes without epoch (default behavioral change)
def test_m14_default_behavior_change_flagged():
    old = _field(default="A")
    new = _field(default="B")
    assert DEFAULT_VALUE_BEHAVIOR_CHANGED in _k(default_change_findings(
        old, new, name="mode"))


# M15 — proof hash changes without a reader (unreadable historical proof)
def test_m15_proof_version_unreadable_killed():
    assert PROOF_VERSION_UNREADABLE in _k(proof_interpretability_findings(
        {"envelope_version": "proof-v0"}, {"proof-v1": {"reader": "r"}}))


# M16 — deprecated surface removed with active consumer
def test_m16_removal_with_active_consumer_killed():
    notice = {"deprecation_id": "D", "contract_id": "CT", "status": "RETIRED"}
    bindings = [{"consumer_id": "c", "contract_id": "CT", "active": True,
                 "migrated": False}]
    assert DEPRECATION_WITH_ACTIVE_CONSUMER in _k(removal_findings(notice,
                                                                  bindings))


# M17 — released contract version mutated in place
def test_m17_released_version_mutated_killed():
    v = release({"contract_id": "CT", "version": "1.0.0", "semantic_epoch": "e1",
                 "schema": {"fields": {"a": _field()}}})
    mutated = dict(v, schema={"fields": {"a": _field(type="int")}})
    assert CONTRACT_VERSION_MUTATED in _k(mutation_findings(v, mutated))


# M18 — compatibility inferred transitively
def test_m18_transitive_inference_killed():
    c1 = build_claim(claim_id="C1", contract_id="CT", producer_version="1",
                     consumer_id="x", consumer_version="1",
                     direction="NEW_PRODUCER_TO_OLD_CONSUMER",
                     scenario_scope=["s"], evidence_refs=["fx"],
                     validator_version="v", tested_at="d")
    inferred = dict(c1, claim_id="C9", evidence_refs=["C1"])
    assert TRANSITIVITY_ASSUMED in _k(transitive_inference_findings([c1],
                                                                    inferred))


# M19 — tenant-crossing transformer
def test_m19_cross_tenant_transformer_killed():
    before = [{"id": "r1", "tenant_id": "t1"}]
    after = [{"id": "r1", "tenant_id": "t2"}]
    assert CROSS_TENANT_MIGRATION_DETECTED in _k(tenant_findings(before, after))


# M20 — security downgrade
def test_m20_security_downgrade_killed():
    rank = {"v-tls13": 2, "v-tls10": 1}
    assert SECURITY_DOWNGRADE_BLOCKED in _k(downgrade_findings(
        "v-tls13", "v-tls10", security_rank=rank))


# --- bounded model checking (AC-0007-197) -----------------------------------
def test_all_bounded_models_hold():
    res = MC.run_all_models()
    assert all(v["verdict"] == "HOLDS" for v in res.values()), \
        {k: v["verdict"] for k, v in res.items()}


@pytest.mark.parametrize("name", list(MC.MODELS))
def test_violating_variant_produces_counterexample(name):
    initial, t, inv = MC.MODELS[name](violating=True)
    res = MC.explore(initial, t, inv)
    assert res["verdict"] == "VIOLATED" and res["counterexample"]


def test_model_check_truncation_is_honest():
    initial, t, inv = MC.checkpoint_model()
    res = MC.explore(initial, t, inv, max_states=2)
    assert res["truncated"] and res["verdict"] == "INCONCLUSIVE_TRUNCATED"


# --- proof envelopes (AC-0007-191..196) -------------------------------------
def test_envelope_deterministic_and_binds_contract_and_transformer():
    e1 = ENV.compatibility_proof_envelope(descriptor={"c": "A"},
                                          producer_version={"v": "2"},
                                          consumer_binding={"b": 1},
                                          compatibility_vector={"semantic": "COMPATIBLE"})
    e2 = ENV.compatibility_proof_envelope(descriptor={"c": "A"},
                                          producer_version={"v": "2"},
                                          consumer_binding={"b": 1},
                                          compatibility_vector={"semantic": "COMPATIBLE"})
    assert e1["envelope_hash"] == e2["envelope_hash"]
    assert e1["classification"] == "EVIDENCE_NOT_AUTHORITY"
    e3 = ENV.compatibility_proof_envelope(descriptor={"c": "B"},
                                          producer_version={"v": "2"},
                                          consumer_binding={"b": 1},
                                          compatibility_vector={"semantic": "COMPATIBLE"})
    assert e1["envelope_hash"] != e3["envelope_hash"]   # contract change
    m1 = ENV.migration_proof_envelope(migration_plan={"p": 1}, transformer={"t": 1})
    m2 = ENV.migration_proof_envelope(migration_plan={"p": 1}, transformer={"t": 2})
    assert m1["envelope_hash"] != m2["envelope_hash"]   # transformer change


def test_envelope_rejects_authority_claim():
    e = ENV.migration_proof_envelope(migration_plan={"p": 1})
    assert PROOF_ENVELOPE_MISMATCH in _k(ENV.validate_envelope(
        dict(e, authorizes_cutover=True)))
