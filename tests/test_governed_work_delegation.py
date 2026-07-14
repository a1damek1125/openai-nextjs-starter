"""FINALIS SP0006 — Governed Work, Delegated Autonomy & Outcome Accountability.

Covers AC-0006-051..080: execution identity, delegation graph shape, capability
leases, structural attenuation / non-amplification, and revocation propagation.

Imports ONLY from ``tools.governed_work.*`` (governance tooling; no product
runtime). Each test is comment-mapped to the AC id(s) it exercises.
"""
from __future__ import annotations

from tools.governed_work import identity, lease, delegation
from tools.governed_work.model import (
    DELEGATION_CYCLE_DETECTED, DELEGATION_DEPTH_EXCEEDED,
    DELEGATION_FANOUT_EXCEEDED, DELEGATION_AUTHORITY_AMPLIFICATION,
    LEASE_ATTENUATION_FAILURE, LEASE_EXPIRED, LEASE_REVOKED,
    REVOCATION_PROPAGATION_STALE, INVALID_WORK_SCHEMA,
)

FAR = "2030-01-01T00:00:00Z"      # parent expiry
NEAR = "2029-01-01T00:00:00Z"     # earlier than parent (a proper narrowing)
BEYOND = "2031-01-01T00:00:00Z"   # later than parent (an illegal extension)


def _k(fs):
    """Set of finding kinds from a Finding list (or a Report)."""
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# --- fixtures / builders ----------------------------------------------------
def make_identity(iid, wo="WO", depth=0, parent=None, role="root"):
    idn = {"execution_identity_id": iid, "work_order_id": wo,
           "role": role, "delegation_depth": depth}
    if parent is not None:
        idn["parent_identity_id"] = parent
    return idn


def make_parent_lease(**over):
    """A valid, fully-bound parent capability lease (D-0006-18)."""
    l = {
        "lease_id": "L-root",
        "tenant_id": "T1",
        "work_order_id": "WO",
        "subject_identity": "id:parent",
        "purpose": "case_triage",
        "targets": ["t1", "t2", "t3"],
        "allowed_operations": ["read", "write", "delete"],
        "effect_classes": ["READ", "LOCAL_WRITE"],
        "data_classes": ["PUBLIC", "INTERNAL"],
        "risk_ceiling": {"operational": "LOW"},
        "cost_ceiling": {"financial_cost": 100},
        "expires_at": FAR,
        "maximum_uses": 10,
        "current_uses": 0,
        "revocation_state": "ACTIVE",
    }
    l.update(over)
    return l


def make_proper_child(parent=None, **over):
    """A structurally attenuated child derived via lease.attenuate."""
    parent = parent or make_parent_lease()
    narrow = {
        "lease_id": "L-child",
        "subject_identity": "id:child",
        "purpose": "case_triage",
        "targets": ["t1"],
        "allowed_operations": ["read"],
        "effect_classes": ["READ"],
        "data_classes": ["PUBLIC"],
        "expires_at": NEAR,
        "maximum_uses": 5,
    }
    narrow.update(over)
    return lease.attenuate(parent, narrow)


# === AC-0006-051 / 052 — execution identity schema ==========================
def test_execution_identity_valid_and_missing_parent():
    # AC-0006-051: a well-formed root execution identity validates cleanly.
    root = make_identity("id:root", depth=0)
    assert identity.validate_identity(root) == []

    # AC-0006-052: a non-root identity (delegation_depth >= 1) with NO
    # parent_identity_id is flagged (INV-0006-14).
    orphan = make_identity("id:sub", depth=1, role="subagent")  # no parent
    kinds = _k(identity.validate_identity(orphan))
    assert INVALID_WORK_SCHEMA in kinds
    msgs = " ".join(f.message for f in identity.validate_identity(orphan))
    assert "no parent" in msgs


def test_validate_registry_duplicate_and_work_order_mismatch():
    # AC-0006-051/052: registry flags duplicate ids AND a child whose work
    # order differs from its parent's (every identity belongs to exactly one
    # work order — INV-0006-14).
    parent = make_identity("P", wo="W1", depth=0)
    dup = make_identity("P", wo="W1", depth=0)                 # duplicate id
    child = make_identity("C", wo="W2", depth=1, parent="P",   # wrong WO
                          role="subagent")
    findings = identity.validate_registry([parent, dup, child])
    msgs = " ".join(f.message for f in findings)
    assert "duplicate execution_identity_id" in msgs
    assert "work_order differs from parent" in msgs
    assert _k(findings) == {INVALID_WORK_SCHEMA}


