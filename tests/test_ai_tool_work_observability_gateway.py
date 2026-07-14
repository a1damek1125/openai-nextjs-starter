"""TOOL-B9.2 v5: Tool Gateway Boundary Proof (section 13) + secret
non-exposure.

At the LOCAL observation stage there is no real provider execution, so a secret
injection can never occur: the gateway proof records only boundary booleans and
salted hashes of the credential scope / requested operation, never raw secret
material. A detected exposure of a secret to the model, the logs or an artifact
is a violation that quarantines the run; an insufficient credential scope or a
revoked integration fails boundary verification. The observatory stores no
secret and grants no authority.
"""
import json

from finalis.ai_employee.tool_contracts import _core_hash
from tests import _b92_kernel as k


# Raw-secret-material key names that must NEVER appear in a derived outcome.
_RAW_SECRET_KEYS = {
    "secret_value", "secret", "api_key", "apikey", "token", "access_token",
    "bearer_token", "refresh_token", "password", "passphrase", "private_key",
    "credential_value", "raw_credential", "plaintext_secret", "client_secret",
}


def _all_keys(obj, acc):
    if isinstance(obj, dict):
        for key, val in obj.items():
            acc.add(key)
            _all_keys(val, acc)
    elif isinstance(obj, list):
        for item in obj:
            _all_keys(item, acc)
    return acc


