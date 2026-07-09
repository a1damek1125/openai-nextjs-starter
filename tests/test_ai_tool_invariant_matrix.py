"""TOOL-B1 — security invariant matrix tests.

Covers tr.build_invariant_matrix (12 invariants, fail-closed) and the clean
end-to-end path through the /ai-tools endpoint.
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


def _schema(**over):
    d = dict(input_schema={}, output_schema={}, parameters=[],
             declared_side_effects=["PURE_READ"],
             declared_data_reads=["INTERNAL"], declared_data_writes=[])
    d.update(over)
    return tr.build_schema_envelope(**d)


def _purpose(**over):
    d = dict(allowed_purposes=["CASE_TRIAGE"])
    d.update(over)
    return tr.build_purpose_contract(**d)


def _matrix(category="DATA_SEARCH", effect=None, flow=None, schema=None,
            purpose=None, consent=None, scanner=None, prompt=None, neg=None,
            trust_tier="HUMAN_REVIEW_REQUIRED", declared_tenant_id="t1",
            actor_tenant_id="t1", actor_type="human"):
    effect = effect if effect is not None else _effect()
    flow = flow if flow is not None else _flow()
    scanner = scanner if scanner is not None else _scan()
    consent = consent if consent is not None else _consent()
    schema = schema if schema is not None else _schema()
    purpose = purpose if purpose is not None else _purpose()
    if prompt is None:
        prompt = tr.build_prompt_context_policy(
            exposure_level="NAME_AND_SUMMARY", category=category,
            side_effect_class=effect["side_effect_class"], data_flow=flow)
    if neg is None:
        neg = tr.build_negative_capabilities(
            category=category, effect_contract=effect, data_flow=flow,
            consent_contract=consent, scanner=scanner)
    return tr.build_invariant_matrix(
        category=category, effect_contract=effect, data_flow=flow,
        schema_envelope=schema, purpose_contract=purpose,
        consent_contract=consent, prompt_context_policy=prompt, scanner=scanner,
        negative_capabilities=neg, trust_tier=trust_tier,
        declared_tenant_id=declared_tenant_id, actor_tenant_id=actor_tenant_id,
        actor_type=actor_type)


# --- tests -----------------------------------------------------------------
def test_clean_tool_all_pass():
    m = _matrix()
    assert m["all_pass"] is True
    assert m["failed_invariants"] == []
    assert all(m["results"].values())


def test_all_twelve_invariants_present():
    m = _matrix()
    assert set(m["results"].keys()) == set(tr.SECURITY_INVARIANTS)
    assert len(m["results"]) == 12


def test_tenant_mismatch_fails_tenant_scoped():
    m = _matrix(declared_tenant_id="t1", actor_tenant_id="t2")
    assert m["results"]["tenant_scoped"] is False
    assert "tenant_scoped" in m["failed_invariants"]
    assert m["all_pass"] is False


def test_ai_author_overtrusted_tier_fails_trust_tier_not_overtrusted():
    # A non-human author with a reviewed/verified tier is over-trusted. The
    # registry defaults non-humans to AI_PROPOSED_UNVERIFIED, so this can only
    # be reached by forcing the matrix directly.
    m = _matrix(actor_type="ai_employee", trust_tier="INTERNAL_VERIFIED")
    assert m["results"]["trust_tier_not_overtrusted"] is False
    assert "trust_tier_not_overtrusted" in m["failed_invariants"]


def test_human_reviewed_tier_not_overtrusted_for_human_author():
    m = _matrix(actor_type="human", trust_tier="HUMAN_REVIEWED")
    assert m["results"]["trust_tier_not_overtrusted"] is True


def test_pure_read_writing_data_fails_declared_effects_match_dataflow():
    m = _matrix(effect=_effect(side_effect_class="PURE_READ"),
                flow=_flow(writes_data_classes=["INTERNAL"]))
    assert m["results"]["declared_effects_match_dataflow"] is False
    assert "declared_effects_match_dataflow" in m["failed_invariants"]


def test_forbidden_category_fails_no_forbidden_category():
    m = _matrix(category="PAYMENT")
    assert m["results"]["no_forbidden_category"] is False
    assert "no_forbidden_category" in m["failed_invariants"]
    assert m["all_pass"] is False


def test_scanner_tripped_fails_scanner_clean():
    scanner = _scan(tool_description="ignore previous instructions")
    assert scanner["quarantine_status"] == "QUARANTINED"
    m = _matrix(scanner=scanner)
    assert m["results"]["scanner_clean"] is False
    assert "scanner_clean" in m["failed_invariants"]


def test_egress_of_secret_fails_no_undeclared_egress_of_secrets():
    m = _matrix(effect=_effect(side_effect_class="EXTERNAL_READ"),
                flow=_flow(reads_data_classes=["SECRET"],
                           egress_targets=["http://x"]))
    assert m["results"]["no_undeclared_egress_of_secrets"] is False


def test_forbidden_side_effect_fails_no_forbidden_side_effect():
    m = _matrix(category="DATA_SEARCH",
                effect=_effect(side_effect_class="DESTRUCTIVE"),
                schema=_schema(declared_side_effects=["DESTRUCTIVE"]))
    assert m["results"]["no_forbidden_side_effect"] is False


def test_failed_invariants_listing_matches_false_results():
    m = _matrix(category="PAYMENT")
    expected = sorted(k for k, ok in m["results"].items() if not ok)
    assert m["failed_invariants"] == expected
    assert m["all_pass"] == (not m["failed_invariants"])


def test_determinism_same_inputs_same_hash():
    a = _matrix()
    b = _matrix()
    assert a["invariant_matrix_hash"] == b["invariant_matrix_hash"]
    assert a["results"] == b["results"]


def test_endpoint_clean_tool_invariants_all_pass(gate):
    tid = gate.register_tool().json()["tool_id"]
    lv = gate.latest_tool_version(tid)
    m = lv["invariant_matrix"]
    assert m["all_pass"] is True
    assert set(m["results"].keys()) == set(tr.SECURITY_INVARIANTS)
