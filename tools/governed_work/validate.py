"""Aggregate Governed-Work validation gate (SP0006 §11.1). Runs the static,
committed-artifact validations conjunctively; a hard finding (P0/P1) can never be
offset by a score (§11.7). The Report is valid only with zero P0 and zero P1.

Runtime-only checkers (drift TOCTOU, cancellation barrier progression, approval-
context revalidation against a live action, bounded model checking) operate on
runtime inputs and are exercised by the CLI / tests, not the static gate.
"""
from __future__ import annotations

from .model import Report
from .intent import validate_candidate_intent
from .workorder import validate_work_order
from .identity import validate_registry
from .delegation import validate_delegation
from .lease import validate_lease, validate_child_lease
from .budget import conservation_findings
from .approval import validate_token  # noqa: F401 (runtime; structural below)
from .outcome import (validate_outcome_contract, defeater_findings,
                      dispute_findings, artifact_vs_outcome_findings)
from .recurrence import validate_contract as validate_recurrence_contract
from .accountability import conservation_findings as accountability_findings
from .envelope import validate_envelope
from .projections import validate_projection


def validate_all(program: dict) -> Report:
    rep = Report()

    for ci in program.get("candidate_intents", []):
        rep.extend(validate_candidate_intent(ci))

    work_by_id = {w.get("work_order_id"): w
                  for w in program.get("work_orders", [])}
    for w in program.get("work_orders", []):
        rep.extend(validate_work_order(w))
        rep.extend(artifact_vs_outcome_findings(w))

    identities = program.get("execution_identities") or program.get("identities", [])
    if identities:
        rep.extend(validate_registry(identities))

    leases_by_id = {l.get("lease_id"): l for l in program.get("leases", [])}
    for l in program.get("leases", []):
        rep.extend(validate_lease(l))
        pid = l.get("parent_lease_id")
        if pid and pid in leases_by_id:
            rep.extend(validate_child_lease(leases_by_id[pid], l))

    edges = program.get("delegation_edges", [])
    if edges:
        # group edges by work order for delegation validation
        by_wo: dict = {}
        for e in edges:
            by_wo.setdefault(e.get("work_order_id"), []).append(e)
        for wid, wedges in by_wo.items():
            w = work_by_id.get(wid, {"work_order_id": wid,
                                     "capability_ceiling": {}})
            rep.extend(validate_delegation(w, wedges, identities, leases_by_id))
            rep.extend(accountability_findings(w, wedges))

    for ledger in program.get("budget_ledgers", []):
        rep.extend(conservation_findings(ledger))

    for oc in program.get("outcome_contracts", []):
        rep.extend(validate_outcome_contract(oc))
    rep.extend(defeater_findings(program.get("outcome_defeaters", [])))
    rep.extend(dispute_findings(program.get("outcome_disputes", [])))

    for rc in program.get("recurring_contracts", []):
        rep.extend(validate_recurrence_contract(rc))

    for env in program.get("proof_envelopes", []):
        rep.extend(validate_envelope(env))

    # external authorization projections are transport/evidence, never authority
    # (INV-0006-45); a committed projection that claims authority is rejected
    for proj in program.get("projections", []):
        rep.extend(validate_projection(proj))

    rep.metrics.update({
        "work_orders": len(program.get("work_orders", [])),
        "candidate_intents": len(program.get("candidate_intents", [])),
        "execution_identities": len(identities),
        "delegation_edges": len(edges),
        "leases": len(program.get("leases", [])),
        "budget_ledgers": len(program.get("budget_ledgers", [])),
        "approval_tokens": len(program.get("approval_tokens", [])),
        "outcome_contracts": len(program.get("outcome_contracts", [])),
        "recurring_contracts": len(program.get("recurring_contracts", [])),
    })
    return rep
