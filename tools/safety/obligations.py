"""Safety Proof Obligations (SP0005 §10.5, D-0005-11/12, §11.3, INV-0005-09).

For an action in a context, a set of mandatory proof obligations is generated;
admission requires ALL mandatory obligations SATISFIED before an ordinary ALLOW.
An UNKNOWN obligation can NEVER become SATISFIED (D-0005-12, AC-0005-032) — it is
not low risk (INV-0005-09).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, OBLIGATION_TYPES, OBLIGATION_STATUS,
                    PROOF_OBLIGATION_UNKNOWN, PROOF_OBLIGATION_FAILED,
                    INVALID_SAFETY_SCHEMA)


def validate_obligation(o: dict) -> list[Finding]:
    out: list[Finding] = []
    oid = o.get("obligation_id", "-")
    if o.get("obligation_type") not in OBLIGATION_TYPES:
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, oid,
                           f"invalid obligation_type {o.get('obligation_type')!r}",
                           {}))
    if o.get("status", "UNKNOWN") not in OBLIGATION_STATUS:
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, oid,
                           f"invalid obligation status {o.get('status')!r}", {}))
    return out


def closure(obligations: list[dict], *, mandatory: set[str] | None = None
            ) -> tuple[bool, list[Finding]]:
    """Return (all_mandatory_satisfied, findings). A mandatory obligation that is
    UNKNOWN/STALE → PROOF_OBLIGATION_UNKNOWN (P0); UNSATISFIED → FAILED (P0). Only
    SATISFIED or NOT_APPLICABLE clears a mandatory obligation."""
    out: list[Finding] = []
    ok = True
    # Fold duplicate obligation_types by WORST status so a same-type SATISFIED
    # entry can never mask an UNKNOWN/STALE/UNSATISFIED one (SWARM-N E4). Higher
    # rank = worse; the worst status per type governs closure.
    _rank = {"SATISFIED": 0, "NOT_APPLICABLE": 0, "UNSATISFIED": 1,
             "STALE": 2, "UNKNOWN": 3}
    by_type: dict[str, str] = {}
    for o in obligations:
        t = o.get("obligation_type")
        st = o.get("status", "UNKNOWN")
        cur = by_type.get(t)
        if cur is None or _rank.get(st, 3) > _rank.get(cur, 3):
            by_type[t] = st
    required = mandatory if mandatory is not None else {
        o["obligation_type"] for o in obligations if o.get("mandatory", True)}
    for t in sorted(required):
        st = by_type.get(t, "UNKNOWN")
        if st == "SATISFIED" or st == "NOT_APPLICABLE":
            continue
        ok = False
        if st in ("UNKNOWN", "STALE"):
            out.append(Finding(PROOF_OBLIGATION_UNKNOWN, P0, t,
                               f"mandatory proof obligation {t} is {st} — cannot "
                               "be treated as satisfied (INV-0005-09)", {}))
        else:  # UNSATISFIED
            out.append(Finding(PROOF_OBLIGATION_FAILED, P0, t,
                               f"mandatory proof obligation {t} is {st}", {}))
    return ok, out


def generate_mandatory(action_contract: dict) -> set[str]:
    """The mandatory proof-obligation types for an action contract."""
    out = set()
    for po in action_contract.get("proof_obligations", []):
        if isinstance(po, str):
            out.add(po)
        elif po.get("mandatory", True):
            out.add(po.get("obligation_type"))
    return out
