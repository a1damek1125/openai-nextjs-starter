"""Relationship Core tests (CRM-A) — graph, consent, memory, promises,
dedupe/merge, external CRM contracts, and sync decisions.
"""
import random
from datetime import datetime, timedelta

import pytest

from finalis.audit import AuditLog
from finalis.crm.adapters import (CrmObjectMapping, NullCrmAdapter,
                                  default_policy, idempotency_key)
from finalis.crm.dedupe import duplicate_candidate, merge_parties
from finalis.crm.engine import ConsentPolicy, RelationshipEngine
from finalis.crm.graph import CrossTenantLinkError
from finalis.crm.memory import CustomerMemory
from finalis.crm.models import (ConsentRecord, ContactPoint, CustomerFact,
                                CustomerMemoryItem, CustomerPromise,
                                ExternalCrmReference, ExternalFieldMapping,
                                OrganizationProfile, Party, PersonProfile)
from finalis.crm.sync import SyncRequest, record_sync_event, sync_decision


def engine():
    return RelationshipEngine(AuditLog())


def person(tenant="t1", name="Jan Kowalski", email="jan@example.pl",
           phone="+48600100200", **kw):
    p = Party(tenant_id=tenant, kind="person", display_name=name,
              person=PersonProfile(first_name=name.split()[0],
                                   last_name=name.split()[-1]), **kw)
    if email:
        p.contact_points.append(ContactPoint(kind="EMAIL", value=email))
    if phone:
        p.contact_points.append(ContactPoint(kind="MOBILE", value=phone))
    return p


class TestPartiesAndGraph:
    def test_1_2_person_and_organization_created(self):
        eng = engine()
        p = eng.graph.add_party(person())
        org = eng.graph.add_party(Party(
            tenant_id="t1", kind="organization", display_name="HVAC sp.",
            organization=OrganizationProfile(legal_name="HVAC sp. z o.o.",
                                             domain="hvac.pl"),
            roles={"vendor"}))
        assert p.kind == "person" and org.kind == "organization"
        assert "vendor" in org.roles
        with pytest.raises(ValueError, match="unknown party kind"):
            Party(tenant_id="t1", kind="robot", display_name="x")
        with pytest.raises(ValueError, match="unknown roles"):
            Party(tenant_id="t1", kind="person", display_name="x",
                  roles={"alien"})

    def test_3_person_links_to_organization(self):
        eng = engine()
        p = eng.graph.add_party(person())
        org = eng.graph.add_party(Party(tenant_id="t1",
                                        kind="organization",
                                        display_name="Firma XYZ"))
        eng.graph.link_parties(tenant_id="t1", from_id=p.id, to_id=org.id,
                               role="employed_by")
        assert eng.graph.organization_of(p.id, tenant_id="t1") is org

    def test_4_party_links_to_case_quote_appointment_evidence(self):
        eng = engine()
        p = eng.graph.add_party(person())
        for kind, target in [("case", "case-1"), ("quote", "q-1"),
                             ("appointment", "appt-1"),
                             ("evidence", "ev-1")]:
            eng.graph.link(tenant_id="t1", party_id=p.id, to_id=target,
                           to_kind=kind, role="customer")
        assert eng.graph.cases_of(p.id, tenant_id="t1") == ["case-1"]
        assert [pp.id for pp, role in
                eng.graph.parties_of_case("case-1", tenant_id="t1")] \
            == [p.id]

    def test_5_27_cross_tenant_links_always_denied(self):
        eng = engine()
        a = eng.graph.add_party(person(tenant="t1"))
        b = eng.graph.add_party(person(tenant="t2",
                                       email="other@example.pl"))
        with pytest.raises(CrossTenantLinkError):
            eng.graph.link_parties(tenant_id="t1", from_id=a.id,
                                   to_id=b.id, role="knows")
        with pytest.raises(CrossTenantLinkError):
            eng.graph.link(tenant_id="t2", party_id=a.id, to_id="case-9",
                           to_kind="case")
        # Property: random edge attempts never produce a cross-tenant edge.
        rng = random.Random(2026)
        parties = [eng.graph.add_party(person(
            tenant=rng.choice(["t1", "t2"]),
            email=f"u{i}@example.pl")) for i in range(20)]
        for _ in range(100):
            x, y = rng.choice(parties), rng.choice(parties)
            try:
                eng.graph.link_parties(tenant_id=x.tenant_id,
                                       from_id=x.id, to_id=y.id,
                                       role="knows")
            except CrossTenantLinkError:
                pass
        for e in eng.graph.edges:
            if e.to_kind == "party":
                pa = eng.graph.parties[e.from_id]
                pb = eng.graph.parties[e.to_id]
                assert pa.tenant_id == pb.tenant_id == e.tenant_id

    def test_6_contact_points_normalized(self):
        p = person(email="  Jan@Example.PL ", phone="+48 600-100-200")
        assert p.contact("EMAIL") == "jan@example.pl"
        assert p.contact("MOBILE") == "+48600100200"
        with pytest.raises(ValueError, match="unknown contact point"):
            ContactPoint(kind="FAX", value="123")


