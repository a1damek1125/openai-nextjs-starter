"""TOOL-B1 — descriptor / version hashing and tamper-evidence.

Hashes are stable and deterministic; the verify endpoint recomputes every
governance hash and the version chain, flagging any divergence as TAMPERED.
"""
import json

from conftest import OWNER
from finalis.ai_employee import tool_registry as tr


def _verify(gate, tool_id):
    return gate.tool(tool_id, "/verify", actor=OWNER, method="POST").json()


class TestHashStability:
    def test_descriptor_hash_stable_across_reads(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        h1 = gate.tool(tid, actor=OWNER).json()["descriptor_hash"]
        h2 = gate.tool(tid, actor=OWNER).json()["descriptor_hash"]
        assert h1 == h2

    def test_head_descriptor_hash_matches_latest_version(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        head = gate.tool(tid, actor=OWNER).json()
        lv = gate.latest_tool_version(tid)
        assert head["descriptor_hash"] == lv["descriptor_hash"]

    def test_descriptor_hash_recomputes_from_descriptor(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        lv = gate.latest_tool_version(tid)
        assert tr.descriptor_hash(lv["descriptor"]) == lv["descriptor_hash"]

    def test_scanner_and_capsule_hashes_recompute(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        lv = gate.latest_tool_version(tid)
        assert tr._core_hash(lv["scanner"], "scanner_hash") == \
            lv["scanner"]["scanner_hash"]
        assert tr._core_hash(lv["risk_capsule"], "risk_capsule_hash") == \
            lv["risk_capsule"]["risk_capsule_hash"]
        assert tr._core_hash(lv["tbom"], "tbom_hash") == \
            lv["tbom"]["tbom_hash"]

    def test_two_tools_same_body_differ_by_id(self, gate):
        a = gate.latest_tool_version(gate.register_tool().json()["tool_id"])
        b = gate.latest_tool_version(gate.register_tool().json()["tool_id"])
        # Same declared body, but tool_id is part of the descriptor.
        assert a["descriptor_hash"] != b["descriptor_hash"]


class TestVerifyMatched:
    def test_untampered_tool_matches(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        r = _verify(gate, tid)
        assert r["verification_status"] == "MATCHED"
        assert r["tamper_detected"] is False
        assert r["dominant_status_if_tampered"] is None
        assert r["version_chain_status"] == "VALID"
        assert r["versions_checked"] == 1

    def test_verify_after_new_version_still_matches(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tool(tid, "/versions", actor=OWNER, method="POST",
                  **gate.clean_tool_body(tool_description="v2 read only"))
        r = _verify(gate, tid)
        assert r["verification_status"] == "MATCHED"
        assert r["version_chain_status"] == "VALID"
        assert r["versions_checked"] == 2


class TestVerifyTamper:
    def test_version_description_tamper_detected(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tamper_tool_version(tid, 1, tool_description="EVIL rewritten")
        r = _verify(gate, tid)
        assert r["tamper_detected"] is True
        assert r["verification_status"] == "MISMATCHED"
        assert r["dominant_status_if_tampered"] == "TAMPERED"
        assert r["tamper_reasons"]

    def test_version_descriptor_hash_field_tamper_detected(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tamper_tool_version(tid, 1, descriptor_hash="0" * 64)
        r = _verify(gate, tid)
        assert r["tamper_detected"] is True
        assert r["dominant_status_if_tampered"] == "TAMPERED"

    def test_version_chain_hash_tamper_detected(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        gate.tamper_tool_version(tid, 1, version_chain_hash="badchain")
        r = _verify(gate, tid)
        assert r["tamper_detected"] is True
        assert r["version_chain_status"] == "MISMATCHED"

    def test_head_hash_divergence_detected(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        # Force the persisted head payload to disagree with its latest version.
        row = gate.db.one("SELECT payload_json FROM ai_tools WHERE id=?", tid)
        p = json.loads(row["payload_json"])
        p["descriptor_hash"] = "0" * 64
        gate.tamper_tool_head(tid, payload_json=json.dumps(p))
        r = _verify(gate, tid)
        assert r["tamper_detected"] is True
        assert any("head descriptor hash diverges" in reason
                   for reason in r["tamper_reasons"])

    def test_head_version_hash_divergence_detected(self, gate):
        tid = gate.register_tool().json()["tool_id"]
        row = gate.db.one("SELECT payload_json FROM ai_tools WHERE id=?", tid)
        p = json.loads(row["payload_json"])
        p["version_hash"] = "f" * 64
        gate.tamper_tool_head(tid, payload_json=json.dumps(p))
        r = _verify(gate, tid)
        assert r["tamper_detected"] is True
        assert any("head version hash diverges" in reason
                   for reason in r["tamper_reasons"])
