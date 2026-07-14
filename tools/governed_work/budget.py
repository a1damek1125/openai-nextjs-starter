"""Budget Vector + Reservation Ledger + Conservation Laws (SP0006 §9.7, §11.6,
D-0006-23..26, INV-0006-18/19).

A budget is a vector over additive dimensions (financial cost, model cost, tool-
call quota, external-effect quota, data-access quota, resource capacity) plus the
non-additive dimensions handled specially: risk (see ``risk.py``) and deadline
(time). The reservation ledger is DETERMINISTIC and IDEMPOTENT and holds NO
external state: a reserve retried with the same idempotency key returns the same
reservation and never double-allocates (INV-0006-18). Conservation is invariant:
per additive dimension ``available + reserved + consumed == total`` at all times,
so ``consumed + reserved <= total`` can never be breached (BUDGET_CONSERVATION_
FAILURE, P0). Child allocations may never in sum exceed the parent's available
budget (D-0006-25), and a child deadline may never exceed the parent's (D-0006-26).

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, BUDGET_DIMENSIONS, BUDGET_OVERCOMMITMENT,
                    BUDGET_CONSERVATION_FAILURE, INVALID_WORK_SCHEMA)
from .canon import sha256_hex, canonical_json


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
        else None


def new_ledger(budget_vector: dict) -> dict:
    """Build a fresh reservation ledger from a budget vector. For each additive
    dimension track total / available / reserved / consumed / released / expired
    / reconciled; ``available`` starts at ``total`` and every other counter at 0
    (D-0006-23)."""
    bv = budget_vector or {}
    dims: dict[str, dict] = {}
    for d in BUDGET_DIMENSIONS:
        total = _num(bv.get(d, 0)) or 0.0
        dims[d] = {"total": total, "available": total, "reserved": 0.0,
                   "consumed": 0.0, "released": 0.0, "expired": 0.0,
                   "reconciled": 0.0}
    return {"dimensions": dims, "reservations": {}, "idempotency": {}}


def _reservation_id(idempotency_key: str, dimension: str) -> str:
    """Deterministic reservation id derived from the idempotency key so retries
    map to the same reservation without any external state."""
    return "resv:" + sha256_hex(canonical_json(
        {"k": idempotency_key, "d": dimension}))[:24]


def reserve(ledger: dict, dimension: str, amount, *, idempotency_key: str,
            subject_identity: str, reservation_id: str | None = None):
    """Reserve ``amount`` of an additive ``dimension``. Idempotent on
    ``idempotency_key``: a duplicate call returns the SAME reservation and does
    not re-allocate. Over-reservation (amount > available) yields a
    BUDGET_OVERCOMMITMENT finding and does NOT mutate the ledger. Returns
    ``(ledger, result)`` where result carries ``status``, ``reservation`` and
    ``findings``."""
    # idempotent replay -------------------------------------------------------
    prior = ledger["idempotency"].get(idempotency_key)
    if prior is not None:
        return ledger, {"status": "IDEMPOTENT_REPLAY",
                        "reservation": ledger["reservations"][prior],
                        "findings": []}

    dim = ledger["dimensions"].get(dimension)
    if dim is None:
        f = Finding(INVALID_WORK_SCHEMA, P1, subject_identity,
                    f"unknown additive budget dimension {dimension!r}",
                    {"dimension": dimension})
        return ledger, {"status": "INVALID", "reservation": None,
                        "findings": [f]}

    amt = _num(amount)
    if amt is None or amt < 0:
        f = Finding(INVALID_WORK_SCHEMA, P1, subject_identity,
                    f"reservation amount must be a non-negative number, "
                    f"got {amount!r}", {"dimension": dimension})
        return ledger, {"status": "INVALID", "reservation": None,
                        "findings": [f]}

    if amt > dim["available"]:
        f = Finding(BUDGET_OVERCOMMITMENT, P1, subject_identity,
                    f"reservation of {amt} on {dimension} exceeds available "
                    f"{dim['available']} (INV-0006-18)",
                    {"dimension": dimension, "requested": amt,
                     "available": dim["available"]})
        return ledger, {"status": "OVERCOMMITMENT", "reservation": None,
                        "findings": [f]}

    rid = reservation_id or _reservation_id(idempotency_key, dimension)
    reservation = {"reservation_id": rid, "dimension": dimension,
                   "amount": amt, "consumed": 0.0,
                   "subject_identity": subject_identity,
                   "idempotency_key": idempotency_key, "state": "RESERVED"}
    dim["available"] -= amt
    dim["reserved"] += amt
    ledger["reservations"][rid] = reservation
    ledger["idempotency"][idempotency_key] = rid
    return ledger, {"status": "RESERVED", "reservation": reservation,
                    "findings": []}


def consume(ledger: dict, reservation_id: str, amount):
    """Consume (up to) ``amount`` of a reservation, moving budget reserved ->
    consumed. Idempotent: consuming the same cumulative amount twice is a no-op;
    consumption is capped at the reserved amount. Returns ``(ledger, result)``."""
    r = ledger["reservations"].get(reservation_id)
    if r is None:
        return ledger, {"status": "UNKNOWN_RESERVATION", "reservation": None,
                        "findings": [Finding(INVALID_WORK_SCHEMA, P1,
                                             reservation_id,
                                             "unknown reservation", {})]}
    if r["state"] in ("RELEASED", "EXPIRED"):
        return ledger, {"status": r["state"], "reservation": r, "findings": []}

    amt = _num(amount) or 0.0
    target = min(max(amt, 0.0), r["amount"])   # cap at the reserved amount
    delta = target - r["consumed"]             # idempotent: replay -> delta 0
    if delta > 0:
        dim = ledger["dimensions"][r["dimension"]]
        dim["reserved"] -= delta
        dim["consumed"] += delta
        r["consumed"] = target
        r["state"] = "CONSUMED" if target >= r["amount"] else "RESERVED"
    return ledger, {"status": r["state"], "reservation": r, "findings": []}


def release(ledger: dict, reservation_id: str):
    """Release the unconsumed remainder of a reservation, returning reserved ->
    available. Idempotent: a second release is a no-op. Returns ``(ledger,
    result)``."""
    r = ledger["reservations"].get(reservation_id)
    if r is None:
        return ledger, {"status": "UNKNOWN_RESERVATION", "reservation": None,
                        "findings": [Finding(INVALID_WORK_SCHEMA, P1,
                                             reservation_id,
                                             "unknown reservation", {})]}
    if r["state"] == "RELEASED":
        return ledger, {"status": "RELEASED", "reservation": r, "findings": []}
    remainder = r["amount"] - r["consumed"]
    if remainder > 0:
        dim = ledger["dimensions"][r["dimension"]]
        dim["reserved"] -= remainder
        dim["available"] += remainder
        dim["released"] += remainder
    r["state"] = "RELEASED"
    return ledger, {"status": "RELEASED", "reservation": r, "findings": []}


def conservation_findings(ledger: dict) -> list[Finding]:
    """Assert the ledger conservation law per additive dimension: consumed +
    reserved <= total and available >= 0 (INV-0006-19). Any breach is a
    BUDGET_CONSERVATION_FAILURE (P0)."""
    out: list[Finding] = []
    for d, s in ledger["dimensions"].items():
        if s["consumed"] + s["reserved"] > s["total"] + 1e-9:
            out.append(Finding(BUDGET_CONSERVATION_FAILURE, P0, d,
                               f"consumed+reserved {s['consumed'] + s['reserved']}"
                               f" exceeds total {s['total']} on {d}",
                               {"dimension": d, **s}))
        if s["available"] < -1e-9:
            out.append(Finding(BUDGET_CONSERVATION_FAILURE, P0, d,
                               f"available budget negative ({s['available']}) "
                               f"on {d}", {"dimension": d, **s}))
    return out


def parent_child_conservation(parent_available: dict,
                              child_allocations: list[dict]) -> list[Finding]:
    """Sum of child allocations per additive dimension must not exceed the
    parent's available budget for that dimension (D-0006-25). Each child entry is
    a dimension->amount mapping (optionally nested under ``allocation``). Emits
    BUDGET_CONSERVATION_FAILURE (P0) per over-allocated dimension."""
    out: list[Finding] = []
    parent_available = parent_available or {}
    for d in BUDGET_DIMENSIONS:
        avail = _num(parent_available.get(d, 0)) or 0.0
        total = 0.0
        for child in child_allocations or []:
            alloc = child.get("allocation", child) if isinstance(child, dict) \
                else {}
            total += _num(alloc.get(d, 0)) or 0.0
        if total > avail + 1e-9:
            out.append(Finding(BUDGET_CONSERVATION_FAILURE, P0, d,
                               f"child allocations sum {total} exceed parent "
                               f"available {avail} on {d} (D-0006-25)",
                               {"dimension": d, "allocated": total,
                                "available": avail}))
    return out


def time_conservation(parent_deadline, child_deadlines, *,
                      parallel: bool = True) -> list[Finding]:
    """Deadline (non-additive) conservation (D-0006-26): no child deadline may
    exceed the parent deadline. When work runs in ``parallel`` (the default) the
    summed child durations are NOT required to fit within the parent's elapsed
    time — only the per-child deadline bound applies. Emits BUDGET_CONSERVATION_
    FAILURE (P0) for each child deadline past the parent's."""
    out: list[Finding] = []
    if parent_deadline is None:
        return out
    for i, cd in enumerate(child_deadlines or []):
        if cd is not None and cd > parent_deadline:
            out.append(Finding(BUDGET_CONSERVATION_FAILURE, P0, f"child[{i}]",
                               f"child deadline {cd} exceeds parent deadline "
                               f"{parent_deadline} (D-0006-26)",
                               {"child_index": i, "child_deadline": cd,
                                "parent_deadline": parent_deadline,
                                "parallel": parallel}))
    return out
