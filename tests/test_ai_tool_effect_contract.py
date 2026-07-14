"""TOOL-B1 — effect contract (pure kernel + endpoint).

build_effect_contract records a DECLARED side-effect posture. It performs no
execution (execution_performed is structurally False). Tests cover determinism,
the least→most-dangerous side-effect rank ordering, the always-False execution
flag, ValueError on an unknown side_effect_class, touches_* surfacing, and that a
registered PURE_READ tool's effect-contract hash verifies via tr._core_hash.
"""
import pytest

from finalis.ai_employee import tool_registry as tr
from tests.conftest import gate  # noqa: F401


def _ec(**over):
    kw = dict(side_effect_class="PURE_READ", reversibility="REVERSIBLE",
              idempotent=True, blast_radius="SELF", touches_external=False,
              touches_customer=False, touches_payment=False, touches_crm=False,
              touches_evidence=False, declared_summary="reads things")
    kw.update(over)
    return tr.build_effect_contract(**kw)


class TestDeterminism:
    def test_same_input_same_hash(self):
        assert _ec()["effect_contract_hash"] == _ec()["effect_contract_hash"]

    def test_hash_recomputes_via_core_hash(self):
        c = _ec()
        assert tr._core_hash(c, "effect_contract_hash") \
            == c["effect_contract_hash"]

    def test_hash_excludes_itself(self):
        c = _ec()
        c2 = dict(c, effect_contract_hash="tampered")
        assert tr._core_hash(c2, "effect_contract_hash") \
            == c["effect_contract_hash"]

    def test_changed_side_effect_class_changes_hash(self):
        assert _ec(side_effect_class="PURE_READ")["effect_contract_hash"] \
            != _ec(side_effect_class="INTERNAL_WRITE")["effect_contract_hash"]

    def test_changed_blast_radius_changes_hash(self):
        assert _ec(blast_radius="SELF")["effect_contract_hash"] \
            != _ec(blast_radius="TENANT")["effect_contract_hash"]

    def test_version_string_present(self):
        assert _ec()["effect_contract_version"] == tr.EFFECT_CONTRACT_VERSION


class TestSideEffectRank:
    def test_rank_matches_taxonomy(self):
        for cls, rank in tr.SIDE_EFFECT_RANK.items():
            assert _ec(side_effect_class=cls)["side_effect_rank"] == rank

    def test_strict_ordering_core_chain(self):
        order = ["PURE_READ", "INTERNAL_WRITE", "EXTERNAL_WRITE",
                 "PAYMENT_MOVEMENT", "DESTRUCTIVE"]
        ranks = [_ec(side_effect_class=c)["side_effect_rank"] for c in order]
        assert ranks == sorted(ranks)
        assert len(set(ranks)) == len(ranks)

    def test_pure_read_is_lowest(self):
        assert _ec(side_effect_class="PURE_READ")["side_effect_rank"] \
            == min(tr.SIDE_EFFECT_RANK.values())

    def test_destructive_is_highest(self):
        assert _ec(side_effect_class="DESTRUCTIVE")["side_effect_rank"] \
            == max(tr.SIDE_EFFECT_RANK.values())


class TestExecutionPerformed:
    def test_always_false_pure_read(self):
        assert _ec()["execution_performed"] is False

    def test_always_false_destructive(self):
        assert _ec(side_effect_class="DESTRUCTIVE",
                   reversibility="IRREVERSIBLE")["execution_performed"] is False


class TestUnknownClass:
    def test_unknown_raises_value_error(self):
        with pytest.raises(ValueError):
            _ec(side_effect_class="NOT_A_CLASS")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _ec(side_effect_class="")


class TestTouchesFlags:
    def test_touches_flags_surface_true(self):
        c = _ec(side_effect_class="EXTERNAL_WRITE", touches_external=True,
                touches_customer=True, touches_payment=True, touches_crm=True,
                touches_evidence=True)
        assert c["touches_external"] and c["touches_customer"]
        assert c["touches_payment"] and c["touches_crm"]
        assert c["touches_evidence"]

    def test_touches_flags_coerced_to_bool(self):
        c = _ec(touches_external=1, touches_customer=0)
        assert c["touches_external"] is True
        assert c["touches_customer"] is False

    def test_touches_flag_change_changes_hash(self):
        assert _ec(touches_payment=False)["effect_contract_hash"] \
            != _ec(touches_payment=True)["effect_contract_hash"]

    def test_idempotent_coerced_to_bool(self):
        assert _ec(idempotent=0)["idempotent"] is False


class TestRegisteredToolEffectContract:
    def test_pure_read_effect_contract_hash_verifies(self, gate):
        r = gate.register_tool()  # clean PURE_READ read-only tool
        assert r.status_code == 200
        tool_id = r.json()["tool_id"]
        lv = gate.latest_tool_version(tool_id)
        ec = lv["effect_contract"]
        assert ec["side_effect_class"] == "PURE_READ"
        assert ec["side_effect_rank"] == 0
        assert ec["execution_performed"] is False
        assert tr._core_hash(ec, "effect_contract_hash") \
            == ec["effect_contract_hash"]

    def test_registered_external_write_has_higher_rank(self, gate):
        r = gate.register_tool(category="INTERNAL_WRITE",
                               side_effect_class="EXTERNAL_WRITE",
                               declared_side_effects=["EXTERNAL_WRITE"])
        tool_id = r.json()["tool_id"]
        ec = gate.latest_tool_version(tool_id)["effect_contract"]
        assert ec["side_effect_rank"] \
            == tr.SIDE_EFFECT_RANK["EXTERNAL_WRITE"]
        assert ec["execution_performed"] is False
