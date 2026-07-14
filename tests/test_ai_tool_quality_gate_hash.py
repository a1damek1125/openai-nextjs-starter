"""TOOL-B2 hashing, determinism and tamper-evidence.

The quality report is descriptor-deterministic: re-checking an unchanged
descriptor yields an identical report hash, while any descriptor/schema change
changes it. Canonical JSON is key-order independent and rejects non-finite
floats. Verify recomputes the self-excluding sub-hashes and trips MISMATCHED on
a tampered stored report.
"""
import json

import pytest

from finalis.ai_employee import tool_quality as tq
from tests.conftest import OWNER


# -- white-box helpers (test-side only; product code is never modified) -------
def _version_row(gate, tool_id):
    return gate.db.one(
        "SELECT id, payload_json FROM ai_tool_versions WHERE tool_id=? AND "
        "version_number=?", tool_id, 1)


def _write_version(gate, row_id, payload):
    gate.db.conn.execute(
        "UPDATE ai_tool_versions SET payload_json=? WHERE id=?",
        (json.dumps(payload), row_id))
    gate.db.conn.commit()


def _latest_report_row(gate, tool_id):
    return gate.db.one(
        "SELECT id, payload_json FROM ai_tool_quality_reports WHERE tool_id=? "
        "ORDER BY seq DESC LIMIT 1", tool_id)


HASH_FIELDS = [
    "quality_report_hash", "quality_evidence_package_hash",
    "quality_assurance_case_hash", "formal_descriptor_ir_hash",
    "assurance_graph_hash", "score_vector_hash",
    "semantic_intent_fingerprint_hash",
]


class TestReportIdentityAndHashes:
    def test_report_stores_identity_fields(self, gate):
        tid, rep = gate.checked_quality_tool()
        assert rep["tool_id"] == tid
        assert rep["tenant_id"]
        assert rep["tool_version_id"]
        assert rep["quality_report_hash"]

    def test_all_component_hashes_present_and_nonempty(self, gate):
        _, rep = gate.checked_quality_tool()
        for f in HASH_FIELDS:
            assert isinstance(rep.get(f), str) and rep[f], f

    def test_report_row_persists_hashes(self, gate):
        tid, rep = gate.checked_quality_tool()
        row = _latest_report_row(gate, tid)
        stored = json.loads(row["payload_json"])
        assert stored["quality_report_hash"] == rep["quality_report_hash"]
        assert stored["tenant_id"] == rep["tenant_id"]


class TestDeterminism:
    def test_same_descriptor_same_report_hash(self, gate):
        tid, rep1 = gate.checked_quality_tool()
        rep2 = gate.quality_check(tid).json()
        assert rep2["quality_report_hash"] == rep1["quality_report_hash"]

    def test_changed_descriptor_changes_report_hash(self, gate):
        tid, rep1 = gate.checked_quality_tool()
        # Edit only the descriptor prose on the same tool/version.
        gate.tamper_tool_version(
            tid, 1, tool_description="Read-only search over local case records "
            "by keyword and reference number; returns matching case ids.")
        rep2 = gate.quality_check(tid).json()
        assert rep2["quality_report_hash"] != rep1["quality_report_hash"]

    def test_changed_output_schema_changes_report_hash(self, gate):
        tid, rep1 = gate.checked_quality_tool()
        row = _version_row(gate, tid)
        p = json.loads(row["payload_json"])
        # Only the output schema hash (a report source-hash input) changes.
        p["schema_envelope"]["output_schema_hash"] = "f" * 64
        _write_version(gate, row["id"], p)
        rep2 = gate.quality_check(tid).json()
        assert rep2["quality_report_hash"] != rep1["quality_report_hash"]


class TestCanonicalJson:
    def test_key_order_independent(self, gate):
        a = {"a": 1, "b": {"x": 1, "y": 2}, "c": [1, 2, 3]}
        b = {"c": [1, 2, 3], "b": {"y": 2, "x": 1}, "a": 1}
        assert tq.canonical_json(a) == tq.canonical_json(b)

    def test_nan_rejected(self, gate):
        with pytest.raises(ValueError):
            tq.canonical_json(float("nan"))

    def test_infinity_rejected(self, gate):
        with pytest.raises(ValueError):
            tq.canonical_json({"x": float("inf")})


class TestVerify:
    def test_verify_matched_on_fresh_report(self, gate):
        tid, _ = gate.checked_quality_tool()
        v = gate.q(tid, "/verify", method="POST").json()
        assert v["verification_status"] == "MATCHED"
        assert v["tamper_detected"] is False
        assert v["tamper_reasons"] == []

    def test_verify_mismatched_after_report_tamper(self, gate):
        tid, _ = gate.checked_quality_tool()
        row = _latest_report_row(gate, tid)
        payload = json.loads(row["payload_json"])
        # Flip the recorded status inside the stored report body only.
        payload["quality_status"] = "QUALITY_FAIL"
        gate.db.conn.execute(
            "UPDATE ai_tool_quality_reports SET payload_json=? WHERE id=?",
            (json.dumps(payload), row["id"]))
        gate.db.conn.commit()
        v = gate.q(tid, "/verify", method="POST").json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["tamper_detected"] is True
        assert v["tamper_reasons"]

    def test_verify_mismatched_after_subhash_tamper(self, gate):
        tid, _ = gate.checked_quality_tool()
        row = _latest_report_row(gate, tid)
        payload = json.loads(row["payload_json"])
        # Corrupt a nested assurance-case field without fixing its self-hash.
        payload["quality_assurance_case"]["quality_assurance_status"] = "FAILED"
        gate.db.conn.execute(
            "UPDATE ai_tool_quality_reports SET payload_json=? WHERE id=?",
            (json.dumps(payload), row["id"]))
        gate.db.conn.commit()
        v = gate.q(tid, "/verify", method="POST").json()
        assert v["verification_status"] == "MISMATCHED"
        assert any("quality_assurance_case" in r for r in v["tamper_reasons"])