class TestConsent:
    def test_7_revoked_consent_blocks_outreach(self):
        eng = engine()
        p = eng.graph.add_party(person())
        eng.record_consent(ConsentRecord(tenant_id="t1", party_id=p.id,
                                         channel="WHATSAPP",
                                         status="GRANTED"))
        eng.record_consent(ConsentRecord(tenant_id="t1", party_id=p.id,
                                         channel="WHATSAPP",
                                         status="REVOKED",
                                         source="client message"))
        d = eng.can_contact(p, channel="WHATSAPP", purpose="service")
        assert d.allowed is False
        assert "non-overrideable" in d.reasons[0]
        # Every consent change is a domain event.
        events = eng.audit.events(event_type="CRM_CONSENT_CHANGED")
        assert len(events) == 2
        assert events[-1].payload["status"] == "REVOKED"

    def test_8_unknown_marketing_consent_requires_review(self):
        eng = engine()
        p = eng.graph.add_party(person())
        eng.record_consent(ConsentRecord(tenant_id="t1", party_id=p.id,
                                         channel="EMAIL",
                                         status="GRANTED"))
        d = eng.can_contact(p, channel="EMAIL", purpose="marketing")
        assert d.allowed is False and d.requires_review is True
        # Service updates on unknown channel consent follow policy.
        d2 = eng.can_contact(p, channel="SMS", purpose="service")
        assert d2.allowed is True          # default policy allows
        strict = RelationshipEngine(AuditLog(), policy=ConsentPolicy(
            service_updates_on_unknown=False))
        strict.graph.add_party(p)
        d3 = strict.can_contact(p, channel="SMS", purpose="service")
        assert d3.allowed is False and d3.requires_review is True

    def test_consent_validation(self):
        with pytest.raises(ValueError, match="unknown consent channel"):
            ConsentRecord(tenant_id="t1", party_id="p", channel="FAX")
        with pytest.raises(ValueError, match="unknown consent status"):
            ConsentRecord(tenant_id="t1", party_id="p", channel="EMAIL",
                          status="MAYBE")


