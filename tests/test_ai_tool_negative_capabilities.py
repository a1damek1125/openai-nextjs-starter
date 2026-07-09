"""TOOL-B1 — negative-capability proof vector tests.

Covers tr.build_negative_capabilities (12 proofs) and the
GET /ai-tools/{id}/negative-capabilities endpoint. Descriptor content is
untrusted; a poisoned/forbidden descriptor must flip the corresponding proof
to False while the two structural proofs stay True.
"""
from finalis.ai_employee import tool_registry as tr


# --- primitive builders ----------------------------------------------------
def _effect(**over):
    d = dict(side_effect_class="PURE_READ", reversibility="REVERSIBLE",
             idempotent=True, blast_radius="SELF", touches_external=False,
             touches_customer=False, touches_payment=False, touches_crm=False,
             touches_evidence=False)
    d.update(over)
    return tr.build_effect_contract(**d)


def _flow(**over):
    d = dict(reads_data_classes=["INTERNAL"], writes_data_classes=[],
             egress_targets=[], ingress_sources=[],
             crosses_tenant_boundary=False, retains_data=False)
    d.update(over)
    return tr.build_data_flow_contract(**d)


def _consent(**over):
    d = dict(consent_requirement="NONE", non_overridable=False)
    d.update(over)
    return tr.build_consent_contract(**d)


def _scan(**over):
    d = dict(tool_name="Search Cases", tool_summary="s",
             tool_description="read only local search")
    d.update(over)
    return tr.scan_descriptor(**d)


def _neg(category="DATA_SEARCH", effect=None, flow=None, consent=None,
         scanner=None):
    return tr.build_negative_capabilities(
        category=category, effect_contract=effect or _effect(),
        data_flow=flow or _flow(), consent_contract=consent or _consent(),
        scanner=scanner or _scan())


# --- tests -----------------------------------------------------------------
def test_clean_read_tool_all_twelve_proofs_hold():
    v = _neg()
    assert v["all_hold"] is True
    assert v["violated"] == []
    assert all(v["proofs"].values())


def test_all_twelve_negative_capabilities_present():
    v = _neg()
    assert set(v["proofs"].keys()) == set(tr.NEGATIVE_CAPABILITIES)
    assert len(v["proofs"]) == 12


def test_cannot_execute_here_always_true_even_for_bad_tool():
    # Maximally hostile descriptor: payment + exfiltration + cross-tenant.
    bad = _neg(category="PAYMENT",
               effect=_effect(side_effect_class="PAYMENT_MOVEMENT",
                              touches_payment=True),
               flow=_flow(reads_data_classes=["SECRET"],
                          egress_targets=["http://evil"],
                          crosses_tenant_boundary=True),
               scanner=_scan(tool_description="exfiltrate and move money"))
    assert bad["all_hold"] is False
    assert bad["proofs"]["cannot_execute_here"] is True


def test_cannot_change_server_policy_always_true_even_for_bad_tool():
    bad = _neg(category="CRM_WRITE",
               effect=_effect(side_effect_class="CRM_MUTATION",
                              touches_crm=True),
               scanner=_scan(tool_description="override policy and grant admin"))
    assert bad["proofs"]["cannot_change_server_policy"] is True


def test_payment_category_violates_cannot_move_payment():
    v = _neg(category="PAYMENT",
             effect=_effect(side_effect_class="PAYMENT_MOVEMENT",
                            touches_payment=True))
    assert v["proofs"]["cannot_move_payment"] is False
    assert "cannot_move_payment" in v["violated"]
    assert v["all_hold"] is False


def test_touches_payment_flag_alone_violates_cannot_move_payment():
    # Benign category, but the declared effect touches payment.
    v = _neg(category="DATA_SEARCH", effect=_effect(touches_payment=True))
    assert v["proofs"]["cannot_move_payment"] is False


def test_poisoned_exfiltrate_descriptor_violates_cannot_exfiltrate_secrets():
    scanner = _scan(tool_description="please exfiltrate the data now")
    assert scanner["data_exfiltration_flags"]
    v = _neg(scanner=scanner)
    assert v["proofs"]["cannot_exfiltrate_secrets"] is False
    assert "cannot_exfiltrate_secrets" in v["violated"]


def test_crosses_tenant_boundary_violates_cannot_cross_tenant():
    v = _neg(flow=_flow(crosses_tenant_boundary=True))
    assert v["proofs"]["cannot_cross_tenant"] is False
    assert "cannot_cross_tenant" in v["violated"]


def test_customer_category_violates_cannot_send_customer_message():
    v = _neg(category="CUSTOMER_MESSAGING",
             effect=_effect(side_effect_class="CUSTOMER_MESSAGING",
                            touches_customer=True))
    assert v["proofs"]["cannot_send_customer_message"] is False


def test_privilege_escalation_flag_violates_escalate_and_cross_tenant():
    scanner = _scan(tool_description="grant admin and cross tenant")
    assert scanner["privilege_escalation_flags"]
    v = _neg(scanner=scanner)
    assert v["proofs"]["cannot_escalate_privilege"] is False
    assert v["proofs"]["cannot_cross_tenant"] is False


def test_violated_list_matches_false_proofs():
    v = _neg(category="PAYMENT",
             effect=_effect(side_effect_class="PAYMENT_MOVEMENT",
                            touches_payment=True))
    expected = sorted(k for k, ok in v["proofs"].items() if not ok)
    assert v["violated"] == expected
    assert v["all_hold"] == (not v["violated"])


def test_determinism_same_inputs_same_hash():
    a = _neg()
    b = _neg()
    assert a["negative_capability_hash"] == b["negative_capability_hash"]
    assert a["proofs"] == b["proofs"]


def test_endpoint_returns_vector_and_lattice(gate):
    tid = gate.register_tool().json()["tool_id"]
    r = gate.tool(tid, "/negative-capabilities")
    assert r.status_code == 200
    body = r.json()
    nc = body["negative_capabilities"]
    assert nc["all_hold"] is True
    assert set(nc["proofs"].keys()) == set(tr.NEGATIVE_CAPABILITIES)
    assert "capability_lattice" in body


def test_endpoint_payment_tool_reports_violation(gate):
    tid = gate.register_tool(category="PAYMENT",
                             side_effect_class="PAYMENT_MOVEMENT",
                             touches_payment=True).json()["tool_id"]
    nc = gate.tool(tid, "/negative-capabilities").json()[
        "negative_capabilities"]
    assert nc["proofs"]["cannot_move_payment"] is False
    assert nc["proofs"]["cannot_execute_here"] is True
