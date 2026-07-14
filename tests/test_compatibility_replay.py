"""SP0007 FINALIS — Historical Compatibility Corpus, Workflow Replay, Proof
Interpretability, Differential/Metamorphic verification, Version Negotiation,
Adapters and Bridges. Covers AC-0007-091..125.

Imports ONLY from tools.compatibility.*.
"""
from __future__ import annotations

from tools.compatibility import model
from tools.compatibility import canon
from tools.compatibility.model import (
    P0, P1, P2, FIXTURE_KINDS, CORPUS_CLASSES, DIRECTIONS,
    WORKFLOW_REPLAY_FAILED, PROOF_VERSION_UNREADABLE,
    VERSION_DOWNGRADE_DETECTED, SECURITY_DOWNGRADE_BLOCKED)
from tools.compatibility.corpus import (
    validate_fixture, corpus_sufficiency, corpus_stats, immutability_findings)
from tools.compatibility.replay import (
    replay_history, replay_findings, proof_interpretability_findings,
    differential, metamorphic_checks)
from tools.compatibility.negotiation import (
    pinning_findings, negotiate, downgrade_findings, firewall_findings,
    validate_adapter, bridge, validate_bridge)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _sev(fs):
    return {f.severity for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _fixture(**over):
    fx = {
        "fixture_id": "fx-1",
        "contract_id": "C1",
        "contract_version": "1.0.0",
        "fixture_kind": "REQUEST",
        "payload": {"a": 1},
        "expected_behavior": {"ok": True},
        "semantic_epoch": "E1",
        "tenant_class": "SYNTHETIC",
        "sensitivity": "NON_SENSITIVE",
        "corpus_class": "COMMON",
        "provenance": {"source": "x"},
    }
    fx.update(over)
    return fx


# ============ AC-0007-091..100 : Historical Compatibility Corpus ============

def test_ac091_full_valid_fixture_validates_clean():
    # AC-0007-091
    assert validate_fixture(_fixture()) == []


def test_ac092_production_raw_tenant_is_poisoned_corpus_p0():
    # AC-0007-092 — PRODUCTION_RAW tenant data never enters the corpus
    fs = validate_fixture(_fixture(tenant_class="PRODUCTION_RAW"))
    assert P0 in _sev(fs)


def test_ac093_unknown_fixture_kind_flagged():
    # AC-0007-093
    fs = validate_fixture(_fixture(fixture_kind="NOT_A_KIND"))
    assert fs
    assert any("fixture_kind" in f.message for f in fs)


def test_ac094_corpus_sufficiency_missing_adversarial_flags():
    # AC-0007-094 — missing ADVERSARIAL class => insufficiency finding
    fixtures = [
        _fixture(fixture_id="a", corpus_class="COMMON"),
        _fixture(fixture_id="b", corpus_class="EDGE"),
        _fixture(fixture_id="c", corpus_class="RARE_CRITICAL"),
    ]
    fs = corpus_sufficiency(fixtures, contract_id="C1")
    assert any("corpus insufficient" in f.message.lower() for f in fs)
    # the ADVERSARIAL gap is a required-class gap (P1)
    adv = [f for f in fs if f.details.get("missing_class") == "ADVERSARIAL"]
    assert adv and adv[0].severity == P1


def test_ac095_all_six_fixture_kinds_representable():
    # AC-0007-095 — every FIXTURE_KIND is a valid, clean fixture
    assert len(FIXTURE_KINDS) == 6
    for kind in FIXTURE_KINDS:
        assert validate_fixture(_fixture(fixture_kind=kind)) == []


def test_ac096_provenance_and_semantic_epoch_required():
    # AC-0007-096
    no_prov = validate_fixture(_fixture(provenance={}))
    assert any("provenance" in f.message for f in no_prov)
    no_epoch = validate_fixture(_fixture(semantic_epoch=""))
    assert any("semantic_epoch" in f.message for f in no_epoch)


def test_ac097_corpus_stats_observable():
    # AC-0007-097 — corpus composition is observable
    fixtures = [_fixture(fixture_id="a"), _fixture(fixture_id="b",
                                                   corpus_class="EDGE")]
    stats = corpus_stats(fixtures)
    assert stats["total"] == 2
    assert stats["by_class"]["COMMON"] == 1
    assert stats["by_kind"]["REQUEST"] == 2


def test_ac098_sufficient_corpus_clean_on_required_classes():
    # AC-0007-098 — all required classes present => no P1 insufficiency
    fixtures = [_fixture(fixture_id=c, corpus_class=c)
                for c in ("COMMON", "EDGE", "ADVERSARIAL", "RARE_CRITICAL")]
    fs = corpus_sufficiency(fixtures, contract_id="C1")
    assert P1 not in _sev(fs)


def test_ac099_corpus_class_must_be_known():
    # AC-0007-099
    fs = validate_fixture(_fixture(corpus_class="BOGUS"))
    assert any("corpus_class" in f.message for f in fs)


def test_ac100_immutability_wrong_recorded_hash_p0():
    # AC-0007-100 — content diverging from recorded hash is corpus mutation P0
    fx = _fixture()
    fs = immutability_findings(fx, "deadbeef-not-the-real-hash")
    assert _sev(fs) == {P0}
    # a matching recorded hash yields nothing
    good = canon.fixture_hash(fx)
    assert immutability_findings(fx, good) == []


# ============ AC-0007-101..104 : Workflow Replay Harness ============

_TABLE = {"A": {"go": "B"}, "B": {"finish": "C"}}
_HISTORY = [{"event": "go", "to_state": "B"},
            {"event": "finish", "to_state": "C"}]


def test_ac101_matching_replay_passes_bounded_evidence():
    # AC-0007-101
    res = replay_history(_HISTORY, _TABLE, initial="A")
    assert res["verdict"] == "REPLAY_PASSED"
    assert res["bounded_evidence"] is True


def test_ac102_missing_transition_diverges_with_counterexample():
    # AC-0007-102
    table = {"A": {"go": "B"}}  # lacks B/finish transition
    res = replay_history(_HISTORY, table, initial="A")
    assert res["verdict"] == "DIVERGED"
    assert isinstance(res["counterexample"], dict)
    assert res["counterexample"]["event"] == "finish"


def test_ac103_replay_findings_p0_with_counterexample():
    # AC-0007-103
    table = {"A": {"go": "B"}}
    fs = replay_findings([_HISTORY], table, initial="A")
    assert _k(fs) == {WORKFLOW_REPLAY_FAILED}
    assert _sev(fs) == {P0}
    assert "counterexample" in fs[0].details


def test_ac104_pass_does_not_claim_universal_proof():
    # AC-0007-104 — passing recorded histories is bounded evidence, not proof
    res = replay_history(_HISTORY, _TABLE, initial="A")
    assert res["bounded_evidence"] is True
    assert "note" in res  # explicitly disclaims universal proof
    assert replay_findings([_HISTORY], _TABLE, initial="A") == []


# ============ AC-0007-105..108 : Proof Interpretability ============

def test_ac105_unreadable_envelope_version_p0():
    # AC-0007-105 — no reader for a historical envelope version => P0
    fs = proof_interpretability_findings(
        {"envelope_version": "v9", "proof_id": "p"}, {"v1": {}})
    assert _k(fs) == {PROOF_VERSION_UNREADABLE}
    assert P0 in _sev(fs)


def test_ac106_readable_envelope_no_finding():
    # AC-0007-106
    fs = proof_interpretability_findings(
        {"envelope_version": "v1"}, {"v1": {"reinterprets": False}})
    assert fs == []


def test_ac107_reinterpreting_reader_blocked_p0():
    # AC-0007-107/108 — a new validator cannot silently reinterpret old proof
    fs = proof_interpretability_findings(
        {"envelope_version": "v1"}, {"v1": {"reinterprets": True}})
    assert _k(fs) == {PROOF_VERSION_UNREADABLE}
    assert _sev(fs) == {P0}


# ============ AC-0007-109/110 : Differential + Metamorphic ============

def _impl_a(payload):
    return {"n": payload.get("a", 0) * 2}


def _impl_a_copy(payload):
    return {"n": payload.get("a", 0) * 2}


def _impl_divergent(payload):
    return {"n": payload.get("a", 0) * 3}


def _impl_raises(payload):
    raise ValueError("boom")


_DIFF_FIXTURES = [_fixture(fixture_id="d1", payload={"a": 1}),
                  _fixture(fixture_id="d2", payload={"a": 2})]


def test_ac109_differential_consistent():
    # AC-0007-109 — identical implementations are CONSISTENT
    res = differential(_DIFF_FIXTURES, _impl_a, _impl_a_copy)
    assert res["verdict"] == "CONSISTENT"
    assert res["divergences"] == []


def test_ac110_differential_divergent_lists_divergence():
    # AC-0007-110 — divergent impl => DIVERGENT with the divergence listed
    res = differential(_DIFF_FIXTURES, _impl_a, _impl_divergent)
    assert res["verdict"] == "DIVERGENT"
    assert len(res["divergences"]) == len(_DIFF_FIXTURES)


def test_ac110_exception_counts_as_divergence():
    # AC-0007-110 — an implementation that raises is divergent behavior
    res = differential(_DIFF_FIXTURES, _impl_a, _impl_raises)
    assert res["verdict"] == "DIVERGENT"
    assert res["divergences"]


def test_metamorphic_order_insensitive_evaluator_all_held():
    # metamorphic — invariant-preserving mutations do not change evaluation
    def evaluate(p):
        return canon.core_hash({"a": p.get("a"), "b": p.get("b")})

    payload = {"a": 1, "b": 2}
    res = metamorphic_checks(payload, evaluate)
    assert res["all_held"] is True
    # reordering keys specifically holds
    reorder = [c for c in res["checks"] if c["mutation"] == "reorder_keys"]
    assert reorder and reorder[0]["invariant_held"] is True


# ============ AC-0007-111/112 : Version Pinning ============

def test_ac111_protected_latest_binding_downgrade_p0():
    # AC-0007-111 — protected binding floating on "latest" => downgrade P0
    fs = pinning_findings({"contract_id": "C1", "protected": True,
                           "version": "latest"})
    assert _k(fs) == {VERSION_DOWNGRADE_DETECTED}
    assert _sev(fs) == {P0}


def test_ac112_exact_pin_protected_clean():
    # AC-0007-112 — an exact pin protected => no finding
    assert pinning_findings({"contract_id": "C1", "protected": True,
                             "version": "1.0.0"}) == []


# ============ AC-0007-113..116 : Version Negotiation + Downgrade ============

def test_ac113_missing_version_fail_closed():
    # AC-0007-113
    assert negotiate(["1.0", "2.0"], None)["result"] == "FAIL_CLOSED"


def test_ac114_unsupported_and_ambiguous_fail_closed():
    # AC-0007-114
    assert negotiate(["1.0", "2.0"], "3.0")["result"] == "FAIL_CLOSED"
    assert negotiate(["1.0", "2.0"], "1.*")["result"] == "FAIL_CLOSED"
    assert negotiate(["1.0", "2.0"], "1-2")["result"] == "FAIL_CLOSED"


def test_ac115_supported_version_accepted():
    # AC-0007-115
    res = negotiate(["1.0", "2.0"], "2.0")
    assert res["result"] == "ACCEPTED"
    assert res["version"] == "2.0"


def test_ac116_security_downgrade_blocked_p0():
    # AC-0007-116 — proposing a weaker version is blocked
    rank = {"strong": 3, "weak": 1}
    fs = downgrade_findings("strong", "weak", security_rank=rank)
    assert _k(fs) == {SECURITY_DOWNGRADE_BLOCKED}
    assert _sev(fs) == {P0}
    # unknown-in-rank proposed also fails closed P0
    fs2 = downgrade_findings("strong", "mystery", security_rank=rank)
    assert _sev(fs2) == {P0}


# ============ AC-0007-117 : Compatibility Firewall ============

def test_ac117_provider_version_leak_flagged():
    # AC-0007-117 — provider-version branches in core leak past the firewall
    fs = firewall_findings({"contract_id": "core",
                            "provider_version_branches": {"openai": "v1"}})
    assert fs
    # a clean core module has no finding
    assert firewall_findings({"contract_id": "core"}) == []


# ============ AC-0007-118..122 : Directional Adapters ============

def _adapter(**over):
    a = {
        "source_contract": "A", "source_version": "1.0",
        "target_contract": "B", "target_version": "2.0",
        "direction": DIRECTIONS[0], "losses": [],
        "failure_semantics": "REJECT",
        "semantic_epoch_relationship": "EQUIVALENT",
    }
    a.update(over)
    return a


def test_ac118_wellformed_adapter_clean():
    # AC-0007-118
    assert validate_adapter(_adapter()) == []


def test_ac119_missing_fields_p1_each():
    # AC-0007-119..121 — each missing required field is P1
    for fld in ("source_contract", "direction", "losses", "failure_semantics"):
        bad = _adapter()
        del bad[fld]
        fs = validate_adapter(bad)
        assert fs and all(f.severity == P1 for f in fs), fld


def test_ac122_redefines_semantics_p0():
    # AC-0007-122 — an adapter can never redefine core semantics
    fs = validate_adapter(_adapter(redefines_semantics=True))
    assert P0 in _sev(fs)


# ============ AC-0007-123..125 : Bridges ============

def test_ac123_bridge_is_non_authoritative_with_hash():
    # AC-0007-123
    b = bridge("SEMANTIC_EPOCH", "e1", "e2")
    assert b["non_authoritative"] is True
    assert b["bridge_hash"]
    assert validate_bridge(b) == []


def test_ac124_authoritative_bridge_p0():
    # AC-0007-124 — a bridge claiming semantic authority is P0
    b = bridge("SEMANTIC_EPOCH", "e1", "e2")
    b["authoritative"] = True
    fs = validate_bridge(b)
    assert P0 in _sev(fs)


def test_ac125_unknown_bridge_kind_p1():
    # AC-0007-125
    b = bridge("NOT_A_BRIDGE", "e1", "e2")
    fs = validate_bridge(b)
    assert fs and any(f.severity == P1 for f in fs)
