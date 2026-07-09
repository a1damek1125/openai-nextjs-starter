"""TOOL-B5 evidence drift detection.

The broker request envelope SEALS reference hashes at open-time. If the evidence
later presented to prepare drifts from that seal (payload mutated, B4 receipt/
decision replay mismatch, causal graph mutated) the broker fails closed. The
unmutated evidence matches the seal and prepares cleanly. Executes nothing.
"""
import copy

from tests import _b5_kernel as k


def _sealed_env(gate, d, pobj):
    """Seal an envelope over CLEAN (deep-copied) evidence."""
    clean_d = copy.deepcopy(d)
    clean_p = copy.deepcopy(pobj)
    return k.make_env(gate, clean_d, clean_p)


def test_payload_mutation_detected(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    mp = copy.deepcopy(pobj)
    mp["payload"] = {"mutated": "after-seal"}
    o = k.prepare(gate, copy.deepcopy(d), mp, head, quality, contract, cert,
                  env=env)
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "PAYLOAD_MUTATED"


def test_b4_receipt_hash_mismatch_detected(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    md = copy.deepcopy(d)
    md["governance_receipt"]["governance_receipt_hash"] = "drifted-receipt-hash"
    o = k.prepare(gate, md, copy.deepcopy(pobj), head, quality, contract, cert,
                  env=env)
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "B4_RECEIPT_MISMATCH"


def test_b4_decision_replay_mismatch_detected(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    md = copy.deepcopy(d)
    md["decision_hash"] = "drifted-decision-hash"
    o = k.prepare(gate, md, copy.deepcopy(pobj), head, quality, contract, cert,
                  env=env)
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "B4_REPLAY_MISMATCH"


def test_causal_action_graph_mutation_detected(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    md = copy.deepcopy(d)
    md["causal_action_graph"]["causal_action_graph_hash"] = "drifted-graph-hash"
    o = k.prepare(gate, md, copy.deepcopy(pobj), head, quality, contract, cert,
                  env=env)
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "CAUSAL_GRAPH_MUTATED"


def test_drift_signal_present_in_all_signals(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    mp = copy.deepcopy(pobj)
    mp["payload"] = {"mutated": "x"}
    o = k.prepare(gate, copy.deepcopy(d), mp, head, quality, contract, cert,
                  env=env)
    assert "PAYLOAD_MUTATED" in o["all_signals"]
    assert o["broker_status"] == "BLOCKED"


def test_unmutated_evidence_matches_seal(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = _sealed_env(gate, d, pobj)
    # Same (deep-copied) clean evidence -> no drift, prepares cleanly.
    o = k.prepare(gate, copy.deepcopy(d), copy.deepcopy(pobj), head, quality,
                  contract, cert, env=env)
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    assert o["dominant_signal"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
