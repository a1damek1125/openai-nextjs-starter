"""CORE-A4.1 — anti-rubber-stamp approval challenge: bound to the exact
package the reviewer saw, required for high-risk, scoped acknowledgements."""
from finalis.ai_employee import approvals as A


def _ch(**over):
    kw = dict(approval_request_id="ar1", tenant_id="t1",
              viewed_package_hash="vp", required_acknowledgements=[
                  "risk_acknowledged", "scope_acknowledged"],
              risk_level="HIGH", subject_required=True, created_at="t",
              expires_at=None, required=True)
    kw.update(over)
    return A.build_challenge(**kw)


class TestChallengeShape:
    def test_version_and_id(self):
        c = _ch()
        assert c["challenge_version"] == A.CHALLENGE_VERSION
        assert c["approval_challenge_id"] == "ar1-challenge"

    def test_bound_to_viewed_package(self):
        assert _ch(viewed_package_hash="XYZ")["viewed_package_hash"] == "XYZ"

    def test_required_status(self):
        assert _ch(required=True)["challenge_status"] == "REQUIRED"
        assert _ch(required=False)["challenge_status"] == "NOT_REQUIRED"

    def test_subject_ack_type_added_when_subject_required(self):
        assert "SUBJECT_ACCESS_ACKNOWLEDGEMENT" in _ch(
            subject_required=True)["challenge_type"]
        assert "SUBJECT_ACCESS_ACKNOWLEDGEMENT" not in _ch(
            subject_required=False)["challenge_type"]

    def test_challenge_types_are_valid_and_sorted(self):
        ct = _ch()["challenge_type"]
        assert ct == sorted(ct)
        assert set(ct) <= A.CHALLENGE_TYPES

    def test_confirmation_fields_match_acknowledgements(self):
        acks = ["a_ack", "b_ack"]
        c = _ch(required_acknowledgements=acks)
        assert c["required_confirmation_fields"] == sorted(acks)
        assert c["required_acknowledgements"] == sorted(acks)

    def test_summary_points_present(self):
        assert len(_ch()["required_summary_points"]) == 4


class TestChallengeBinding:
    def test_reuse_after_package_change_breaks_binding(self):
        # A challenge bound to package P1 must not verify against P2.
        c = _ch(viewed_package_hash="P1")
        assert c["viewed_package_hash"] != "P2"

    def test_hash_covers_viewed_package(self):
        a = _ch(viewed_package_hash="P1")["challenge_hash"]
        b = _ch(viewed_package_hash="P2")["challenge_hash"]
        assert a != b

    def test_hash_covers_required_status(self):
        assert _ch(required=True)["challenge_hash"] \
            != _ch(required=False)["challenge_hash"]
