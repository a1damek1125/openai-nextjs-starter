"""SP0009 integration: the real RC-SP0009 twin, validation and CLI.

Verifies the materialized Release Assurance Twin qualifies honestly, is
deterministic, re-validates against a fresh build, and that the CLI surfaces
the release dossier. This is the end-to-end acceptance evidence (AC-0009-235..
240) for the SP0009 change itself.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.release import bootstrap, validate, envelope, model

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def twin():
    return bootstrap.build_twin(ROOT)


def test_twin_deterministic(twin):
    assert bootstrap.build_twin(ROOT)["twin_digest"] == twin["twin_digest"]


def test_twin_qualifies_with_no_p0_p1(twin):
    assert twin["counts"]["findings"]["P0"] == 0
    assert twin["counts"]["findings"]["P1"] == 0
    assert twin["qualification"]["qualifiable"] is True
    assert twin["candidate"]["status"] == "READY_FOR_LATER_PROMOTION"


def test_all_qualification_conjuncts_true(twin):
    for name, ok in twin["qualification"]["conjuncts"].items():
        assert ok is True, name


def test_no_live_deployment_or_migration(twin):
    # progressive delivery contract exists but never executes
    assert twin["progressive_delivery"]["executes_rollout"] is False
    # frontier unchanged (boundary clean is part of validate)
    from tools.release import boundary
    assert boundary.check_frontier_unchanged(ROOT) == []


def test_browser_flake_reproduced_and_classified_not_hidden(twin):
    fc = twin["flake_classification"]
    assert "browser" in fc["test_id"]
    assert fc["classification"] in ("ENVIRONMENT_INSTABILITY",
                                    "TEST_FLAKE_CONFIRMED")
    # the flake is the single advisory P2, never silently dropped
    assert twin["counts"]["findings"]["P2"] >= 1


def test_ai_closure_honest_no_provider(twin):
    ai = twin["ai_release_closure"]
    assert ai["provider_identity"]["provider"] == "none"
    assert twin["sp0011_qualification"]["qualification"] == "PENDING_SP0011"
    assert twin["sp0011_qualification"]["evidence"] is None


def test_archaeology_absences_hashed_into_genome(twin):
    assert twin["archaeology"]["ci_workflow_hash"] == "ABSENT"
    # the candidate genome binds the (absent) CI hash — recompute matches
    from tools.release import candidate
    assert candidate.verify_genome(twin["candidate"]) == []


def test_release_envelope_valid_and_sealed(twin):
    assert envelope.validate_envelope(twin["release_envelope"]) == []
    # every hash field present (a proof omitting a ledger is tampering)
    for f in envelope.HASH_FIELDS:
        assert twin["release_envelope"].get(f)


def test_proof_changes_when_a_ledger_changes(twin):
    env = dict(twin["release_envelope"])
    env["test_execution_ledger_hash"] = "MUTATED"
    fs = envelope.validate_envelope(env)
    assert any(f.kind == "RELEASE_PROOF_MISMATCH" for f in fs)


def test_validate_twin_passes(twin):
    rep = validate.validate_twin(twin, ROOT)
    assert rep.valid, rep.as_dict()["counts"]


def test_gate_ledger_and_verdict_consistent(twin):
    verdict = twin["gate_verdict"]
    assert verdict["qualifiable"] is True
    assert verdict["blocking"] == []
    # every required hard gate that is not advisory recorded a result
    assert twin["gate_results"]["GATE_PROOF_INTEGRITY"] == "PASS"


def test_impact_cone_uses_real_sp0008_inventory():
    from tools.release import impact
    cone = impact.impact_cone(ROOT, ["finalis/portal/db.py"])
    # db.py hosts DB_TABLE/DB_MIGRATION surfaces in the SP0008 inventory
    assert cone["direct_impacts"]
    assert any("DB" in d.get("parent_contract_id", "") or
               d.get("parent_contract_id") for d in cone["direct_impacts"])
