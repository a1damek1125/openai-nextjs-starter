"""Checkpointed Backfill + Lease + Barrier (SP0007 §11.7, D-0007-48/49/50,
AC-0007-158..165).

Deterministic in-memory reference implementation — no real database, no
external effect (INV-0007-47). Backfill proceeds in deterministic sorted
batches; every batch seals a checkpoint {index, source_hash, target_hash,
committed_ids} (D-0007-48). Batches are IDEMPOTENT: re-running a committed
batch never duplicates (INV-0007-39); resume after restart continues past the
latest verified checkpoint. A failing item is quarantined without poisoning
its batch. Exactly one owner may hold the migration lease per protected scope
(D-0007-49, AC-0007-163/164); an active barrier blocks incompatible concurrent
writes to its scope (D-0007-50, AC-0007-165). Conservation always holds:
processed + pending + failed == total.
"""
from __future__ import annotations

from .model import (Finding, P0, BACKFILL_CHECKPOINT_INVALID,
                    MIGRATION_CONCURRENCY_CONFLICT, INVALID_COMPAT_SCHEMA)
from .canon import core_hash, canonical_json


def _item_id(item):
    if isinstance(item, dict):
        return item.get("id", item.get("record_id"))
    return item


def _sort_key(item) -> str:
    return canonical_json(_item_id(item))


def committed_ids(state: dict) -> set:
    """Union of ids sealed into checkpoints — the idempotency witness."""
    out: set = set()
    for cp in state.get("checkpoints", []):
        out.update(cp.get("committed_ids", []))
    return out


def new_backfill(total_items: list, *, batch_size: int) -> dict:
    """Fresh backfill state: pending in deterministic sorted order, nothing
    processed, no checkpoints (D-0007-48)."""
    return {"pending": sorted(list(total_items), key=_sort_key),
            "processed": [], "failed": [], "checkpoints": [],
            "quarantined": [], "batch_size": int(batch_size),
            "total": len(total_items)}


def run_batch(state: dict, transform) -> dict:
    """Take the next deterministic batch, transform item-by-item (a failing
    item goes to failed+quarantined — batch isolation), commit, and seal a
    checkpoint. IDEMPOTENT: a batch matching the last sealed checkpoint's
    source_hash, or ids already committed, is never re-applied (INV-0007-39).
    Returns a new state; the input state is not mutated."""
    new = {"pending": list(state.get("pending", [])),
           "processed": list(state.get("processed", [])),
           "failed": list(state.get("failed", [])),
           "checkpoints": list(state.get("checkpoints", [])),
           "quarantined": list(state.get("quarantined", [])),
           "batch_size": state.get("batch_size", 1),
           "total": state.get("total",
                              len(state.get("pending", []))
                              + len(state.get("processed", []))
                              + len(state.get("failed", [])))}
    if not new["pending"]:
        return new
    size = max(1, int(new["batch_size"]))
    batch = sorted(new["pending"], key=_sort_key)[:size]
    source_hash = core_hash(batch)

    # idempotency guard 1: identical to the last sealed checkpoint
    if new["checkpoints"] and \
            new["checkpoints"][-1].get("source_hash") == source_hash:
        batch_ids = {_item_id(i) for i in batch}
        new["pending"] = [i for i in new["pending"]
                          if _item_id(i) not in batch_ids]
        return new

    already = committed_ids(new)
    committed_now: list = []
    targets: list = []
    consumed_ids: set = set()
    for item in batch:
        iid = _item_id(item)
        consumed_ids.add(iid)
        # idempotency guard 2: never re-commit an already-committed id
        if iid in already:
            continue
        try:
            result = transform(item)
        except Exception as exc:
            failed = {"id": iid, "item": item, "error": repr(exc)}
            new["failed"].append(failed)
            new["quarantined"].append(failed)
            continue
        new["processed"].append(result)
        targets.append(result)
        committed_now.append(iid)

    new["pending"] = [i for i in new["pending"]
                      if _item_id(i) not in consumed_ids]
    if committed_now:
        new["checkpoints"].append({
            "index": len(new["checkpoints"]),
            "source_hash": source_hash,
            "target_hash": core_hash(targets),
            "committed_ids": committed_now,
        })
    return new