class TestPromisesAndMemory:
    def test_9_10_customer_and_finalis_promises(self):
        eng = engine()
        p = eng.graph.add_party(person())
        eng.record_promise(CustomerPromise(
            tenant_id="t1", party_id=p.id, promisor="customer",
            what="send photos", case_id="case-1"))
        eng.record_promise(CustomerPromise(
            tenant_id="t1", party_id=p.id, promisor="finalis",
            what="call back with quote by Friday", case_id="case-1"))
        assert len(eng.open_promises(p.id, tenant_id="t1")) == 2
        assert len(eng.open_promises(p.id, tenant_id="t1",
                                     promisor="finalis")) == 1
        assert eng.audit.events(event_type="CRM_PROMISE_RECORDED")
        with pytest.raises(ValueError, match="promisor"):
            eng.record_promise(CustomerPromise(
                tenant_id="t1", party_id=p.id, promisor="ai",
                what="anything"))

    def test_11_ai_memory_needs_human_verification(self):
        mem = CustomerMemory(AuditLog())
        item = mem.add(CustomerMemoryItem(
            tenant_id="t1", party_id="p1", memory_type="VERIFIED_FACT",
            content={"boiler_model": "Viessmann V200"},
            source="ai_worker", confidence=0.95))
        assert item.memory_type == "AI_SUGGESTED"    # downgraded on entry
        assert not mem.usable_for_critical_decision(item).allowed
        with pytest.raises(PermissionError, match="human"):
            mem.verify(item, verified_by="ai-worker-2",
                       actor_kind="ai_worker")
        mem.verify(item, verified_by="owner-1")
        assert item.memory_type == "VERIFIED_FACT"
        assert mem.usable_for_critical_decision(item).allowed

    def test_12_stale_memory_blocked_alone(self):
        mem = CustomerMemory()
        old = mem.add(CustomerMemoryItem(
            tenant_id="t1", party_id="p1", memory_type="VERIFIED_FACT",
            content={"address": "old street 1"}, source="human",
            recorded_at=datetime.utcnow() - timedelta(days=400)))
        d = mem.usable_for_critical_decision(old)
        assert not d.allowed and "stale" in d.reasons[0]

    def test_13_disputed_fact_blocks_automation(self):
        mem = CustomerMemory()
        item = mem.add(CustomerMemoryItem(
            tenant_id="t1", party_id="p1", memory_type="VERIFIED_FACT",
            content={"invoice_email": "a@b.pl"}, source="human"))
        mem.dispute(item, by="client complaint")
        d = mem.usable_for_critical_decision(item)
        assert not d.allowed and "disputed" in d.reasons[0].lower()

    def test_sensitive_memory_needs_permission(self):
        mem = CustomerMemory()
        item = mem.add(CustomerMemoryItem(
            tenant_id="t1", party_id="p1", memory_type="VERIFIED_FACT",
            content={"payment_issue": "chargeback history"},
            source="human", sensitive=True))
        assert not mem.usable_for_critical_decision(item).allowed
        assert mem.usable_for_critical_decision(
            item, actor_has_sensitive_permission=True).allowed


class TestDedupeMerge:
    def test_14_15_same_email_and_phone_detected(self):
        a = person(name="Jan Kowalski")
        b = person(name="J. Kowalski")
        c = duplicate_candidate(a, b)
        assert c.score >= 0.8 and c.verdict == "LIKELY_DUPLICATE"
        assert "same email" in c.signals and "same phone" in c.signals
        d = duplicate_candidate(person(email="x@a.pl", phone="+48111"),
                                person(email="y@b.pl", phone="+48222",
                                       name="Anna Nowak"))
        assert d.verdict == "NOT_DUPLICATE"

    def test_16_conflicting_verified_facts_block_auto_merge(self):
        a, b = person(), person(name="Jan Kowalski")
        c = duplicate_candidate(
            a, b,
            facts_a=[CustomerFact(tenant_id="t1", party_id=a.id,
                                  key="vat_id", value="PL111",
                                  verified=True)],
            facts_b=[CustomerFact(tenant_id="t1", party_id=b.id,
                                  key="vat_id", value="PL999",
                                  verified=True)])
        assert c.verdict == "MERGE_REQUIRES_REVIEW"
        assert any("conflicting verified fact" in s for s in c.signals)
        with pytest.raises(PermissionError, match="reason"):
            merge_parties(c, surviving=a, merged=b, decided_by="owner-1")

    def test_17_cross_tenant_never_merges(self):
        a = person(tenant="t1")
        b = person(tenant="t2")
        c = duplicate_candidate(a, b, same_external_crm_id=True)
        assert c.verdict == "DO_NOT_MERGE" and c.score == 0.0
        with pytest.raises(PermissionError):
            merge_parties(c, surviving=a, merged=b, decided_by="owner-1")

    def test_18_merge_decision_preserves_sources(self):
        audit = AuditLog()
        a, b = person(), person(name="Jan Kowalski")
        c = duplicate_candidate(a, b)
        with pytest.raises(PermissionError, match="human"):
            merge_parties(c, surviving=a, merged=b,
                          decided_by="ai-worker", actor_kind="ai_worker")
        decision = merge_parties(c, surviving=a, merged=b,
                                 decided_by="owner-1",
                                 reason="same client", audit=audit)
        assert decision.surviving_party_id == a.id
        assert decision.merged_party_ids == [b.id]
        assert b.merged_into_id == a.id           # tombstone, not deletion
        assert audit.events(event_type="CRM_PARTIES_MERGED")