# === AC-0006-053 / 054 / 055 — delegation graph is a DAG ====================
def test_dag_has_no_cycle():
    # AC-0006-053/054: a proper parent->child->grandchild DAG has no authority
    # cycle.
    edges = [
        {"parent_identity": "A", "child_identity": "B"},
        {"parent_identity": "B", "child_identity": "C"},
    ]
    assert delegation.has_cycle(edges) is False
    assert delegation.find_cycle(edges) is None
    graph = delegation.build_graph(edges)
    assert graph["A"] == ["B"] and graph["B"] == ["C"]


def test_cycle_detected_is_p0():
    # AC-0006-055: an authority-bearing cycle (A->B, B->A) is detected and
    # validate_delegation emits DELEGATION_CYCLE_DETECTED at P0 (INV-0006-11).
    edges = [
        {"parent_identity": "A", "child_identity": "B"},
        {"parent_identity": "B", "child_identity": "A"},
    ]
    assert delegation.has_cycle(edges) is True
    assert delegation.find_cycle(edges) is not None

    idns = [make_identity("A"), make_identity("B")]
    wo = {"work_order_id": "WO"}
    findings = delegation.validate_delegation(wo, edges, idns, {})
    assert DELEGATION_CYCLE_DETECTED in _k(findings)
    cyc = [f for f in findings if f.kind == DELEGATION_CYCLE_DETECTED]
    assert cyc and cyc[0].severity == "P0"


# === AC-0006-056 / 057 / 058 — bounded delegation shape =====================
def test_delegation_depth_exceeded():
    # AC-0006-056: with capability_ceiling max_delegation_depth = 1, a chain of
    # depth 2 (A->B->C) exceeds the ceiling => DELEGATION_DEPTH_EXCEEDED.
    edges = [
        {"parent_identity": "A", "child_identity": "B"},
        {"parent_identity": "B", "child_identity": "C"},
    ]
    assert delegation.depth_of(edges, "C") == 2
    idns = [make_identity("A", depth=0),
            make_identity("B", depth=1, parent="A", role="subagent"),
            make_identity("C", depth=2, parent="B", role="subagent")]
    wo = {"work_order_id": "WO",
          "capability_ceiling": {"max_delegation_depth": 1}}
    findings = delegation.validate_delegation(wo, edges, idns, {})
    assert DELEGATION_DEPTH_EXCEEDED in _k(findings)


def test_delegation_fanout_exceeded():
    # AC-0006-057/058: direct fan-out of 3 beyond max_direct_fanout = 2 =>
    # DELEGATION_FANOUT_EXCEEDED on the parent node.
    edges = [
        {"parent_identity": "A", "child_identity": "B"},
        {"parent_identity": "A", "child_identity": "C"},
        {"parent_identity": "A", "child_identity": "D"},
    ]
    assert delegation.fanout_of(edges, "A") == 3
    assert delegation.descendant_count(edges, "A") == 3
    idns = [make_identity("A", depth=0),
            make_identity("B", depth=1, parent="A", role="subagent"),
            make_identity("C", depth=1, parent="A", role="subagent"),
            make_identity("D", depth=1, parent="A", role="subagent")]
    wo = {"work_order_id": "WO",
          "capability_ceiling": {"max_direct_fanout": 2}}
    findings = delegation.validate_delegation(wo, edges, idns, {})
    assert DELEGATION_FANOUT_EXCEEDED in _k(findings)


# === AC-0006-059..071 — capability lease binding, expiry, uses, revocation ==
def test_lease_binds_context_and_is_valid_when_active():
    # AC-0006-059..069: a lease binds tenant/work_order/subject/purpose/targets/
    # operations/effects/data and carries expiry + use-count.
    l = make_parent_lease()
    for f in ("tenant_id", "work_order_id", "subject_identity", "purpose",
              "targets", "allowed_operations", "effect_classes", "data_classes",
              "expires_at", "maximum_uses"):
        assert l.get(f) not in (None, "", [])
    # AC-0006-070: an ACTIVE, unexpired lease produces no hard finding.
    assert lease.validate_lease(l, now="2026-01-01T00:00:00Z") == []


def test_lease_revoked_and_expired():
    # AC-0006-071: leases are revocable and expiring.
    revoked = make_parent_lease(revocation_state="REVOKED")
    assert LEASE_REVOKED in _k(lease.validate_lease(revoked))

    active = make_parent_lease()
    # now is PAST expires_at => LEASE_EXPIRED.
    assert LEASE_EXPIRED in _k(lease.validate_lease(active, now=BEYOND))