def resume(state: dict) -> dict:
    """Resume after restart: continue after the latest sealed checkpoint —
    committed and failed ids are never reprocessed (D-0007-48,
    AC-0007-160)."""
    done = committed_ids(state)
    failed_ids = {_item_id(f.get("item", f)) if isinstance(f, dict) else f
                  for f in state.get("failed", [])}
    new = dict(state)
    new["pending"] = sorted(
        [i for i in state.get("pending", [])
         if _item_id(i) not in done and _item_id(i) not in failed_ids],
        key=_sort_key)
    return new


def checkpoint_findings(state: dict) -> list[Finding]:
    """Recompute each checkpoint's target hash from the processed records it
    committed — a mismatch is BACKFILL_CHECKPOINT_INVALID (P0). Also enforce
    conservation: processed + pending + failed == total (§12.7)."""
    out: list[Finding] = []
    processed_by_id = {_item_id(p): p for p in state.get("processed", [])}
    for cp in state.get("checkpoints", []):
        idx = cp.get("index", "-")
        targets = []
        missing = False
        for iid in cp.get("committed_ids", []):
            if iid not in processed_by_id:
                missing = True
                break
            targets.append(processed_by_id[iid])
        if missing or core_hash(targets) != cp.get("target_hash"):
            out.append(Finding(BACKFILL_CHECKPOINT_INVALID, P0,
                               f"checkpoint:{idx}",
                               f"checkpoint {idx} target hash does not match "
                               "recomputed hash of its committed records "
                               "(D-0007-48)",
                               {"index": idx,
                                "sealed": cp.get("target_hash")}))
    total = state.get("total", 0)
    accounted = (len(state.get("processed", []))
                 + len(state.get("pending", []))
                 + len(state.get("failed", [])))
    if accounted != total:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P0, "backfill",
                           "migration progress conservation violated",
                           {"accounted": accounted, "total": total}))
    return out


def duplicate_findings(state: dict, batch_ids: list) -> list[Finding]:
    """Attempting to commit already-committed ids is a P0 duplicate-batch
    finding (INV-0007-39) — idempotency is proven, not assumed."""
    dups = sorted({str(i) for i in batch_ids} &
                  {str(i) for i in committed_ids(state)})
    if not dups:
        return []
    return [Finding(BACKFILL_CHECKPOINT_INVALID, P0, "backfill",
                    "duplicate batch commit attempted for already-committed "
                    f"ids {dups} (INV-0007-39)", {"duplicate_ids": dups})]


def acquire_lease(leases: dict, scope: str, owner: str):
    """One owner per protected scope (D-0007-49). A second distinct owner is
    MIGRATION_CONCURRENCY_CONFLICT (P0) and acquires nothing
    (AC-0007-163/164); re-acquisition by the same owner is idempotent."""
    holder = leases.get(scope)
    if holder is not None and holder != owner:
        return leases, [Finding(MIGRATION_CONCURRENCY_CONFLICT, P0, scope,
                                f"lease on scope {scope!r} held by "
                                f"{holder!r}; second owner {owner!r} denied "
                                "(D-0007-49)",
                                {"holder": holder, "requestor": owner})]
    new = dict(leases)
    new[scope] = owner
    return new, []


def barrier_findings(barrier: dict, write_attempt: dict) -> list[Finding]:
    """An active barrier blocks incompatible concurrent writes to its scope
    (D-0007-50, AC-0007-165). Fail-closed: only writes explicitly marked
    compatible=True pass."""
    if not barrier.get("active"):
        return []
    if write_attempt.get("scope") != barrier.get("scope"):
        return []
    if write_attempt.get("compatible") is True:
        return []
    scope = barrier.get("scope", "-")
    return [Finding(MIGRATION_CONCURRENCY_CONFLICT, P0, str(scope),
                    f"write to scope {scope!r} blocked by active migration "
                    "barrier — incompatible concurrent write (D-0007-50)",
                    {"writer": write_attempt.get("writer"),
                     "scope": scope})]
