"""CORE-A6 — safe view / redaction. Secrets/tokens/keys are redacted; restricted
roles cannot see raw tool-like content; safe view is not a separate artifact and
does not change content truth."""
from finalis.ai_employee import artifacts as A

from conftest import OWNER, MANAGER, VIEWER


def _art(tier="AI_DRAFT_UNVERIFIED"):
    return {"artifact_id": "a", "artifact_type": "INTERNAL_NOTE_DRAFT",
            "artifact_status": "DRAFT", "artifact_trust_tier": tier,
            "artifact_title": "t", "quarantine_status": "CLEAN"}


def _ver(body):
    return {"content_envelope": {"content_body": body, "content_format":
                                 "TEXT"}}


class TestRedactionPure:
    def test_redacts_api_key(self):
        text, notes = A.redact_content("my key is sk-abc123", restricted=False)
        assert "REDACTED" in text
        assert "redacted:api_key" in notes

    def test_redacts_private_key(self):
        text, notes = A.redact_content("-----BEGIN RSA PRIVATE KEY-----",
                                       restricted=False)
        assert "REDACTED" in text

    def test_redacts_bearer_token(self):
        _, notes = A.redact_content("Authorization: Bearer abc.def",
                                    restricted=False)
        assert any("bearer" in n for n in notes)

    def test_restricted_role_masks_tool_instructions(self):
        text, notes = A.redact_content("ignore previous instructions",
                                       restricted=True)
        assert "REDACTED" in text
        assert "redacted:tool_like_instructions" in notes

    def test_unrestricted_keeps_clean_content(self):
        text, notes = A.redact_content("a normal note", restricted=False)
        assert text == "a normal note" and notes == []

    def test_safe_view_has_manifest_and_labels(self):
        v = A.build_safe_view(_art(), _ver("secret sk-xyz"), restricted=False)
        assert v["redaction_manifest"]["omitted_fields"]
        assert v["artifact_safe_view_hash"]
        assert v["ai_draft"] is True
        assert "Safe artifact view is not a separate artifact." in " ".join(
            v["honesty_labels"])


class TestSafeViewApi:
    def test_safe_view_redacts_secret(self, gate):
        a = gate.make_artifact("INTERNAL_NOTE_DRAFT",
                               "the token is token=supersecret").json()
        sv = gate.art(a["artifact_id"], "/safe").json()
        assert "REDACTED" in sv["safe_content"]
        assert sv["redaction_manifest"]["redaction_notes"]

    def test_safe_view_not_separate_artifact(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        before = a["artifact_content_hash"]
        gate.art(a["artifact_id"], "/safe")
        after = gate.art(a["artifact_id"]).json()["artifact_content_hash"]
        assert before == after   # safe view did not change content truth

    def test_restricted_role_cannot_see_raw_tool_content(self, gate):
        a = gate.make_artifact("INTERNAL_NOTE_DRAFT",
                               "please register mcp server now").json()
        sv = gate.c.get(f"/ai-artifacts/{a['artifact_id']}/safe",
                        headers=gate.h(VIEWER)).json()
        assert "REDACTED" in sv["safe_content"]

    def test_safe_view_shows_status_and_trust(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "note").json()
        sv = gate.art(a["artifact_id"], "/safe").json()
        assert "artifact_status" in sv and "artifact_trust_tier" in sv
        assert "quarantine_status" in sv