# === AC-0006-072 — attenuation proof for a proper child =====================
def test_attenuation_proof_holds_for_proper_child():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    ok, reasons = lease.is_attenuation(parent, child)
    assert ok and reasons == []
    proof = lease.attenuation_proof(parent, child)
    assert proof["is_attenuated"] is True
    assert proof["parent_lease_id"] == "L-root"
    assert proof["child_lease_id"] == "L-child"
    assert delegation.non_amplification_holds(parent, child) is True
    # a proper child raises no attenuation finding.
    assert lease.validate_child_lease(parent, child) == []


# === AC-0006-073 — operation EXPANSION is amplification ======================
def test_child_operation_expansion_fails():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    child["allowed_operations"] = ["read", "admin"]  # "admin" not in parent
    kinds = _k(lease.validate_child_lease(parent, child))
    assert LEASE_ATTENUATION_FAILURE in kinds
    assert DELEGATION_AUTHORITY_AMPLIFICATION in kinds
    assert delegation.non_amplification_holds(parent, child) is False


# === AC-0006-074 — target EXPANSION fails ===================================
def test_child_target_expansion_fails():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    child["targets"] = ["t1", "t9"]  # t9 not granted to parent
    assert LEASE_ATTENUATION_FAILURE in _k(
        lease.validate_child_lease(parent, child))


# === AC-0006-075 — data-scope EXPANSION fails ===============================
def test_child_data_scope_expansion_fails():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    child["data_classes"] = ["PUBLIC", "SECRET"]  # SECRET not in parent
    assert LEASE_ATTENUATION_FAILURE in _k(
        lease.validate_child_lease(parent, child))


# === AC-0006-076 — expiry EXTENSION fails ===================================
def test_child_expiry_extension_fails():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    child["expires_at"] = BEYOND  # outlives parent
    findings = lease.validate_child_lease(parent, child)
    assert LEASE_ATTENUATION_FAILURE in _k(findings)
    _, reasons = lease.is_attenuation(parent, child)
    assert any("expiry" in r for r in reasons)


# === AC-0006-077 — use-count EXPANSION fails ================================
def test_child_use_count_expansion_fails():
    parent = make_parent_lease()
    child = make_proper_child(parent)
    child["maximum_uses"] = 20  # more uses than parent's 10
    findings = lease.validate_child_lease(parent, child)
    assert LEASE_ATTENUATION_FAILURE in _k(findings)
    _, reasons = lease.is_attenuation(parent, child)
    assert any("use count" in r for r in reasons)


# === AC-0006-078 — risk-ceiling EXPANSION fails =============================
def test_child_risk_ceiling_expansion_fails():
    parent = make_parent_lease()  # risk_ceiling operational LOW
    child = make_proper_child(parent)
    child["risk_ceiling"] = {"operational": "HIGH"}  # HIGH > LOW
    findings = lease.validate_child_lease(parent, child)
    assert LEASE_ATTENUATION_FAILURE in _k(findings)
    assert DELEGATION_AUTHORITY_AMPLIFICATION in _k(findings)


# === AC-0006-079 — parent revocation invalidates descendants ================
def test_revocation_invalidates_descendants_but_not_independent_root():
    root = make_parent_lease(lease_id="R", parent_lease_id=None)
    child_a = make_parent_lease(lease_id="A", parent_lease_id="R")
    grandchild = make_parent_lease(lease_id="G", parent_lease_id="A")
    # child_b holds its OWN independent root authority -> survives (D-0006-19).
    child_b = make_parent_lease(lease_id="B", parent_lease_id="R",
                                independent_root_authority=True)
    leases = [root, child_a, grandchild, child_b]

    result = lease.revoke_descendants(leases, "R")
    assert result["revoked"] == "R"
    inv = set(result["invalidated"])
    assert "A" in inv and "G" in inv       # descendants cascade-invalidated
    assert "B" not in inv                   # independent root survives


# === AC-0006-080 — revocation propagation staleness =========================
def test_revocation_propagation_stale():
    stale = {"revocation_id": "REV-1", "issued_seq": 10, "observed_seq": 25,
             "max_propagation_delay": 5}  # 15 > 5
    assert REVOCATION_PROPAGATION_STALE in _k(
        lease.revocation_staleness(stale))

    fresh = {"revocation_id": "REV-2", "issued_seq": 10, "observed_seq": 12,
             "max_propagation_delay": 5}  # 2 <= 5
    assert lease.revocation_staleness(fresh) == []
