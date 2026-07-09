"""TOOL-B5: credential-free corridor (b.build_credential_free_corridor).

There must be NO usable credential path from the broker request to any effect
plane. Certificates/receipts/passports are evidence, never credentials. A
credential-bearing adapter manifest breaks the corridor -> QUARANTINED.
Every asserted status confirmed by running the kernel.
"""
from tests import _b5_kernel as k


def test_clean_corridor_is_credential_free(gate):
    o = k.clean_outcome(gate)
    corridor = o["credential_free_corridor"]
    assert corridor["corridor_status"] == "CREDENTIAL_FREE"
    assert corridor["signal"] is None
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"


def test_passport_safety_flags_do_not_trip_corridor(gate):
    # The clean B4 passport/receipt carry is_token/is_bearer=False safety flags;
    # those flag KEYS must not be mistaken for a credential -> no findings.
    o = k.clean_outcome(gate)
    assert o["credential_free_corridor"]["credential_findings"] == []


def test_certificates_and_receipts_are_not_credentials(gate):
    # Clean corridor has zero findings even though the decision embeds a
    # governance receipt and the outcome embeds proof-carrying certificates.
    o = k.clean_outcome(gate)
    assert o["credential_free_corridor"]["credential_findings"] == []
    assert o["proof_carrying_broker_action_certificate"]["is_credential"] is False


def test_adapter_manifest_with_credential_key_breaks_corridor(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"credential": "x"})
    corridor = o["credential_free_corridor"]
    assert corridor["corridor_status"] == "CORRIDOR_BROKEN"
    assert corridor["signal"] == "CREDENTIAL_CORRIDOR_BROKEN"
    assert "CREDENTIAL_CORRIDOR_BROKEN" in o["all_signals"]
    assert o["broker_status"] == "QUARANTINED"


def test_adapter_manifest_with_secret_marker_value_breaks_corridor(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"adapter_kind": "carries a bearer token"})
    corridor = o["credential_free_corridor"]
    assert corridor["corridor_status"] == "CORRIDOR_BROKEN"
    assert corridor["signal"] == "CREDENTIAL_CORRIDOR_BROKEN"
    assert o["broker_status"] == "QUARANTINED"


def test_accesstoken_value_in_adapter_manifest_breaks_corridor(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  adapter_manifest={"adapter_kind": "holds an access_token"})
    assert o["credential_free_corridor"]["corridor_status"] == "CORRIDOR_BROKEN"


def test_corridor_hash_is_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert)
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert)
    assert (o1["credential_free_corridor"]["credential_free_corridor_hash"] ==
            o2["credential_free_corridor"]["credential_free_corridor_hash"])
