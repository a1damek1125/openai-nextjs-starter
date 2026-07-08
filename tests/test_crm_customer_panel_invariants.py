"""CRM-D operational invariant matrices — deterministic, server-side.

The UI is convenience; the invariants are enforced in the API. These
matrices pin the operational safety guarantees of the Customer Panel at
the layer that actually holds them, so a UI regression can never quietly
relax them:

  * RBAC x action        — who may do what (deny by default, server-side)
  * consent decision     — marketing never implied, revoked non-overridable
  * memory trust         — AI cannot create verified truth; humans verify
  * merge safety         — human-only, reason-required, tombstone, no
                           cross-tenant merge
  * sync decision        — external data cannot overwrite verified Finalis
                           truth; no external provider is ever called

Browser proof that these same guarantees are visible to a real user lives
in tests/test_browser_e2e.py (the CRM-D block).
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.auth import AuthService
from finalis.portal.seed import DEMO_TENANT, seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    # The seed ships owner/manager/operator/viewer; add an ai_worker in the
    # same tenant so the AI-safety rows of the matrices are real, not
    # hypothetical.
    AuthService(a.state.db).create_user(
        tenant_id=DEMO_TENANT, email="ai@demo.finalis",
        password="demo1234", role="ai_worker", display_name="AI Worker")
    return a


@pytest.fixture()
def client(app):
    return TestClient(app)


def _tok(client, email, password="demo1234"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


ROLES = {
    "owner": "owner@demo.finalis",
    "manager": "manager@demo.finalis",
    "operator": "operator@demo.finalis",
    "viewer": "viewer@demo.finalis",
    "ai_worker": "ai@demo.finalis",
}


@pytest.fixture()
def heads(client):
    return {role: _tok(client, email) for role, email in ROLES.items()}


def _new_party(client, h, name="Matrix Co", **extra):
    r = client.post("/crm/parties", json={
        "kind": "person", "display_name": name, **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _new_ai_memory(client, h, party_id):
    """An AI-suggested memory item (downgraded from VERIFIED on the way in)."""
    r = client.post(f"/crm/parties/{party_id}/memory", json={
        "memory_type": "VERIFIED_FACT", "source": "ai_worker",
        "content": {"boiler": "V200"}, "confidence": 0.9}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["memory_type"] == "AI_SUGGESTED"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Matrix 1 — RBAC x action. Deny by default; every mutation is gated on a
# server-side permission, never on UI visibility.
# ---------------------------------------------------------------------------
class TestRbacActionMatrix:
    # action -> (allowed roles). Everything else must be 403.
    EXPECTED = {
        "read": {"owner", "manager", "operator", "viewer", "ai_worker"},
        "consent_check": {"owner", "manager", "operator", "viewer",
                          "ai_worker"},
        "create": {"owner", "manager", "operator", "ai_worker"},
        "add_memory": {"owner", "manager", "operator", "ai_worker"},
        "verify_memory": {"owner", "manager"},
        "merge": {"owner"},
        "external_ref": {"owner"},
        "sync_decision": {"owner"},
    }

    def _do(self, client, owner_h, h, action):
        """Perform `action` with headers `h`; return the status code.
        Real, pre-created resources are used so an allowed role gets a
        genuine 200 and a denied role is refused *before* any 404/400."""
        if action == "read":
            return client.get("/crm/parties", headers=h).status_code
        pid = _new_party(client, owner_h, "RBAC Target")
        if action == "consent_check":
            return client.post("/crm/consent/check", json={
                "party_id": pid, "channel": "EMAIL",
                "purpose": "service"}, headers=h).status_code
        if action == "create":
            return client.post("/crm/parties", json={
                "kind": "person", "display_name": "Made"},
                headers=h).status_code
        if action == "add_memory":
            return client.post(f"/crm/parties/{pid}/memory", json={
                "memory_type": "VERIFIED_FACT", "source": "human",
                "content": {"k": "v"}, "confidence": 0.9},
                headers=h).status_code
        if action == "verify_memory":
            mid = _new_ai_memory(client, owner_h, pid)
            return client.post(f"/crm/memory/{mid}/verify",
                               headers=h).status_code
        if action == "merge":
            other = _new_party(client, owner_h, "Dup",
                               contact_points=[{"kind": "EMAIL",
                                                "value": "dup@x.pl"}])
            return client.post("/crm/merge", json={
                "surviving_party_id": pid, "merged_party_id": other,
                "reason": "same client"}, headers=h).status_code
        if action == "external_ref":
            return client.post(
                f"/crm/parties/{pid}/external-references", json={
                    "provider": "hubspot", "object_kind": "Contact",
                    "external_id": "hs-1"}, headers=h).status_code
        if action == "sync_decision":
            return client.post("/crm/sync/decision", json={
                "direction": "import", "field": "email",
                "internal_value": "a@x.pl", "external_value": "b@x.pl"},
                headers=h).status_code
        raise AssertionError(action)

    def test_matrix(self, client, heads):
        owner_h = heads["owner"]
        for action, allowed in self.EXPECTED.items():
            for role, h in heads.items():
                code = self._do(client, owner_h, h, action)
                if role in allowed:
                    assert code != 403, \
                        f"{role} should be allowed {action}, got {code}"
                    assert code == 200, \
                        f"{role} {action} expected 200, got {code}"
                else:
                    assert code == 403, \
                        f"{role} must be denied {action}, got {code}"

    def test_ai_worker_holds_no_human_judgment_over_crm(self, client, heads):
        # The structural AI-safety invariant, restated at the CRM surface:
        # an AI worker can suggest (create/add memory) but can never verify
        # memory, approve a merge, or touch external sync.
        owner_h, ai = heads["owner"], heads["ai_worker"]
        pid = _new_party(client, owner_h, "AI Bounds")
        mid = _new_ai_memory(client, owner_h, pid)
        assert client.post(f"/crm/memory/{mid}/verify",
                           headers=ai).status_code == 403
        assert client.post("/crm/merge", json={
            "surviving_party_id": pid, "merged_party_id": pid,
            "reason": "x"}, headers=ai).status_code == 403
        assert client.post("/crm/sync/decision", json={
            "direction": "import", "field": "email",
            "internal_value": "a", "external_value": "b"},
            headers=ai).status_code == 403


# ---------------------------------------------------------------------------
# Matrix 2 — consent decision. Marketing is never implied; revoked/denied
# consent is non-overridable; transactional service messaging follows
# tenant policy.
# ---------------------------------------------------------------------------
class TestConsentDecisionMatrix:
    def _record(self, client, h, pid, channel, status):
        r = client.post(f"/crm/parties/{pid}/consents", json={
            "channel": channel, "status": status, "source": "portal"},
            headers=h)
        assert r.status_code == 200, r.text

    def _check(self, client, h, pid, channel, purpose):
        r = client.post("/crm/consent/check", json={
            "party_id": pid, "channel": channel, "purpose": purpose},
            headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    def test_matrix(self, client, heads):
        h = heads["owner"]

        # Unknown consent, service purpose -> allowed (transactional policy).
        p1 = _new_party(client, h, "Unknown Consent")
        d = self._check(client, h, p1, "EMAIL", "service")
        assert d["allowed"] is True and d["requires_review"] is False

        # Unknown consent, marketing purpose -> HUMAN_REVIEW (never implied).
        d = self._check(client, h, p1, "EMAIL", "marketing")
        assert d["allowed"] is False and d["requires_review"] is True

        # Revoked channel -> BLOCKED for service AND marketing; a later
        # GRANTED marketing record cannot override the revoked channel.
        p2 = _new_party(client, h, "Revoked Channel")
        self._record(client, h, p2, "EMAIL", "REVOKED")
        self._record(client, h, p2, "MARKETING", "GRANTED")
        for purpose in ("service", "marketing"):
            d = self._check(client, h, p2, "EMAIL", purpose)
            assert d["allowed"] is False and d["requires_review"] is False, \
                purpose

        # Denied marketing consent -> BLOCKED even on a granted channel.
        p3 = _new_party(client, h, "Denied Marketing")
        self._record(client, h, p3, "EMAIL", "GRANTED")
        self._record(client, h, p3, "MARKETING", "DENIED")
        d = self._check(client, h, p3, "EMAIL", "marketing")
        assert d["allowed"] is False and d["requires_review"] is False
        # ...but transactional service on the granted channel is fine.
        d = self._check(client, h, p3, "EMAIL", "service")
        assert d["allowed"] is True

        # Explicit marketing consent -> allowed marketing outreach.
        p4 = _new_party(client, h, "Opted In")
        self._record(client, h, p4, "EMAIL", "GRANTED")
        self._record(client, h, p4, "MARKETING", "GRANTED")
        d = self._check(client, h, p4, "EMAIL", "marketing")
        assert d["allowed"] is True


# ---------------------------------------------------------------------------
# Matrix 3 — memory trust. AI cannot create verified truth; only a human
# verifies; a dispute downgrades and (in the UI) blocks automation.
# ---------------------------------------------------------------------------
class TestMemoryTrustMatrix:
    def _add(self, client, h, pid, source, mtype="VERIFIED_FACT"):
        r = client.post(f"/crm/parties/{pid}/memory", json={
            "memory_type": mtype, "source": source,
            "content": {"fact": source}, "confidence": 0.9}, headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    def test_matrix(self, client, heads):
        h = heads["owner"]
        pid = _new_party(client, h, "Memory Trust")

        # human + VERIFIED_FACT -> stays VERIFIED_FACT.
        assert self._add(client, h, pid, "human")["memory_type"] \
            == "VERIFIED_FACT"

        # ai_worker + VERIFIED_FACT -> silently downgraded to AI_SUGGESTED.
        ai = self._add(client, h, pid, "ai_worker")
        assert ai["memory_type"] == "AI_SUGGESTED"

        # human verification promotes AI_SUGGESTED -> VERIFIED_FACT.
        v = client.post(f"/crm/memory/{ai['id']}/verify", headers=h)
        assert v.status_code == 200
        assert v.json()["memory_type"] == "VERIFIED_FACT"

        # dispute downgrades to DISPUTED_FACT.
        d = client.post(f"/crm/memory/{ai['id']}/dispute", headers=h)
        assert d.status_code == 200
        assert d.json()["memory_type"] == "DISPUTED_FACT"

        # mark-stale downgrades to STALE_FACT.
        s = client.post(f"/crm/memory/{ai['id']}/mark-stale", headers=h)
        assert s.status_code == 200
        assert s.json()["memory_type"] == "STALE_FACT"


# ---------------------------------------------------------------------------
# Matrix 4 — merge safety. Human-only, reason-required, tombstone (history
# preserved), never cross-tenant.
# ---------------------------------------------------------------------------
class TestMergeSafetyMatrix:
    def test_reason_required(self, client, heads):
        h = heads["owner"]
        a = _new_party(client, h, "Keep")
        b = _new_party(client, h, "Drop")
        r = client.post("/crm/merge", json={
            "surviving_party_id": a, "merged_party_id": b}, headers=h)
        assert r.status_code == 400            # no written reason

    def test_merge_tombstones_not_deletes(self, client, heads):
        h = heads["owner"]
        a = _new_party(client, h, "Survivor",
                       contact_points=[{"kind": "EMAIL",
                                        "value": "same@x.pl"}])
        b = _new_party(client, h, "Duplicate",
                       contact_points=[{"kind": "EMAIL",
                                        "value": "same@x.pl"}])
        r = client.post("/crm/merge", json={
            "surviving_party_id": a, "merged_party_id": b,
            "reason": "same client, typo"}, headers=h)
        assert r.status_code == 200, r.text
        # The merged party is tombstoned (merged_into_id set), still
        # retrievable — history is preserved, nothing is destroyed.
        detail = client.get(f"/crm/parties/{b}", headers=h)
        assert detail.status_code == 200
        assert detail.json().get("merged_into_id") == a
        # It disappears from the active list but the survivor remains.
        listing = client.get("/crm/parties", headers=h).json()
        active = {p["id"] for p in listing["parties"]
                  if not p.get("merged_into_id")}
        assert a in active and b not in active

    def test_ai_and_non_managers_cannot_merge(self, client, heads):
        owner_h = heads["owner"]
        a = _new_party(client, owner_h, "A")
        b = _new_party(client, owner_h, "B")
        for role in ("ai_worker", "operator", "manager", "viewer"):
            r = client.post("/crm/merge", json={
                "surviving_party_id": a, "merged_party_id": b,
                "reason": "x"}, headers=heads[role])
            assert r.status_code == 403, role

    def test_cross_tenant_merge_is_impossible(self, client, app, heads):
        # A party in another tenant is not even visible to this tenant, so
        # a merge that references it is refused (never silently succeeds).
        other = TestClient(app)
        oh = _tok(other, "owner@other.finalis")
        foreign = other.post("/crm/parties", json={
            "kind": "person", "display_name": "Foreign"},
            headers=oh).json()["id"]
        mine = _new_party(client, heads["owner"], "Mine")
        r = client.post("/crm/merge", json={
            "surviving_party_id": mine, "merged_party_id": foreign,
            "reason": "attempt"}, headers=heads["owner"])
        assert r.status_code == 404           # foreign id invisible/refused


# ---------------------------------------------------------------------------
# Matrix 5 — sync decision. External data never overwrites verified Finalis
# truth; no external provider is ever called; dry-run writes nothing.
# ---------------------------------------------------------------------------
class TestSyncDecisionMatrix:
    def _decide(self, client, h, **body):
        r = client.post("/crm/sync/decision", json={
            "direction": "import", "field": "email", **body}, headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    def test_matrix(self, client, heads):
        h = heads["owner"]

        # Verified internal + differing external -> conflict, never override.
        d = self._decide(client, h, internal_value="verified@finalis.pl",
                         external_value="other@ext.com",
                         internal_verified=True)
        assert d["decision"] == "CONFLICT_REQUIRES_REVIEW"
        assert d["conflict"] is not None
        assert d["conflict"]["resolution"] == "review"

        # Identical values -> nothing to do.
        d = self._decide(client, h, internal_value="a@x.pl",
                         external_value="a@x.pl")
        assert d["decision"] == "SKIP_NO_CHANGE"

        # Both sides changed since last sync -> human review.
        d = self._decide(client, h, internal_value="a@x.pl",
                         external_value="b@x.pl", internal_changed=True,
                         external_changed=True)
        assert d["decision"] == "CONFLICT_REQUIRES_REVIEW"

        # Unmapped field -> policy denies it (no unscoped field bleed).
        d = self._decide(client, h, field="ssn", internal_value="x",
                         external_value="y")
        assert d["decision"] == "DENY_FIELD_POLICY"

        # Marketing field -> consent/policy blocks the sync.
        d = self._decide(client, h, field="newsletter", internal_value="x",
                         external_value="y")
        assert d["decision"] == "DENY_CONSENT"

    def test_dry_run_calls_no_external_provider(self, client, heads):
        h = heads["owner"]
        r = client.post("/crm/sync/dry-run", json={
            "direction": "export", "field": "email",
            "internal_value": "a@x.pl", "external_value": "b@x.pl"},
            headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        # The single most load-bearing fact: nothing left the building.
        assert data["external_write_happened"] is False
        assert data["adapter"].get("dry_run") is True
        assert data["adapter"].get("provider", "null-crm") in (
            "null-crm", None)
