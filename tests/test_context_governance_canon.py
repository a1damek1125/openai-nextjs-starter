"""TOOL-B10 canon: deterministic canonical JSON, SHA-256, Merkle forest."""
from tools.context_governance import canon


def test_canonical_json_is_sorted_compact_and_unicode():
    s = canon.canonical_json({"b": 1, "a": "ź"})
    assert s == '{"a":"ź","b":1}'


def test_canonical_json_rejects_nan():
    import math
    try:
        canon.canonical_json({"x": math.nan})
        assert False, "NaN must be rejected"
    except ValueError:
        pass


def test_hash_obj_is_stable_and_order_independent():
    a = canon.hash_obj({"x": 1, "y": 2})
    b = canon.hash_obj({"y": 2, "x": 1})
    assert a == b and len(a) == 64


def test_strip_volatile_removes_presentation_keys():
    core = canon.strip_volatile({"id": 1, "created_at": "t", "label": "hi",
                                 "nested": {"observed_at": "t2", "keep": 3}})
    assert core == {"id": 1, "nested": {"keep": 3}}


def test_core_hash_ignores_volatile():
    h1 = canon.core_hash({"id": 1, "created_at": "a"})
    h2 = canon.core_hash({"id": 1, "created_at": "b"})
    assert h1 == h2


def test_merkle_root_empty_is_sentinel():
    assert canon.merkle_root([]) == canon.sha256_hex("EMPTY_MERKLE")


def test_merkle_root_changes_with_any_leaf():
    base = canon.merkle_root(["a", "b", "c"])
    assert base != canon.merkle_root(["a", "b", "d"])
    assert base != canon.merkle_root(["a", "b"])


def test_class_root_is_order_independent():
    assert canon.class_root(["a", "b", "c"]) == canon.class_root(["c", "a", "b"])


def test_global_root_binds_all_classes():
    r1 = canon.global_root({"A": "x", "B": "y"})
    r2 = canon.global_root({"A": "x", "B": "z"})
    assert r1 != r2


def test_content_address_and_commitment_are_deterministic():
    assert canon.content_address("abc") == canon.content_address("abc")
    assert canon.content_address("abc") != canon.content_address("abd")
    assert canon.commitment("s").startswith(canon.commitment("s")[:10])
    assert canon.commitment("s") != canon.commitment("t")


def test_commitment_does_not_reveal_secret():
    c = canon.commitment("top-secret")
    assert "top-secret" not in c
