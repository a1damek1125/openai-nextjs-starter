"""TOOL-B1 — collision / shadowing / multi-tool poisoning (SECURITY-CRITICAL).

normalize_tool_key makes 'Send_Email', 'send email' and 'send-email' collide by
design. detect_collisions flags key/alias overlap and shadowing of an
equal-or-higher-trust OFFERABLE tool. detect_multi_tool_poisoning finds
cross-tool hazards no single descriptor exposes: an escalation_chain (secret
reader + egress/messaging writer) and key_confusion (duplicate offerable keys).
Endpoint tests confirm same-name registration is BLOCKED and that collision
detection is tenant-scoped.
"""
import pytest

from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate, OWNER, OTHER_OWNER  # noqa: F401


class TestNormalizeKey:
    def test_underscore_space_hyphen_collide(self):
        assert (tr.normalize_tool_key("Send_Email")
                == tr.normalize_tool_key("send email")
                == tr.normalize_tool_key("send-email") == "send-email")

    def test_punctuation_collapsed(self):
        assert tr.normalize_tool_key("  Send!!Email  ") == "send-email"

    def test_empty_key(self):
        assert tr.normalize_tool_key("") == ""


def _cand(**o):
    kw = dict(tool_id="cand", tool_key="send-email", aliases=[],
              trust_tier="AI_PROPOSED_UNVERIFIED", risk_rank=2, status="DRAFT")
    kw.update(o)
    return kw


def _exist(**o):
    kw = dict(tool_id="ex", tool_key="send-email", aliases=[],
              trust_tier="HUMAN_REVIEWED", risk_rank=2, status="ADMITTED")
    kw.update(o)
    return kw


class TestCollisions:
    def test_key_collision_detected(self):
        r = tr.detect_collisions(candidate=_cand(), existing=[_exist()])
        assert r["has_collision"]
        assert r["collisions"][0]["colliding_keys"] == ["send-email"]

    def test_alias_collision_detected(self):
        cand = _cand(tool_key="mailer", aliases=["Send Email"])
        r = tr.detect_collisions(candidate=cand, existing=[_exist()])
        assert r["has_collision"]

    def test_shadowing_of_higher_trust_offerable(self):
        r = tr.detect_collisions(candidate=_cand(), existing=[_exist()])
        assert r["has_shadowing"]

    def test_no_shadowing_of_non_offerable(self):
        # Same key but existing is only DRAFT -> collision, no shadowing.
        r = tr.detect_collisions(candidate=_cand(),
                                 existing=[_exist(status="DRAFT")])
        assert r["has_collision"] and not r["has_shadowing"]

    def test_no_shadowing_when_candidate_higher_trust(self):
        # Candidate strictly higher trust than the offerable existing tool.
        cand = _cand(trust_tier="INTERNAL_VERIFIED")
        r = tr.detect_collisions(candidate=cand,
                                 existing=[_exist(trust_tier="HUMAN_REVIEWED")])
        assert r["has_collision"] and not r["has_shadowing"]

    def test_self_is_not_a_collision(self):
        r = tr.detect_collisions(candidate=_cand(tool_id="same"),
                                 existing=[_exist(tool_id="same")])
        assert not r["has_collision"]


class TestMultiToolPoisoning:
    def test_escalation_chain(self):
        descs = [
            {"tool_id": "r", "tool_key": "reader", "side_effect_class":
             "PURE_READ", "reads_data_classes": ["SECRET"],
             "writes_data_classes": [], "egress": [], "status": "DRAFT"},
            {"tool_id": "w", "tool_key": "writer", "side_effect_class":
             "EXTERNAL_WRITE", "reads_data_classes": [],
             "writes_data_classes": [], "egress": ["http://x"],
             "status": "DRAFT"}]
        m = tr.detect_multi_tool_poisoning(descs)
        assert m["has_findings"]
        assert any(f["code"] == "escalation_chain" for f in m["findings"])

    def test_messaging_writer_forms_chain(self):
        descs = [
            {"tool_id": "r", "tool_key": "reader", "side_effect_class":
             "PURE_READ", "reads_data_classes": ["CREDENTIALS"], "egress": [],
             "status": "ADMITTED"},
            {"tool_id": "w", "tool_key": "msg", "side_effect_class":
             "CUSTOMER_MESSAGING", "reads_data_classes": [], "egress": [],
             "status": "ADMITTED"}]
        m = tr.detect_multi_tool_poisoning(descs)
        assert any(f["code"] == "escalation_chain" for f in m["findings"])

    def test_key_confusion(self):
        descs = [
            {"tool_id": "a", "tool_key": "dup", "side_effect_class": "PURE_READ",
             "reads_data_classes": [], "egress": [], "status": "DRAFT"},
            {"tool_id": "b", "tool_key": "dup", "side_effect_class": "PURE_READ",
             "reads_data_classes": [], "egress": [], "status": "ADMITTED"}]
        m = tr.detect_multi_tool_poisoning(descs)
        assert any(f["code"] == "key_confusion" for f in m["findings"])

    def test_no_findings_for_single_safe_reader(self):
        descs = [
            {"tool_id": "r", "tool_key": "reader", "side_effect_class":
             "PURE_READ", "reads_data_classes": ["INTERNAL"], "egress": [],
             "status": "DRAFT"}]
        m = tr.detect_multi_tool_poisoning(descs)
        assert not m["has_findings"]


class TestEndpointCollisions:
    def test_duplicate_name_surfaces_collision_and_blocks(self, gate):
        gate.register_tool(tool_name="Send Report")
        r2 = gate.register_tool(tool_name="Send Report")
        j = r2.json()
        assert j["status"] == "BLOCKED"
        assert "BLOCKED" in j["hard_fail_signals"]
        lv = gate.latest_tool_version(j["tool_id"])
        assert lv["collision"]["has_collision"]
        assert lv["multi_tool"]["has_findings"]

    def test_collisions_are_tenant_scoped(self, gate):
        # Same key in another tenant must NOT collide.
        gate.register_tool(tool_name="Shared Name", requester=OWNER)
        r = gate.register_tool(tool_name="Shared Name", requester=OTHER_OWNER)
        lv = gate.latest_tool_version(r.json()["tool_id"], actor=OTHER_OWNER)
        assert not lv["collision"]["has_collision"]
        assert not lv["multi_tool"]["has_findings"]
