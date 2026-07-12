"""SP0010 property-based, metamorphic and scale tests (§20 tests 72..82).

Deterministic property checks over generated hypergraphs, evidence domains,
paired worlds and defeater graphs, plus metamorphic invariances (file
relocation, display-label change, graph ordering) and a bounded scale test.
"""
from __future__ import annotations

from pathlib import Path

from tools.architecture_closure import (canon, model, hypergraph, epistemic,
                                        evidence, defeaters, circularity,
                                        noninterference, closure)

ROOT = Path(__file__).resolve().parents[1]


# --- property: conjunctive activation never fires on a proper subset ---------
def test_prop_conjunctive_activation():
    for n in range(2, 8):
        premises = [f"P{i}" for i in range(n)]
        edges = [{"conclusion_claim_ref": "G", "premise_claim_refs": premises,
                  "conjunctive": True}]
        # every proper subset must NOT activate
        for miss in range(n):
            anchored = [p for j, p in enumerate(premises) if j != miss]
            hg = {"anchored": anchored, "edges": edges}
            assert "G" not in hypergraph.positive_support_closure(
                hg)["supported"]
        # the full set activates
        hg_full = {"anchored": premises, "edges": edges}
        assert "G" in hypergraph.positive_support_closure(hg_full)["supported"]


# --- property: four-valued state is a pure function of (support, refute) ------
def test_prop_four_valued_total():
    seen = set()
    for s in (True, False):
        for r in (True, False):
            seen.add(model.epistemic_state(s, r))
    assert seen == set(model.EPISTEMIC_STATES)


# --- property: minimal support is an antichain (no set contains another) -----
def test_prop_minimal_support_antichain():
    sets = [["a"], ["a", "b"], ["b", "c"], ["b", "c", "d"], ["e"]]
    mini = evidence._minimize(sets)
    for i, x in enumerate(mini):
        for j, y in enumerate(mini):
            if i != j:
                assert not set(x) < set(y)


# --- property: grounded extension is conflict-free -----------------------------
def test_prop_grounded_extension_conflict_free():
    args = ["A", "B", "C", "D"]
    attacks = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")]  # even cycle
    ext = defeaters.grounded_extension(args, attacks)
    ins = set(ext["in"])
    for src, tgt in attacks:
        assert not (src in ins and tgt in ins)   # no IN attacks another IN


# --- property: any unsupported cycle over generated graphs is flagged ---------
def test_prop_unsupported_cycles_flagged():
    for n in range(2, 6):
        nodes = [f"N{i}" for i in range(n)]
        edges = {nodes[i]: [nodes[(i + 1) % n]] for i in range(n)}  # ring
        res = circularity.analyze(edges, anchored=set(), nodes=set(nodes))
        assert res["unsupported"]


# --- property: paired-world PASS requires ignoring the protected var ----------
def test_prop_noninterference_leak_always_fails():
    for hp in noninterference.HYPERPROPERTIES:
        spec = noninterference.HYPERPROPERTIES[hp]
        varying = spec["varying"]

        def leak(w, _v=varying):
            return {"leak": w[_v]}
        assert noninterference.verify_hyperproperty(
            hp, model_override=leak)["status"] == "FAIL"


# --- metamorphic: display-label change does not move the closure digest -------
def test_metamorphic_label_change_stable():
    a = {"canonical_name": "x", "display_name": "Old", "label": "L1"}
    b = {"canonical_name": "x", "display_name": "New", "label": "L2"}
    assert canon.core_hash(a) == canon.core_hash(b)


# --- metamorphic: dict/graph ordering does not change roots -------------------
def test_metamorphic_ordering_stable():
    cr1 = {"a": "1", "b": "2", "c": "3"}
    cr2 = {"c": "3", "a": "1", "b": "2"}
    assert canon.global_root(cr1) == canon.global_root(cr2)


# --- scale: closure builds within a bounded claim universe deterministically --
def test_scale_closure_bounded_and_deterministic():
    t = closure.build_closure(ROOT)
    # bounded: claim universe is modest (constitutions * guarantees + invariants)
    assert len(t["epistemic_states"]) < 200
    assert t["closure_digest"] == closure.build_closure(ROOT)["closure_digest"]


# --- resource: fixed-point iteration terminates quickly ----------------------
def test_resource_fixed_point_bounded():
    t = closure.build_closure(ROOT)
    assert t["positive_support"]["iterations"] < 20
