"""TOOL-B1 — capability lattice / reachability tests.

Covers tr.build_capability_lattice, tr.reachable_forbidden, and the GET
/ai-tools/{id}/negative-capabilities endpoint. Tests assert ACTUAL behavior.
"""
from finalis.ai_employee import tool_registry as tr
from tests.conftest import OWNER, MANAGER, VIEWER


def _ec(se_class, **over):
    kw = dict(reversibility="REVERSIBLE", idempotent=True, blast_radius="SELF",
              touches_external=False, touches_customer=False,
              touches_payment=False, touches_crm=False, touches_evidence=False)
    kw.update(over)
    return tr.build_effect_contract(side_effect_class=se_class, **kw)


def _df(reads=None, writes=None, egress=None, crosses=False):
    return tr.build_data_flow_contract(
        reads_data_classes=reads or [], writes_data_classes=writes or [],
        egress_targets=egress or [], ingress_sources=[],
        crosses_tenant_boundary=crosses, retains_data=False)


def _lattice(category, ec, df, tool_id="t", tenant_id="x"):
    return tr.build_capability_lattice(
        tool_id=tool_id, tenant_id=tenant_id, category=category,
        effect_contract=ec, data_flow=df)


def test_destructive_effect_is_forbidden_reachable():
    lat = _lattice("INTERNAL_WRITE", _ec("DESTRUCTIVE"), _df(reads=["INTERNAL"]))
    assert lat["forbidden_effect_reachable"] == ["DESTRUCTIVE"]
    assert lat["has_forbidden_reachable"] is True


def test_payment_movement_effect_is_forbidden_reachable():
    lat = _lattice("INTERNAL_COMPUTE",
                   _ec("PAYMENT_MOVEMENT", touches_payment=True),
                   _df(reads=["INTERNAL"]))
    assert lat["forbidden_effect_reachable"] == ["PAYMENT_MOVEMENT"]
    assert lat["has_forbidden_reachable"] is True


def test_crm_and_evidence_mutation_are_forbidden_reachable():
    for se in ("CRM_MUTATION", "EVIDENCE_MUTATION", "CUSTOMER_MESSAGING"):
        lat = _lattice("INTERNAL_WRITE", _ec(se), _df(reads=["INTERNAL"]))
        assert lat["has_forbidden_reachable"] is True
        assert se in lat["forbidden_effect_reachable"]


def test_pure_read_has_no_forbidden_reachable():
    lat = _lattice("DATA_SEARCH", _ec("PURE_READ"), _df(reads=["INTERNAL"]))
    assert lat["reachable_effects"] == ["PURE_READ"]
    assert lat["forbidden_effect_reachable"] == []
    assert lat["has_forbidden_reachable"] is False


def test_egress_path_adds_egress_node_but_is_not_a_forbidden_effect():
    # An egress target reaches an EGRESS node; EGRESS is not in
    # FORBIDDEN_SIDE_EFFECTS, so the lattice does not flag it as forbidden.
    lat = _lattice("DATA_SEARCH", _ec("PURE_READ"),
                   _df(reads=["INTERNAL"], egress=["https://sink.example"]))
    assert "EGRESS" in lat["reachable_effects"]
    assert lat["forbidden_effect_reachable"] == []
    assert lat["has_forbidden_reachable"] is False


def test_reachable_effects_includes_written_data_classes_in_nodes():
    lat = _lattice("INTERNAL_WRITE", _ec("INTERNAL_WRITE"),
                   _df(reads=["INTERNAL"], writes=["INTERNAL"]))
    # The written data class becomes a DATA_WRITE node with an edge.
    write_nodes = [n for n in lat["nodes"] if n["node"] == "DATA_WRITE"]
    assert any(n["id"] == "INTERNAL" for n in write_nodes)
    assert lat["reachable_effects"] == ["INTERNAL_WRITE"]


def test_reachable_forbidden_helper():
    forbidden = _lattice("INTERNAL_WRITE", _ec("DESTRUCTIVE"),
                         _df(reads=["INTERNAL"]))
    benign = _lattice("DATA_SEARCH", _ec("PURE_READ"), _df(reads=["INTERNAL"]))
    assert tr.reachable_forbidden(forbidden) is True
    assert tr.reachable_forbidden(benign) is False


def test_capability_lattice_deterministic_hash():
    ec, df = _ec("PURE_READ"), _df(reads=["INTERNAL"])
    a = _lattice("DATA_SEARCH", ec, df)
    b = _lattice("DATA_SEARCH", ec, df)
    assert a["capability_lattice_hash"] == b["capability_lattice_hash"]


def test_capability_lattice_hash_changes_with_effect():
    df = _df(reads=["INTERNAL"])
    read = _lattice("DATA_SEARCH", _ec("PURE_READ"), df)
    dest = _lattice("DATA_SEARCH", _ec("DESTRUCTIVE"), df)
    assert read["capability_lattice_hash"] != dest["capability_lattice_hash"]


def test_lattice_nodes_and_edges_structure():
    lat = _lattice("DATA_SEARCH", _ec("PURE_READ"), _df(reads=["INTERNAL"]))
    node_kinds = {n["node"] for n in lat["nodes"]}
    assert {"INPUT", "CATEGORY", "SIDE_EFFECT"} <= node_kinds
    assert all(set(e) == {"from", "to"} for e in lat["edges"])


def test_endpoint_negative_capabilities_returns_capability_lattice(gate):
    r = gate.register_tool()
    tool_id = r.json()["tool_id"]
    resp = gate.tool(tool_id, "/negative-capabilities", actor=OWNER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["capability_lattice"]["tool_id"] == tool_id
    assert body["capability_lattice"]["has_forbidden_reachable"] is False
    assert body["negative_capabilities"]["all_hold"] is True
    assert body["honesty_labels"] == tr.HONESTY_LABELS


def test_endpoint_lattice_flags_forbidden_reachable_for_destructive(gate):
    # A DESTRUCTIVE declared tool is a forbidden capability; the endpoint's
    # lattice reflects the reachable forbidden effect.
    r = gate.register_tool(category="INTERNAL_WRITE",
                           side_effect_class="DESTRUCTIVE",
                           declared_side_effects=["DESTRUCTIVE"])
    tool_id = r.json()["tool_id"]
    body = gate.tool(tool_id, "/negative-capabilities", actor=OWNER).json()
    assert body["capability_lattice"]["has_forbidden_reachable"] is True
    assert "DESTRUCTIVE" in body["capability_lattice"][
        "forbidden_effect_reachable"]