class TestExternalCrmContracts:
    def test_19_external_reference_maps_provider_object_id(self):
        ref = ExternalCrmReference(tenant_id="t1", party_id="p1",
                                   provider="hubspot",
                                   object_kind="Contact",
                                   external_id="hs-123")
        assert (ref.provider, ref.object_kind, ref.external_id) \
            == ("hubspot", "Contact", "hs-123")
        with pytest.raises(ValueError, match="unknown crm object"):
            ExternalCrmReference(tenant_id="t1", party_id="p1",
                                 provider="hubspot",
                                 object_kind="Widget", external_id="1")
        with pytest.raises(ValueError, match="unknown canonical"):
            CrmObjectMapping(provider="hubspot", canonical_kind="Widget",
                             external_kind="widgets")

    def test_20_23_adapter_dry_run_and_idempotency(self):
        adapter = NullCrmAdapter()
        assert adapter.is_mock is True
        key = idempotency_key(tenant_id="t1", provider="null-crm",
                              object_kind="Contact", external_id="x1",
                              operation="update")
        # Deterministic: retries produce the same key.
        assert key == idempotency_key(
            tenant_id="t1", provider="null-crm", object_kind="Contact",
            external_id="x1", operation="update")
        r = adapter.push_object(tenant_id="t1", object_kind="Contact",
                                payload={"email": "a@b.pl"},
                                idempotency_key=key, dry_run=True)
        assert r["dry_run"] is True and adapter.pushed == []
        with pytest.raises(ValueError, match="idempotency"):
            adapter.push_object(tenant_id="t1", object_kind="Contact",
                                payload={}, idempotency_key="",
                                dry_run=False)
        adapter.push_object(tenant_id="t1", object_kind="Contact",
                            payload={"email": "a@b.pl"},
                            idempotency_key=key, dry_run=False)
        dup = adapter.push_object(tenant_id="t1", object_kind="Contact",
                                  payload={"email": "a@b.pl"},
                                  idempotency_key=key, dry_run=False)
        assert dup["skipped"] == "duplicate idempotency key"
        assert len(adapter.pushed) == 1        # never double-written


