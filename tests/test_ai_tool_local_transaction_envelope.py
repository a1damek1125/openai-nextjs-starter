"""TOOL-B9 v5: semantic transaction envelope + source-surface isolation. The
canonical envelope is a reproducible function of the evidence (not of actor
identity), and every source surface is isolated: it may ORIGINATE a local
request but NEVER grants authority, approval, or provider access. Any surface
outside the allowed set is TRANSACTION_ENVELOPE_INVALID; a surface that claims
authority/approval is SOURCE_SURFACE_GRANTED_AUTHORITY. No external effect.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k


def _envelope(o):
    return o["transaction_envelope"]


def _isolation(o):
    return o["source_surface_isolation"]


# --- kernel layer ----------------------------------------------------------
def test_envelope_clean_valid_and_grants_no_authority():
    env = _envelope(k.clean_outcome())
    assert env["transaction_status"] == "ENVELOPE_BUILT"
    assert env["source_surface"] == "WEB_PORTAL"
    assert env["signal"] is None
    assert env["reason_code"] is None
    assert env["is_external"] is False
    assert env["grants_authority"] is False


def test_envelope_canonical_hash_recomputes():
    env = _envelope(k.clean_outcome())
    assert _core_hash(
        env, "canonical_hash", "signal", "reason_code", "transaction_status",
        "transaction_id", "actor_id", "role_id") == env["canonical_hash"]


def test_envelope_allowed_surface_web_portal_accepted():
    o = k.clean_outcome(source_surface="WEB_PORTAL")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert _envelope(o)["transaction_status"] == "ENVELOPE_BUILT"


def test_envelope_allowed_surface_internal_test_accepted():
    o = k.clean_outcome(source_surface="INTERNAL_TEST")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    env = _envelope(o)
    assert env["source_surface"] == "INTERNAL_TEST"
    assert env["transaction_status"] == "ENVELOPE_BUILT"


def test_envelope_allowed_future_surfaces_accepted_metadata_only():
    for surface in ("GOVERNED_WORKBENCH_FUTURE", "MOBILE_IOS_FUTURE",
                    "MOBILE_ANDROID_FUTURE", "MOBILE_WEB_FUTURE",
                    "SLACK_FUTURE", "TEAMS_FUTURE"):
        o = k.clean_outcome(source_surface=surface)
        assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED", surface
        assert _envelope(o)["transaction_status"] == "ENVELOPE_BUILT", surface
        iso = _isolation(o)
        assert iso["is_future_surface"] is True, surface
        assert iso["metadata_only"] is True, surface
        assert iso["grants_authority"] is False, surface
        assert iso["can_originate_local_request"] is False, surface


def test_envelope_lowercase_surface_normalized_and_accepted():
    o = k.clean_outcome(source_surface="web_portal")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert _envelope(o)["source_surface"] == "WEB_PORTAL"


def test_envelope_disallowed_surface_email_inbound_blocked():
    o = k.prepare(source_surface="EMAIL_INBOUND")
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "TRANSACTION_ENVELOPE_INVALID"
    assert o["local_commit_applied"] is False
    assert _envelope(o)["transaction_status"] == "INVALID"


def test_envelope_disallowed_surface_slack_message_blocked():
    o = k.prepare(source_surface="SLACK_MESSAGE")
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "TRANSACTION_ENVELOPE_INVALID"
    assert o["local_commit_applied"] is False


def test_envelope_surface_claims_authority_blocked():
    o = k.prepare(surface_claims_authority=True)
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "SOURCE_SURFACE_GRANTED_AUTHORITY"
    assert o["local_commit_applied"] is False


def test_envelope_surface_claims_approval_blocked():
    o = k.prepare(surface_claims_approval=True)
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "SOURCE_SURFACE_GRANTED_AUTHORITY"
    assert o["local_commit_applied"] is False


def test_source_surface_isolation_clean_grants_no_authority():
    iso = _isolation(k.clean_outcome())
    assert iso["isolation_status"] == "ISOLATED"
    assert iso["signal"] is None
    assert iso["grants_authority"] is False
    assert iso["grants_approval"] is False
    assert iso["grants_provider_access"] is False
    assert iso["bypasses_rbac"] is False
    assert iso["bypasses_tenant_policy"] is False
    assert iso["creates_external_effect"] is False
    assert iso["can_originate_local_request"] is True


def test_source_surface_isolation_hash_recomputes():
    iso = _isolation(k.clean_outcome())
    assert _core_hash(iso, "source_surface_isolation_hash", "signal") == iso[
        "source_surface_isolation_hash"]


def test_source_surface_isolation_leak_on_claimed_authority():
    iso = _isolation(k.prepare(surface_claims_authority=True))
    assert iso["isolation_status"] == "LEAK"
    assert iso["signal"] == "SOURCE_SURFACE_GRANTED_AUTHORITY"
    assert iso["grants_authority"] is False


def test_envelope_surface_change_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    other = k.prepare(source_surface="INTERNAL_TEST")["b9_decision_hash"]
    assert clean != other


# --- API layer -------------------------------------------------------------
def test_api_envelope_endpoint_returns_field(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/envelope")
    assert r.status_code == 200
    body = r.json()
    env = body["transaction_envelope"]
    assert env["transaction_status"] == "ENVELOPE_BUILT"
    assert env["grants_authority"] is False
    assert body["honesty_labels"]


def test_api_source_surface_isolation_endpoint_returns_field(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/source-surface-isolation")
    assert r.status_code == 200
    body = r.json()
    iso = body["source_surface_isolation"]
    assert iso["isolation_status"] == "ISOLATED"
    assert iso["grants_authority"] is False
    assert body["honesty_labels"]


def test_api_envelope_disallowed_surface_blocked(gate):
    b8id, _ = gate.b8_accepted_outcome()
    o = gate.local_tx(b8id, op="commit-local",
                      source_surface="EMAIL_INBOUND").json()
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "TRANSACTION_ENVELOPE_INVALID"
    assert o["local_commit_applied"] is False


def test_api_surface_claims_authority_blocked(gate):
    b8id, _ = gate.b8_accepted_outcome()
    o = gate.local_tx(b8id, op="commit-local",
                      surface_claims_authority=True).json()
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "SOURCE_SURFACE_GRANTED_AUTHORITY"
    assert o["local_commit_applied"] is False
