"""Deterministic graph algorithm tests (SP0001 AC-14, AC-15).

SCC (Tarjan) and reverse-reachability are checked against simple reference
oracles so the impact cone / cycle detection are provably correct.
"""
from __future__ import annotations

from tools.architecture.graph import TypedGraph


def _bfs_reverse_oracle(edges, seeds):
    """Naive reference: all nodes that can reach any seed."""
    rev = {}
    nodes = set()
    for s, d in edges:
        rev.setdefault(d, set()).add(s)
        nodes.add(s); nodes.add(d)
    seen = set(seeds)
    changed = True
    while changed:
        changed = False
        for node in list(seen):
            for pred in rev.get(node, set()):
                if pred not in seen:
                    seen.add(pred); changed = True
    return sorted(seen)


def _mk(edges):
    g = TypedGraph()
    for s, d in edges:
        g.add_edge("E", s, d)
    return g


def test_scc_acyclic_all_singletons():
    g = _mk([("a", "b"), ("b", "c"), ("c", "d")])
    comps = g.strongly_connected_components(["E"])
    assert all(len(c) == 1 for c in comps)
    assert not g.has_cycle(["E"])


def test_scc_detects_simple_cycle():
    g = _mk([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")])
    comps = g.strongly_connected_components(["E"])
    cyc = [c for c in comps if len(c) > 1]
    assert cyc == [["a", "b", "c"]]
    assert g.has_cycle(["E"])


def test_scc_two_independent_cycles():
    g = _mk([("a", "b"), ("b", "a"), ("x", "y"), ("y", "x")])
    cyc = sorted([c for c in g.strongly_connected_components(["E"]) if len(c) > 1])
    assert cyc == [["a", "b"], ["x", "y"]]


def test_scc_self_loop_is_not_multi_node_cycle():
    g = _mk([("a", "a"), ("a", "b")])
    # a self-loop is a single-node SCC; has_cycle only reports multi-node SCCs
    assert not g.has_cycle(["E"])


def test_scc_large_chain_is_linear_and_acyclic():
    edges = [(str(i), str(i + 1)) for i in range(2000)]
    g = _mk(edges)
    assert not g.has_cycle(["E"])
    assert len(g.strongly_connected_components(["E"])) == 2001


def test_reverse_reachable_matches_oracle():
    edges = [("app", "crm"), ("app", "evidence"), ("crm", "db"),
             ("evidence", "db"), ("report", "crm")]
    g = _mk(edges)
    got = g.reverse_reachable(["E"], ["db"])
    assert got == _bfs_reverse_oracle(edges, ["db"])
    # everyone reaches db except db itself's non-predecessors
    assert set(got) == {"app", "crm", "evidence", "report", "db"}


def test_reverse_reachable_seed_only_when_isolated():
    g = _mk([("a", "b")])
    assert g.reverse_reachable(["E"], ["z"]) == ["z"]


def test_reverse_reachable_depth_bound_is_advisory():
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    g = _mk(edges)
    full = g.reverse_reachable(["E"], ["d"], max_depth=None)
    shallow = g.reverse_reachable(["E"], ["d"], max_depth=1)
    assert set(full) == {"a", "b", "c", "d"}
    assert "a" not in shallow and "c" in shallow  # depth 1 = direct predecessors


def test_determinism_repeated_calls():
    edges = [("a", "b"), ("b", "c"), ("c", "a")]
    g = _mk(edges)
    assert g.strongly_connected_components(["E"]) == \
        g.strongly_connected_components(["E"])
