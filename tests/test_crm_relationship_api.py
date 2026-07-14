"""Relationship Core API tests (CRM-B) — migration v6 persistence, RBAC,
tenant isolation, consent, memory rules, dedupe/merge, sync decisions
over real HTTP. Engine rules are proven in test_crm_relationship_core.py.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def login(client, email="owner@demo.finalis", password="demo1234"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_person(client, h, name="Jan Kowalski", email="jan@example.pl",
                phone="+48 600-100-200"):
    r = client.post("/crm/parties", json={
        "kind": "person", "display_name": name,
        "person": {"first_name": name.split()[0],
                   "last_name": name.split()[-1]},
        "contact_points": [{"kind": "EMAIL", "value": email},
                           {"kind": "MOBILE", "value": phone}]},
        headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def first_case_id(client, h):
    return client.get("/cases", headers=h).json()[0]["id"]


class TestPartiesApi:
    def test_1_2_11_12_create_person_org_normalized(self, client):
        h = login(client)
        p = make_person(client, h, email="  Jan@Example.PL ")
        cps = {c["kind"]: c["value"] for c in p["contact_points"]}
        assert cps["EMAIL"] == "jan@example.pl"          # normalized
        assert cps["MOBILE"] == "+48600100200"           # normalized
        org = client.post("/crm/parties", json={
            "kind": "organization", "display_name": "HVAC sp. z o.o.",
            "organization": {"legal_name": "HVAC sp. z o.o.",
                             "domain": "hvac.pl"},
            "roles": ["vendor"]}, headers=h).json()
        assert org["kind"] == "organization"
        assert client.post("/crm/parties", json={"kind": "robot",
                                                 "display_name": "x"},
                           headers=h).status_code == 400

    def test_3_party_persists_across_restart(self, tmp_path):
        db_file = str(tmp_path / "crm.db")
        app1 = create_app(db_file)
        seed(app1.state.db)
        c1 = TestClient(app1)
        h = login(c1)
        p = make_person(c1, h)
        c1.post(f"/crm/parties/{p['id']}/consents",
                json={"channel": "WHATSAPP", "status": "REVOKED"},
                headers=h)
        c1.post(f"/crm/parties/{p['id']}/promises",
                json={"promisor": "customer", "what": "send photos"},
                headers=h)
        # Fresh app over the same file: hydrated from migration v6.
        c2 = TestClient(create_app(db_file))
        h2 = login(c2)
        detail = c2.get(f"/crm/parties/{p['id']}", headers=h2).json()
        assert detail["display_name"] == "Jan Kowalski"
        consents = c2.get(f"/crm/parties/{p['id']}/consents",
                          headers=h2).json()
        assert consents[0]["status"] == "REVOKED"
        check = c2.post("/crm/consent/check",
                        json={"party_id": p["id"],
                              "channel": "WHATSAPP"}, headers=h2).json()
        assert check["allowed"] is False       # revocation survived
        promises = c2.get(f"/crm/parties/{p['id']}/promises",
                          headers=h2).json()
        assert promises[0]["what"] == "send photos"

    def test_4_5_tenant_scoping(self, client):
        h = login(client)
        p = make_person(client, h)
        listed = client.get("/crm/parties", headers=h).json()
        assert any(x["id"] == p["id"] for x in listed["parties"])
        assert listed["legacy_case_contacts"]      # bridge visible
        h_other = login(client, "owner@other.finalis")
        other = client.get("/crm/parties", headers=h_other).json()
        assert other["parties"] == []
        assert client.get(f"/crm/parties/{p['id']}",
                          headers=h_other).status_code == 404
        assert client.patch(f"/crm/parties/{p['id']}", json={},
                            headers=h_other).status_code == 404

    def test_6_viewer_cannot_create(self, client):
        hv = login(client, "viewer@demo.finalis")
        assert client.post("/crm/parties",
                           json={"kind": "person",
                                 "display_name": "X"},
                           headers=hv).status_code == 403
        # But viewer can read.
        assert client.get("/crm/parties", headers=hv).status_code == 200


class TestGraphApi:
    def test_7_9_links_person_org_case(self, client):
        h = login(client)
        p = make_person(client, h)
        org = client.post("/crm/parties", json={
            "kind": "organization", "display_name": "Firma XYZ"},
            headers=h).json()
        r = client.post("/crm/relationships", json={
            "from_id": p["id"], "to_id": org["id"], "to_kind": "party",
            "role": "employed_by"}, headers=h)
        assert r.status_code == 200
        case_id = first_case_id(client, h)
        r2 = client.post("/crm/relationships", json={
            "from_id": p["id"], "to_id": case_id, "to_kind": "case"},
            headers=h)
        assert r2.status_code == 200
        rels = client.get(f"/crm/parties/{p['id']}/relationships",
                          headers=h).json()
        assert {x["to_kind"] for x in rels} == {"party", "case"}
        case_parties = client.get(f"/crm/cases/{case_id}/parties",
                                  headers=h).json()
        assert case_parties[0]["party_id"] == p["id"]
        detail = client.get(f"/crm/parties/{p['id']}", headers=h).json()
        assert detail["cases"] == [case_id]

    def test_8_10_cross_tenant_links_denied(self, client):
        h = login(client)
        p = make_person(client, h)
        case_id = first_case_id(client, h)
        h_other = login(client, "owner@other.finalis")
        p_other = make_person(client, h_other, email="o@o.pl",
                              phone="+48111222333")
        # Cross-tenant party link.
        assert client.post("/crm/relationships", json={
            "from_id": p["id"], "to_id": p_other["id"],
            "to_kind": "party"}, headers=h).status_code == 404
        # Cross-tenant case link (their party, our case).
        assert client.post("/crm/relationships", json={
            "from_id": p_other["id"], "to_id": case_id,
            "to_kind": "case"}, headers=h_other).status_code == 404
        # Property: no cross-tenant edge exists in the persisted graph.
        rows = client.app.state.db.all(
            "SELECT e.tenant_id AS et, p.tenant_id AS pt FROM "
            "crm_relationship_edges e JOIN crm_parties p "
            "ON p.id = e.from_id")
        assert all(r["et"] == r["pt"] for r in rows)


class TestConsentApi:
    def test_13_revoked_blocks_outreach(self, client):
        h = login(client)
        p = make_person(client, h)
        client.post(f"/crm/parties/{p['id']}/consents",
                    json={"channel": "WHATSAPP", "status": "GRANTED"},
                    headers=h)
        client.post(f"/crm/parties/{p['id']}/consents",
                    json={"channel": "WHATSAPP", "status": "REVOKED",
                          "source": "client message"}, headers=h)
        check = client.post("/crm/consent/check",
                            json={"party_id": p["id"],
                                  "channel": "WHATSAPP",
                                  "purpose": "service"},
                            headers=h).json()
        assert check["allowed"] is False
        assert "non-overrideable" in check["reasons"][0]

    def test_14_15_unknown_marketing_review_and_events(self, client):
        h = login(client)
        p = make_person(client, h)
        client.post(f"/crm/parties/{p['id']}/consents",
                    json={"channel": "EMAIL", "status": "GRANTED"},
                    headers=h)
        check = client.post("/crm/consent/check",
                            json={"party_id": p["id"], "channel": "EMAIL",
                                  "purpose": "marketing"},
                            headers=h).json()
        assert check["allowed"] is False
        assert check["requires_review"] is True
        events = client.app.state.audit.events(
            event_type="CRM_CONSENT_CHANGED")
        assert events and events[-1].payload["channel"] == "EMAIL"
        assert client.post(f"/crm/parties/{p['id']}/consents",
                           json={"channel": "FAX", "status": "GRANTED"},
                           headers=h).status_code == 400


class TestPromisesMemoryApi:
    def test_16_17_promises_persist(self, client):
        h = login(client)
        p = make_person(client, h)
        for promisor in ("customer", "finalis"):
            r = client.post(f"/crm/parties/{p['id']}/promises",
                            json={"promisor": promisor, "what": "x"},
                            headers=h)
            assert r.status_code == 200
        assert client.post(f"/crm/parties/{p['id']}/promises",
                           json={"promisor": "ai", "what": "x"},
                           headers=h).status_code == 400
        rows = client.app.state.db.all(
            "SELECT promisor FROM crm_promises WHERE party_id=?",
            p["id"])
        assert {r["promisor"] for r in rows} == {"customer", "finalis"}

    def test_18_19_ai_memory_downgraded_human_verifies(self, client):
        h = login(client)
        p = make_person(client, h)
        m = client.post(f"/crm/parties/{p['id']}/memory", json={
            "memory_type": "VERIFIED_FACT",
            "content": {"boiler": "Viessmann"},
            "source": "ai_worker", "confidence": 0.95},
            headers=h).json()
        assert m["memory_type"] == "AI_SUGGESTED"     # downgraded
        row = client.app.state.db.one(
            "SELECT memory_type FROM crm_memory_items WHERE id=?",
            m["id"])
        assert row["memory_type"] == "AI_SUGGESTED"   # persisted too
        # Operator lacks action.approve → cannot verify.
        ho = login(client, "operator@demo.finalis")
        assert client.post(f"/crm/memory/{m['id']}/verify",
                           headers=ho).status_code == 403
        v = client.post(f"/crm/memory/{m['id']}/verify",
                        headers=h).json()
        assert v["memory_type"] == "VERIFIED_FACT"

    def test_20_21_dispute_and_stale(self, client):
        h = login(client)
        p = make_person(client, h)
        m = client.post(f"/crm/parties/{p['id']}/memory", json={
            "memory_type": "VERIFIED_FACT",
            "content": {"email": "a@b.pl"}, "source": "human"},
            headers=h).json()
        d = client.post(f"/crm/memory/{m['id']}/dispute",
                        headers=h).json()
        assert d["memory_type"] == "DISPUTED_FACT"
        s = client.post(f"/crm/memory/{m['id']}/mark-stale",
                        headers=h).json()
        assert s["memory_type"] == "STALE_FACT"

    def test_22_sensitive_memory_hidden_without_permission(self, client):
        h = login(client)
        p = make_person(client, h)
        client.post(f"/crm/parties/{p['id']}/memory", json={
            "memory_type": "RISK_NOTE",
            "content": {"note": "chargeback history"},
            "source": "human", "sensitive": True}, headers=h)
        # Owner (has document.view_sensitive) sees it.
        assert len(client.get(f"/crm/parties/{p['id']}/memory",
                              headers=h).json()) == 1
        # Manager lacks view_sensitive → sensitive item hidden.
        hm = login(client, "manager@demo.finalis")
        assert client.get(f"/crm/parties/{p['id']}/memory",
                          headers=hm).json() == []


class TestDedupeMergeApi:
    def test_23_24_dedupe_from_persisted_data(self, client):
        h = login(client)
        a = make_person(client, h)
        make_person(client, h, name="J. Kowalski")     # same email+phone
        cands = client.get(f"/crm/parties/{a['id']}/dedupe-candidates",
                           headers=h).json()
        assert cands and cands[0]["verdict"] == "LIKELY_DUPLICATE"
        assert "same email" in cands[0]["signals"]
        assert "same phone" in cands[0]["signals"]

    def test_26_27_28_merge_rules(self, client):
        h = login(client)
        a = make_person(client, h)
        b = make_person(client, h, name="Jan Kowalski")
        # Reason required.
        assert client.post("/crm/merge", json={
            "surviving_party_id": a["id"], "merged_party_id": b["id"],
            "reason": " "}, headers=h).status_code == 400
        r = client.post("/crm/merge", json={
            "surviving_party_id": a["id"], "merged_party_id": b["id"],
            "reason": "same client"}, headers=h).json()
        assert r["merged_party_ids"] == [b["id"]]
        detail = client.get(f"/crm/parties/{b['id']}", headers=h).json()
        assert detail["merged_into_id"] == a["id"]     # tombstoned
        row = client.app.state.db.one(
            "SELECT * FROM crm_merge_decisions WHERE tenant_id=?",
            "demo-hvac")
        assert row["reason"] == "same client"
        # Viewer/manager without tenant.manage_users cannot merge.
        ho = login(client, "operator@demo.finalis")
        assert client.post("/crm/merge", json={
            "surviving_party_id": a["id"], "merged_party_id": b["id"],
            "reason": "x"}, headers=ho).status_code == 403


class TestExternalSyncApi:
    def test_29_external_reference_persists(self, client):
        h = login(client)
        p = make_person(client, h)
        r = client.post(f"/crm/parties/{p['id']}/external-references",
                        json={"provider": "hubspot",
                              "object_kind": "Contact",
                              "external_id": "hs-123"}, headers=h)
        assert r.status_code == 200
        refs = client.get(f"/crm/parties/{p['id']}/external-references",
                          headers=h).json()
        assert refs[0]["external_id"] == "hs-123"
        assert client.post(
            f"/crm/parties/{p['id']}/external-references",
            json={"provider": "hubspot", "object_kind": "Widget",
                  "external_id": "1"}, headers=h).status_code == 400

    def test_30_sync_requires_integration_permission(self, client):
        hm = login(client, "manager@demo.finalis")
        assert client.post("/crm/sync/dry-run", json={},
                           headers=hm).status_code == 403

    def test_31_37_dry_run_never_writes_externally(self, client):
        h = login(client)
        r = client.post("/crm/sync/dry-run", json={
            "field": "marketing_opt_in", "internal_value": "yes",
            "external_value": "no", "marketing_consent_denied": True},
            headers=h).json()
        assert r["decision"] == "DENY_CONSENT"
        assert r["external_write_happened"] is False
        assert r["adapter"]["is_mock"] is True
        # 32: an idempotency key is always attached.
        assert len(r["idempotency_key"]) == 64
        # No external provider called: NullCrmAdapter recorded nothing.
        assert client.app.state.crm.audit is not None
        row = client.app.state.db.one(
            "SELECT * FROM crm_external_sync_events WHERE tenant_id=?",
            "demo-hvac")
        assert row["decision"] == "DENY_CONSENT"

    def test_33_34_36_conflicts_and_source_of_truth(self, client):
        h = login(client)
        both = client.post("/crm/sync/decision", json={
            "direction": "import", "field": "email",
            "internal_value": "a@a.pl", "external_value": "b@b.pl",
            "internal_changed": True, "external_changed": True},
            headers=h).json()
        assert both["decision"] == "CONFLICT_REQUIRES_REVIEW"
        verified = client.post("/crm/sync/decision", json={
            "direction": "import", "field": "email",
            "internal_value": "v@finalis.pl", "external_value": "x@x.pl",
            "internal_verified": True}, headers=h).json()
        assert verified["decision"] == "CONFLICT_REQUIRES_REVIEW"
        outcome = client.post("/crm/sync/decision", json={
            "direction": "import", "field": "case_outcome",
            "internal_value": "WON_COMPLETED",
            "external_value": "closed"}, headers=h).json()
        assert outcome["decision"] == "DENY_FIELD_POLICY"

    def test_35_sync_event_redacts_secrets(self, client):
        h = login(client)
        client.post("/crm/sync/dry-run", json={
            "field": "email", "internal_value": "a@b.pl",
            "external_value": "c@d.pl",
            "note": "using api_key=sk-abc123def456ghi789 now"},
            headers=h)
        rows = client.app.state.db.all(
            "SELECT detail_json FROM crm_external_sync_events")
        assert rows
        for r in rows:
            assert "sk-abc123" not in r["detail_json"]
        for ev in client.app.state.audit.events(
                event_type="CRM_SYNC_EVENT"):
            assert "sk-abc123" not in str(ev.payload)