class TestSyncDecisions:
    def _policy(self, **kw):
        policy = default_policy("t1")
        policy.enabled = kw.pop("enabled", True)
        policy.dry_run = kw.pop("dry_run", False)
        policy.allow_export = kw.pop("allow_export", True)
        policy.field_mappings = [ExternalFieldMapping(
            provider="null-crm", canonical_field="email",
            external_field="properties.email")]
        for k, v in kw.items():
            setattr(policy, k, v)
        return policy

    def test_21_export_without_permission_denied(self):
        req = SyncRequest(tenant_id="t1", policy_tenant_id="t1",
                          direction="export", field="email",
                          internal_value="a@b.pl", external_value="old",
                          actor_id=None, actor_has_permission=False)
        assert sync_decision(req, self._policy()).decision \
            == "DENY_PERMISSION"

    def test_22_marketing_consent_denied_blocks_sync(self):
        req = SyncRequest(tenant_id="t1", policy_tenant_id="t1",
                          direction="export", actor_id="u1",
                          actor_has_permission=True,
                          field="marketing_opt_in",
                          internal_value="yes", external_value="no",
                          marketing_consent_denied=True)
        assert sync_decision(req, self._policy()).decision \
            == "DENY_CONSENT"

    def test_24_both_changed_requires_review(self):
        req = SyncRequest(tenant_id="t1", policy_tenant_id="t1",
                          direction="import", field="email",
                          internal_value="new@a.pl",
                          external_value="newer@b.pl",
                          internal_changed=True, external_changed=True)
        d = sync_decision(req, self._policy())
        assert d.decision == "CONFLICT_REQUIRES_REVIEW"
        assert d.conflict and d.conflict.resolution == "review"

    def test_28_verified_internal_never_overwritten_property(self):
        rng = random.Random(9)
        policy = self._policy()
        for _ in range(50):
            req = SyncRequest(
                tenant_id="t1", policy_tenant_id="t1",
                direction="import", field="email",
                internal_value="verified@finalis.pl",
                external_value=f"x{rng.randint(1, 999)}@ext.com",
                internal_verified=True,
                internal_changed=rng.random() > .5,
                external_changed=rng.random() > .5)
            d = sync_decision(req, policy)
            assert d.decision == "CONFLICT_REQUIRES_REVIEW"

    def test_more_denials_and_skips(self):
        policy = self._policy()
        base = dict(tenant_id="t1", policy_tenant_id="t1",
                    direction="import", field="email",
                    internal_value="same", external_value="same")
        assert sync_decision(SyncRequest(**base),
                             policy).decision == "SKIP_NO_CHANGE"
        assert sync_decision(SyncRequest(**{**base,
                                            "tenant_id": "t2"}),
                             policy).decision == "DENY_TENANT_MISMATCH"
        assert sync_decision(
            SyncRequest(**{**base, "external_value": "x",
                           "rate_limited": True}),
            policy).decision == "DENY_RATE_LIMIT"
        assert sync_decision(
            SyncRequest(**{**base, "field": "vat_id",
                           "external_value": "x"}),
            policy).decision == "DENY_FIELD_POLICY"
        assert sync_decision(
            SyncRequest(**{**base, "external_value": "x",
                           "is_deletion": True}),
            policy).decision == "CONFLICT_REQUIRES_REVIEW"
        dry = self._policy(dry_run=True)
        assert sync_decision(
            SyncRequest(**{**base, "external_value": "x"}),
            dry).decision == "DRY_RUN_ONLY"

    def test_25_no_secrets_in_sync_events(self):
        audit = AuditLog()
        d = sync_decision(SyncRequest(
            tenant_id="t1", policy_tenant_id="t1", direction="import",
            field="email", internal_value="a", external_value="b"),
            self._policy())
        event = record_sync_event(
            tenant_id="t1", provider="null-crm", direction="import",
            object_kind="Contact", decision=d,
            detail={"note": "api_key=sk-abc123def456ghi789 used",
                    "token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ"},
            audit=audit)
        assert "sk-abc123" not in str(event.detail)
        assert "eyJhbGci" not in str(event.detail)
        assert "[REDACTED]" in event.detail["note"]
        for ev in audit.events():
            assert "sk-abc123" not in str(ev.payload)

    def test_26_finalis_is_source_of_operational_truth(self):
        """Case outcome fields are simply not syncable: no mapping exists
        for them, so any attempt is denied by field policy."""
        policy = self._policy()
        for forbidden in ("case_state", "case_outcome", "won_completed"):
            d = sync_decision(SyncRequest(
                tenant_id="t1", policy_tenant_id="t1",
                direction="import", field=forbidden,
                internal_value="WON_COMPLETED", external_value="closed"),
                policy)
            assert d.decision == "DENY_FIELD_POLICY"
