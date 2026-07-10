"""TOOL-B9.2 v5: Context Continuity Capsule (section 9) + Company Memory Snapshot
Provenance (section 10).

The context capsule reconstructs *which* task/surface the work belonged to (it is
not an authority); a task mismatch or an expired context degrades the run. The
memory snapshot binds the EXACT versions of every company-memory fact retrieved,
distinguishing merely-retrieved from actually-influential facts. It stores no
full content and no chain of thought. Disputed-critical, expired, revoked or
provenance-unknown memory prevents the outcome from being PROVEN. Derived
evidence only: neither capsule grants authority.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _ctx(**over):
    return k.prepare(**over)["context_capsule"]


def _mem(**over):
    return k.prepare(**over)["memory_snapshot"]


def _degrades(over, expected_signal, expected_truth):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert o["work_outcome_truth_state"] == expected_truth
    assert expected_signal in o["all_signals"]
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- context capsule: kernel layer -----------------------------------------
def test_ctxmem_context_clean_valid():
    cc = _ctx()
    assert cc["context_status"] == "VALID"
    assert cc["signal"] is None


def test_ctxmem_context_is_not_authority():
    cc = _ctx()
    assert cc["context_is_authority"] is False


def test_ctxmem_context_task_mismatch_partial():
    o = _degrades({"context_task_mismatch": True}, "CONTEXT_TASK_MISMATCH",
                  "PARTIAL")
    assert o["context_capsule"]["context_status"] != "VALID"


def test_ctxmem_context_expired_stale():
    o = _degrades({"context_expired": True}, "CONTEXT_EXPIRED", "STALE")
    assert o["context_capsule"]["signal"] == "CONTEXT_EXPIRED"


def test_ctxmem_context_hash_recompute():
    cc = _ctx()
    assert _core_hash(cc, "context_capsule_hash", "signal") == \
        cc["context_capsule_hash"]


def test_ctxmem_context_hash_changes_on_degradation():
    assert _ctx()["context_capsule_hash"] != \
        _ctx(context_task_mismatch=True)["context_capsule_hash"]


# --- memory snapshot: kernel layer -----------------------------------------
def test_ctxmem_memory_clean_snapshot_valid():
    ms = _mem()
    assert ms["snapshot_status"] == "VALID"
    assert ms["memory_freshness_status"] == "FRESH"
    assert ms["signal"] is None


def test_ctxmem_memory_exact_versions_bound():
    ms = _mem(memory_facts=[{"id": "m1", "trust": "SYSTEM_DERIVED",
                             "version": "v9", "used": True},
                            {"id": "m2", "trust": "SYSTEM_DERIVED",
                             "version": "v3", "used": True}])
    assert ms["retrieved_memory_versions"] == {"m1": "v9", "m2": "v3"}


def test_ctxmem_memory_unused_retrieved_not_influential():
    # A retrieved-but-unused fact must NOT be claimed to have influenced the
    # outcome: it appears in retrieved refs but not in influential refs.
    ms = _mem(memory_facts=[{"id": "used1", "trust": "SYSTEM_DERIVED",
                             "used": True},
                            {"id": "seen1", "trust": "SYSTEM_DERIVED",
                             "used": False}])
    assert "seen1" in ms["retrieved_memory_refs"]
    assert "used1" in ms["retrieved_memory_refs"]
    assert "seen1" not in ms["influential_memory_refs"]
    assert "used1" in ms["influential_memory_refs"]


def test_ctxmem_memory_disputed_critical_not_proven():
    o = _degrades({"memory_facts": [{"id": "m", "trust": "DISPUTED",
                                     "critical": True, "used": True}]},
                  "MEMORY_CRITICAL_FACT_DISPUTED", "PARTIAL")
    assert o["work_outcome_truth_state"] != "PROVEN"
    assert o["memory_snapshot"]["memory_conflict_status"] == "CONFLICT"


def test_ctxmem_memory_expired_stale():
    o = _degrades({"memory_facts": [{"id": "m", "trust": "EXPIRED"}]},
                  "MEMORY_FACT_EXPIRED", "STALE")
    ms = o["memory_snapshot"]
    assert ms["memory_freshness_status"] == "STALE"
    assert ms["memory_expiry_status"] == "EXPIRED"


def test_ctxmem_memory_revoked_rejected():
    o = _degrades({"memory_facts": [{"id": "m", "trust": "REVOKED"}]},
                  "MEMORY_FACT_REVOKED", "REVOKED")
    assert o["work_run_state"] == "REJECTED"


def test_ctxmem_memory_provenance_unknown():
    o = _degrades({"memory_provenance_unknown": True},
                  "MEMORY_PROVENANCE_UNKNOWN", "UNKNOWN")
    assert o["memory_snapshot"]["signal"] == "MEMORY_PROVENANCE_UNKNOWN"


def test_ctxmem_memory_stores_no_content_or_chain_of_thought():
    ms = _mem(memory_facts=[{"id": "m", "trust": "SYSTEM_DERIVED",
                             "used": True, "content": "secretish"}])
    assert ms["stores_full_content"] is False
    assert ms["stores_chain_of_thought"] is False


def test_ctxmem_memory_snapshot_immutable():
    assert _mem()["snapshot_immutable"] is True


def test_ctxmem_memory_trust_classes_from_constant():
    # Every trust class the snapshot reports is drawn from the declared set.
    ms = _mem(memory_facts=[{"id": "a", "trust": "VERIFIED_CANONICAL",
                             "used": True},
                            {"id": "b", "trust": "AI_SUGGESTED", "used": True}])
    for tc in ms["memory_trust_classes"]:
        assert tc in wo.MEMORY_TRUST_CLASSES


def test_ctxmem_memory_snapshot_hash_recompute():
    ms = _mem()
    assert _core_hash(ms, "snapshot_hash", "signal") == ms["snapshot_hash"]


def test_ctxmem_memory_hash_changes_on_degradation():
    assert _mem()["snapshot_hash"] != \
        _mem(memory_facts=[{"id": "m", "trust": "REVOKED"}])["snapshot_hash"]


def test_ctxmem_grants_no_authority():
    o = k.clean_outcome()
    assert o["is_authority"] is False
    assert o["context_capsule"]["context_is_authority"] is False


# --- API layer -------------------------------------------------------------
def test_ctxmem_api_context_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "context")
    assert r.status_code == 200
    cc = r.json()["context_capsule"]
    assert cc["context_status"] == "VALID"
    assert cc["context_is_authority"] is False


def test_ctxmem_api_memory_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "memory")
    assert r.status_code == 200
    ms = r.json()["memory_snapshot"]
    assert ms["snapshot_status"] == "VALID"
    assert ms["stores_chain_of_thought"] is False
    assert ms["snapshot_immutable"] is True
