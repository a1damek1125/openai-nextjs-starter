"""TOOL-B5 capability identity seal + certificate chain closure.

The capability identity seal binds the sealed B1 head to the request envelope;
the certificate chain closure proves B1 registry -> B2 quality -> B3 contract ->
B4 receipt all hold. Closure NEVER authorizes execution. Executes nothing.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_clean_capability_identity_seal_is_sealed(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert)
    seal = o["capability_identity_seal"]
    assert seal["seal_status"] == "SEALED"
    assert seal["identity_sealed"] is True
    assert seal["signal"] is None


def test_clean_certificate_chain_is_closed_with_all_links(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert)
    closure = o["certificate_chain_closure"]
    assert closure["closure_status"] == "CHAIN_CLOSED"
    links = closure["chain_links"]
    for link in ("b1_registry", "b2_quality", "b3_contract", "b4_receipt"):
        assert links[link] is True, link
    assert closure["missing_links"] == []
    assert closure["signal"] is None


def test_seal_fails_when_head_missing(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj)
    seal = b.build_capability_identity_seal(
        tenant_id=gate.tid, broker_request_id="br1", head=None,
        contract=contract, envelope=env)
    assert seal["seal_status"] == "SEAL_FAILED"
    assert seal["identity_sealed"] is False
    assert seal["signal"] == "CAPABILITY_IDENTITY_SEAL_FAILED"


def test_seal_fails_on_mismatched_tool_id(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj)
    seal = b.build_capability_identity_seal(
        tenant_id=gate.tid, broker_request_id="br1",
        head={**head, "tool_id": "not-the-sealed-tool"},
        contract=contract, envelope=env)
    assert seal["seal_status"] == "SEAL_FAILED"
    assert seal["signal"] == "CAPABILITY_IDENTITY_SEAL_FAILED"


def test_chain_opens_when_a_link_is_missing(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    closure = b.build_certificate_chain_closure(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        quality_report=None, contract=contract, b4_decision=d)
    assert closure["closure_status"] == "CHAIN_OPEN"
    assert closure["chain_links"]["b2_quality"] is False
    assert "b2_quality" in closure["missing_links"]
    assert closure["signal"] == "CERTIFICATE_CHAIN_CLOSURE_FAILED"


def test_seal_and_chain_hashes_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj)
    s1 = b.build_capability_identity_seal(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        contract=contract, envelope=env)
    s2 = b.build_capability_identity_seal(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        contract=contract, envelope=env)
    assert s1["capability_identity_seal_hash"] == \
        s2["capability_identity_seal_hash"]
    c1 = b.build_certificate_chain_closure(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        quality_report=quality, contract=contract, b4_decision=d)
    c2 = b.build_certificate_chain_closure(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        quality_report=quality, contract=contract, b4_decision=d)
    assert c1["certificate_chain_closure_hash"] == \
        c2["certificate_chain_closure_hash"]


def test_certificate_chain_closure_never_authorizes_execution(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    # closed chain
    closed = b.build_certificate_chain_closure(
        tenant_id=gate.tid, broker_request_id="br1", head=head,
        quality_report=quality, contract=contract, b4_decision=d)
    assert closed["closure_status"] == "CHAIN_CLOSED"
    assert closed["authorizes_execution"] is False
    # open chain also refuses to authorize
    opened = b.build_certificate_chain_closure(
        tenant_id=gate.tid, broker_request_id="br1", head=None,
        quality_report=quality, contract=contract, b4_decision=d)
    assert opened["authorizes_execution"] is False
