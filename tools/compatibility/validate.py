"""Aggregate compatibility-program validation gate (SP0007 §11, D-0007-02).

Runs the static, committed-artifact validations conjunctively over the loaded
Compatibility Twin; a hard finding (P0/P1) can never be offset by any score. The
Report is valid only with zero P0 and zero P1. Runtime-only evaluators (diff of
two live contracts, replay of a candidate implementation, dual-read of two
readers, path selection) operate on runtime inputs and are exercised by the CLI
and tests, not the static gate.
"""
from __future__ import annotations

from .model import Report
from .contracts import validate_descriptor, validate_version
from .consumers import validate_binding, unknown_consumer_findings
from .vector import validate_claim, staleness_findings
from .corpus import validate_fixture, corpus_sufficiency
from .migration import validate_edge
from .plan import validate_plan
from .deprecation import (validate_notice, validate_support_window,
                          removal_findings)
from .negotiation import pinning_findings, validate_adapter, validate_bridge
from .intent import validate_intent
from .fitness import fitness_findings
from .envelope import validate_envelope


def validate_all(program: dict) -> Report:
    rep = Report()

    for d in program.get("descriptors", []):
        rep.extend(validate_descriptor(d))
        rep.extend(unknown_consumer_findings(d, program.get("bindings", [])))
    for v in program.get("versions", []):
        rep.extend(validate_version(v))
    for b in program.get("bindings", []):
        rep.extend(validate_binding(b))
        rep.extend(pinning_findings(b))
    for c in program.get("claims", []):
        rep.extend(validate_claim(c))
        rep.extend(staleness_findings(c))
    for fx in program.get("fixtures", []):
        rep.extend(validate_fixture(fx))
    # corpus sufficiency per protected contract (STABLE C2+)
    for d in program.get("descriptors", []):
        if d.get("stability") == "STABLE" \
                and d.get("criticality") in ("C2", "C3", "C4") \
                and d.get("requires_corpus", True):
            rep.extend(corpus_sufficiency(program.get("fixtures", []),
                                          contract_id=d.get("contract_id")))
    for e in program.get("migration_edges", []):
        rep.extend(validate_edge(e))
    for p in program.get("migration_plans", []):
        rep.extend(validate_plan(p))
    for n in program.get("deprecations", []):
        rep.extend(validate_notice(n))
        rep.extend(removal_findings(n, program.get("bindings", [])))
    for w in program.get("support_windows", []):
        rep.extend(validate_support_window(w))
    for a in program.get("adapters", []):
        rep.extend(validate_adapter(a))
    for br in program.get("bridges", []):
        rep.extend(validate_bridge(br))
    for ci in program.get("change_intents", []):
        rep.extend(validate_intent(ci))
    for env in program.get("proof_envelopes", []):
        rep.extend(validate_envelope(env))
    # the nine compatibility fitness functions run over the whole program
    rep.extend(fitness_findings(program))

    rep.metrics.update({
        "descriptors": len(program.get("descriptors", [])),
        "versions": len(program.get("versions", [])),
        "bindings": len(program.get("bindings", [])),
        "claims": len(program.get("claims", [])),
        "fixtures": len(program.get("fixtures", [])),
        "migration_edges": len(program.get("migration_edges", [])),
        "migration_plans": len(program.get("migration_plans", [])),
        "deprecations": len(program.get("deprecations", [])),
        "adapters": len(program.get("adapters", [])),
        "bridges": len(program.get("bridges", [])),
        "change_intents": len(program.get("change_intents", [])),
    })
    return rep
