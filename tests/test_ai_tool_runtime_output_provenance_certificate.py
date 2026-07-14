"""TOOL-B6 read-path runtime microkernel: output-provenance certificate.

Core v5 guarantee: a trusted safe output must carry an output-provenance
certificate that binds the provenance-map, bisimulation, non-interference,
canary, info-usage and side-channel evidence. The certificate is LOCAL evidence
only: it is not a token and can never authorize write execution. Verified
against ACTUAL kernel behavior.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _components(o):
    return dict(provenance_map=o["read_output_provenance_map"],
                bisimulation=o["output_provenance_bisimulation"],
                non_interference=o["semantic_non_interference_matrix"],
                canary=o["canary_non_leakage_proof"],
                info_usage=o["information_usage_proof"],
                side_channel=o["side_channel_budget_seal"])


def test_clean_certificate_certified(gate):
    o = k.clean_outcome(gate)
    cert = o["output_provenance_certificate"]
    assert cert["certificate_status"] == "OUTPUT_PROVENANCE_CERTIFIED", \
        "output provenance certificate required for trusted output"


def test_clean_certificate_not_token(gate):
    o = k.clean_outcome(gate)
    assert o["output_provenance_certificate"]["is_token"] is False


def test_clean_certificate_cannot_authorize_write(gate):
    o = k.clean_outcome(gate)
    cert = o["output_provenance_certificate"]
    assert cert["authorizes_write_execution"] is False, \
        "cannot authorize write execution"


def test_clean_certificate_note_disclaims(gate):
    o = k.clean_outcome(gate)
    note = o["output_provenance_certificate"]["note"].lower()
    assert "not a production signature" in note
    assert "cannot authorize write execution" in note


def test_certificate_binds_component_hashes(gate):
    o = k.clean_outcome(gate)
    cert = o["output_provenance_certificate"]
    assert cert["read_output_provenance_map_hash"] == \
        o["read_output_provenance_map"]["read_output_provenance_map_hash"]
    assert cert["output_provenance_bisimulation_hash"] == \
        o["output_provenance_bisimulation"][
            "output_provenance_bisimulation_hash"]
    assert cert["semantic_non_interference_matrix_hash"] == \
        o["semantic_non_interference_matrix"][
            "semantic_non_interference_matrix_hash"]
    assert cert["canary_non_leakage_proof_hash"] == \
        o["canary_non_leakage_proof"]["canary_non_leakage_proof_hash"]
    assert cert["information_usage_proof_hash"] == \
        o["information_usage_proof"]["information_usage_proof_hash"]
    assert cert["side_channel_budget_seal_hash"] == \
        o["side_channel_budget_seal"]["side_channel_budget_seal_hash"]


def test_component_signal_fails_certificate(gate):
    o = k.clean_outcome(gate)
    comps = _components(o)
    # One component (the bisimulation) now carries a blocking signal.
    comps["bisimulation"] = {**comps["bisimulation"],
                             "signal": "OUTPUT_PROVENANCE_BISIMULATION_FAILED"}
    cert = rt.build_output_provenance_certificate(
        tenant_id=gate.tid, runtime_request_id="x", **comps)
    assert cert["certificate_status"] == "OUTPUT_PROVENANCE_CERTIFICATE_FAILED"
    assert cert["authorizes_write_execution"] is False


def test_certificate_hash_deterministic(gate):
    o = k.clean_outcome(gate)
    comps = _components(o)
    a = rt.build_output_provenance_certificate(
        tenant_id=gate.tid, runtime_request_id="x", **comps)
    b = rt.build_output_provenance_certificate(
        tenant_id=gate.tid, runtime_request_id="x", **comps)
    assert a["output_provenance_certificate_hash"] == \
        b["output_provenance_certificate_hash"]


def test_provenance_endpoints_work(gate):
    rid, _ = gate.prepared_runtime()

    cert = gate.rt(rid, "/output-provenance-certificate")
    assert cert.status_code == 200
    assert cert.json()["output_provenance_certificate"][
        "certificate_status"] == "OUTPUT_PROVENANCE_CERTIFIED"

    prov = gate.rt(rid, "/read-output-provenance")
    assert prov.status_code == 200
    assert prov.json()["read_output_provenance_map"][
        "provenance_status"] == "OUTPUT_PROVENANCE_MATCHED"

    bisim = gate.rt(rid, "/output-provenance-bisimulation")
    assert bisim.status_code == 200
    assert bisim.json()["output_provenance_bisimulation"][
        "bisimulation_status"] == "BISIMULATION_MATCHED"

    ni = gate.rt(rid, "/semantic-non-interference")
    assert ni.status_code == 200
    assert ni.json()["semantic_non_interference_matrix"][
        "matrix_status"] == "SEMANTIC_NON_INTERFERENCE_MATCHED"