def _degrades(over, expected_signal, expected_truth=None, expected_state=None):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert expected_signal in o["all_signals"]
    if expected_truth is not None:
        assert o["work_outcome_truth_state"] == expected_truth
    if expected_state is not None:
        assert o["work_run_state"] == expected_state
    # LOCAL: even on a boundary violation nothing is injected or exfiltrated.
    gb = o["gateway_boundary"]
    assert gb["secret_injection_occurred"] is False
    assert gb["stores_secret"] is False
    assert o["produced_external_effect"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_gw_clean_boundary_valid_allow():
    gb = k.clean_outcome()["gateway_boundary"]
    assert gb["credential_boundary_valid"] is True
    assert gb["gateway_decision"] == "ALLOW"
    assert gb["signal"] is None


def test_gw_secret_injection_always_false():
    # No real provider execution locally -> injection can never occur.
    for over in ({}, {"secret_exposed_to_model": True},
                 {"secret_exposed_to_logs": True},
                 {"integration_revoked": True},
                 {"requested_operation": "w", "credential_scope": ["r"]}):
        gb = k.prepare(**over)["gateway_boundary"]
        assert gb["secret_injection_occurred"] is False
        assert gb["stores_secret"] is False


def test_gw_stores_secret_false():
    o = k.clean_outcome()
    assert o["stores_secret"] is False
    assert o["gateway_boundary"]["stores_secret"] is False


def test_gw_credential_reference_present_but_no_raw_credential():
    # A reference id may be recorded; the raw credential never is.
    gb = k.prepare(credential_reference_id="cred-ref-9",
                   integration_id="intg-1")["gateway_boundary"]
    assert gb["credential_reference_id"] == "cred-ref-9"
    assert gb["stores_secret"] is False
    keys = _all_keys(gb, set())
    assert not (keys & _RAW_SECRET_KEYS)


def test_gw_secret_exposed_to_model_quarantines():
    o = _degrades({"secret_exposed_to_model": True},
                  "SECRET_EXPOSURE_TO_MODEL_DETECTED",
                  expected_truth="TAMPERED", expected_state="QUARANTINED")
    assert o["gateway_boundary"]["secret_exposed_to_model"] is True
    assert o["gateway_boundary"]["credential_boundary_valid"] is False


def test_gw_secret_exposed_to_logs_quarantines():
    _degrades({"secret_exposed_to_logs": True},
              "SECRET_EXPOSURE_TO_LOG_DETECTED",
              expected_truth="TAMPERED", expected_state="QUARANTINED")


def test_gw_secret_exposed_to_artifact_quarantines():
    _degrades({"secret_exposed_to_artifact": True},
              "SECRET_EXPOSURE_TO_ARTIFACT_DETECTED",
              expected_truth="TAMPERED", expected_state="QUARANTINED")


def test_gw_credential_scope_insufficient():
    o = _degrades({"requested_operation": "w", "credential_scope": ["r"]},
                  "CREDENTIAL_SCOPE_INSUFFICIENT", expected_truth="PARTIAL")
    assert o["gateway_boundary"]["gateway_decision"] == "BLOCK"


def test_gw_integration_revoked_fails_boundary():
    o = _degrades({"integration_revoked": True},
                  "CREDENTIAL_REFERENCE_REVOKED", expected_truth="PARTIAL")
    assert o["gateway_boundary"]["credential_boundary_valid"] is False


def test_gw_boundary_records_hashes_not_raw_values():
    gb = k.clean_outcome()["gateway_boundary"]
    for h in ("credential_scope_hash", "requested_operation_hash",
              "allowed_operation_hash"):
        assert h in gb
        assert isinstance(gb[h], str) and len(gb[h]) == 64


def test_gw_rotation_and_revocation_epochs_present():
    gb = k.clean_outcome()["gateway_boundary"]
    assert isinstance(gb["credential_rotation_epoch"], int)
    assert isinstance(gb["credential_revocation_epoch"], int)


def test_gw_proof_hash_recompute():
    gb = k.clean_outcome()["gateway_boundary"]
    assert _core_hash(gb, "gateway_proof_hash", "signal") == \
        gb["gateway_proof_hash"]


def test_gw_exposure_actual_effect_fields_stay_false():
    o = k.prepare(secret_exposed_to_model=True)
    for f in ("produced_external_effect", "provider_called", "message_sent",
              "payment_executed", "external_crm_mutated", "delivered_externally",
              "outbox_released"):
        assert o[f] is False


def test_gw_serialized_outcome_has_no_raw_secret_fields():
    # Build a full outcome that references a credential and would surface a
    # secret if the design leaked one; assert no raw secret field names exist
    # anywhere and that every secret-related key holds only a boolean.
    o = k.prepare(credential_reference_id="cred-ref-77",
                  integration_id="intg-1", tool_id="tool-1")
    # Round-trips cleanly (derived, JSON-serializable) — no opaque secret blobs.
    dumped = json.loads(json.dumps(o))
    keys = _all_keys(dumped, set())
    assert not (keys & _RAW_SECRET_KEYS)
    for key in keys:
        if "secret" in key.lower() or "password" in key.lower():
            # Every such key is a boundary boolean, never a value carrier.
            assert isinstance(_find_first(o, key), bool)


def _find_first(obj, target):
    if isinstance(obj, dict):
        if target in obj:
            return obj[target]
        for v in obj.values():
            found = _find_first(v, target)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, target)
            if found is not None:
                return found
    return None


# --- API layer -------------------------------------------------------------
def test_gw_api_gateway_boundary_endpoint(gate):
    wrid, _ = gate.observed_work()
    gb = gate.wo(wrid, "gateway-boundary").json()["gateway_boundary"]
    assert gb["credential_boundary_valid"] is True
    assert gb["gateway_decision"] == "ALLOW"
    assert gb["secret_injection_occurred"] is False
    assert gb["stores_secret"] is False


def test_gw_api_boundary_no_raw_secret_material(gate):
    wrid, _ = gate.observed_work(credential_reference_id="cred-ref-1")
    gb = gate.wo(wrid, "gateway-boundary").json()["gateway_boundary"]
    keys = _all_keys(gb, set())
    assert not (keys & _RAW_SECRET_KEYS)
    assert "credential_scope_hash" in gb


def test_gw_api_secret_exposure_quarantines(gate):
    wrid, o = gate.observed_work(secret_exposed_to_model=True)
    assert o["work_run_state"] == "QUARANTINED"
    assert "SECRET_EXPOSURE_TO_MODEL_DETECTED" in o["all_signals"]
    gb = gate.wo(wrid, "gateway-boundary").json()["gateway_boundary"]
    assert gb["credential_boundary_valid"] is False
    assert gb["secret_injection_occurred"] is False
