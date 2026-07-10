"""TOOL-B9.2 v5: Principal Continuity Graph (section 7) — the observatory
reconstructs *who* the work ran on behalf of from bound identity/role/membership
evidence, keeping the source principal and the effective (acting) principal
represented separately. It never guesses identity from a display name or email
similarity, stores no secret, and binds the revocation epoch. When continuity is
unknown, revoked, session-invalid or cross-tenant the run does not certify.

Derived evidence only: the continuity graph grants no authority.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _pc(**over):
    return k.prepare(**over)["principal_continuity"]


def _degrades_identity(over, expected_signal, expected_state, expected_truth):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] == expected_state
    assert o["work_outcome_truth_state"] == expected_truth
    assert expected_signal in o["all_signals"]
    # No external effect, ever, even on an invalidated continuity graph.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_identity_clean_continuity_valid():
    pc = _pc()
    assert pc["identity_continuity_valid"] is True
    assert pc["continuity_status"] == "VALID"


def test_identity_clean_no_heuristics_or_secret():
    pc = _pc()
    assert pc["stores_secret"] is False
    assert pc["uses_display_name_heuristic"] is False
    assert pc["uses_email_similarity"] is False


def test_identity_clean_run_certified():
    o = k.clean_outcome()
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["principal_continuity"]["signal"] is None


def test_identity_source_and_effective_fields_present():
    pc = _pc()
    assert "source_principal_id" in pc
    assert "effective_principal_id" in pc
    assert "source_principal_type" in pc
    assert "effective_principal_type" in pc


def test_identity_source_and_effective_may_differ():
    # source (delegating human) and effective (acting actor) are separate.
    pc = _pc(source_principal_id="user:1", effective_principal_id="agent:9")
    assert pc["source_principal_id"] == "user:1"
    assert pc["effective_principal_id"] == "agent:9"
    assert pc["source_principal_id"] != pc["effective_principal_id"]
    # A well-formed (both present) mapping is still continuous.
    assert pc["identity_continuity_valid"] is True


def test_identity_types_represented_separately():
    pc = _pc()
    assert pc["source_principal_type"] == "HUMAN_USER"
    assert pc["effective_principal_type"] == "SYSTEM_ACTOR"


def test_identity_missing_principal_unknown_not_guessed():
    # No source nor effective principal -> do NOT guess identity.
    o = _degrades_identity(
        {"source_principal_id": None, "effective_principal_id": None},
        "PRINCIPAL_CONTINUITY_UNKNOWN", "OBSERVATION_COMPLETE", "PARTIAL")
    pc = o["principal_continuity"]
    assert pc["identity_continuity_valid"] is False
    assert pc["continuity_status"] != "VALID"
    assert pc["uses_display_name_heuristic"] is False
    assert pc["uses_email_similarity"] is False


def test_identity_missing_effective_only_unknown():
    o = _degrades_identity(
        {"effective_principal_id": None, "source_principal_id": None},
        "PRINCIPAL_CONTINUITY_UNKNOWN", "OBSERVATION_COMPLETE", "PARTIAL")
    assert o["principal_continuity"]["signal"] == "PRINCIPAL_CONTINUITY_UNKNOWN"


def test_identity_mapping_revoked_rejected():
    o = _degrades_identity({"principal_mapping_revoked": True},
                           "PRINCIPAL_MAPPING_REVOKED", "REJECTED", "REVOKED")
    assert o["principal_continuity"]["signal"] == "PRINCIPAL_MAPPING_REVOKED"


def test_identity_session_invalid_partial():
    _degrades_identity({"principal_session_invalid": True},
                       "PRINCIPAL_SESSION_INVALID", "OBSERVATION_COMPLETE",
                       "PARTIAL")


def test_identity_cross_tenant_rejected():
    _degrades_identity({"principal_cross_tenant": True},
                       "PRINCIPAL_CROSS_TENANT_REJECTED", "OBSERVATION_COMPLETE",
                       "PARTIAL")


def test_identity_revocation_epoch_bound():
    pc = _pc(principal_epoch=7)
    assert pc["revocation_epoch"] == 7
    # Default clean epoch is bound too.
    assert _pc()["revocation_epoch"] == 1


def test_identity_version_pinned():
    pc = _pc()
    assert pc["identity_mapping_version"] == "im-v1"
    assert pc["role_version"] == "role-v1"
    assert pc["membership_version"] == "mem-v1"


def test_identity_continuity_hash_recompute():
    pc = _pc()
    assert _core_hash(pc, "principal_continuity_hash", "signal") == \
        pc["principal_continuity_hash"]


def test_identity_hash_changes_on_degradation():
    clean = _pc()["principal_continuity_hash"]
    bad = _pc(principal_mapping_revoked=True)["principal_continuity_hash"]
    assert clean != bad


def test_identity_grants_no_authority():
    o = k.clean_outcome()
    assert o["is_authority"] is False
    assert o["authorizes_execution"] is False
    assert o["stores_secret"] is False


# --- API layer -------------------------------------------------------------
def test_identity_api_principal_continuity_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "principal-continuity")
    assert r.status_code == 200
    pc = r.json()["principal_continuity"]
    assert pc["continuity_status"] == "VALID"
    assert pc["identity_continuity_valid"] is True


def test_identity_api_source_effective_present(gate):
    wrid, _ = gate.observed_work()
    pc = gate.wo(wrid, "principal-continuity").json()["principal_continuity"]
    assert pc["source_principal_id"] is not None
    assert pc["effective_principal_id"] is not None
    assert pc["uses_email_similarity"] is False


def test_identity_api_clean_run_certified(gate):
    wrid, o = gate.observed_work()
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["principal_continuity"]["stores_secret"] is False
