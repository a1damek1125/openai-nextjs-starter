"""Bounded model checks over the release kernel's core invariants (SP0009
§20 property tests, D-0009-08/09/18/32).

Small exhaustive checks that must HOLD: the gate lattice is non-compensatory
and UNKNOWN-blocking over its full result alphabet; the candidate genome moves
on every material field; the attempt ledger is append-only; threshold quorum
never counts duplicate or same-domain signers as diversity. A violation is P0.
"""
from __future__ import annotations

from .model import Finding, P0, GATE_RESULTS
from .candidate import candidate_genome, GENOME_FIELDS
from . import gates as G
from .attempts import ExecutionLedger
from .trust import threshold_quorum, trust_root


def model_lattice_fail_closed() -> list[Finding]:
    """Exhaustive over the result alphabet: any non-PASS result on a required
    hard gate blocks; no combination of other passes compensates."""
    out = []
    hard_gate = "GATE_TENANT_ISOLATION"
    plan = {g: "NOT_APPLICABLE" for g in G.GATE_REGISTRY}
    plan[hard_gate] = "REQUIRED"
    plan["GATE_UNIT_TESTS"] = "REQUIRED"
    for bad in [r for r in GATE_RESULTS if r != "PASS"] + [None]:
        results = {hard_gate: bad, "GATE_UNIT_TESTS": "PASS"}
        v = G.hard_verdict(plan, results)
        if v["qualifiable"]:
            out.append(Finding(
                "RELEASE_PROOF_MISMATCH", P0, "MODEL/lattice",
                f"hard gate result {bad!r} did not block (fail-open)", {}))
    ok = G.hard_verdict(plan, {hard_gate: "PASS", "GATE_UNIT_TESTS": "PASS"})
    if not ok["qualifiable"]:
        out.append(Finding("RELEASE_PROOF_MISMATCH", P0, "MODEL/lattice",
                           "all-PASS plan did not qualify", {}))
    return out


def model_genome_sensitivity() -> list[Finding]:
    """Every material genome field moves the genome when changed."""
    out = []
    base = {f: f"v-{f}" for f in GENOME_FIELDS}
    g0 = candidate_genome(base)
    for f in GENOME_FIELDS:
        g1 = candidate_genome({**base, f: "CHANGED"})
        if g1 == g0:
            out.append(Finding(
                "CANDIDATE_GENOME_MISMATCH", P0, "MODEL/genome",
                f"material field {f} did not move the candidate genome", {}))
    if candidate_genome(dict(base)) != g0:
        out.append(Finding("CANDIDATE_GENOME_MISMATCH", P0, "MODEL/genome",
                           "genome not deterministic", {}))
    return out


def model_ledger_append_only() -> list[Finding]:
    """A failure followed by passes never disappears."""
    out = []
    led = ExecutionLedger()
    led.record(candidate_genome="g", test_id="t", result="FAIL",
               environment_fingerprint="e")
    for _ in range(3):
        led.record(candidate_genome="g", test_id="t", result="PASS",
                   environment_fingerprint="e")
    state = led.effective_state("t", "g")
    if not state["ever_failed"] or len(led.failures("t")) != 1:
        out.append(Finding("RELEASE_PROOF_MISMATCH", P0, "MODEL/ledger",
                           "failure was erased by passing reruns", {}))
    if state["attempt_count"] != 4:
        out.append(Finding("RELEASE_PROOF_MISMATCH", P0, "MODEL/ledger",
                           "ledger lost attempts", {}))
    return out


def model_quorum_diversity() -> list[Finding]:
    """Duplicate signers and same-domain multiplicity never create quorum."""
    out = []
    root_a = trust_root(trust_root_id="R1", version=1, trust_domain="dom-a",
                        threshold=2, authorized_signers=["s1", "s2"],
                        valid_from="2026-01-01", expires_at="2027-01-01")
    # same signer twice: threshold 2 must NOT be met
    q = threshold_quorum([{"signer": "s1"}, {"signer": "s1"}], [root_a],
                         now="2026-06-01")
    if q["quorum"]:
        out.append(Finding("TRUST_THRESHOLD_NOT_MET", P0, "MODEL/quorum",
                           "duplicate signer counted twice", {}))
    # two signers, one domain, min_trust_domains=2 must NOT be met
    q2 = threshold_quorum([{"signer": "s1"}, {"signer": "s2"}], [root_a],
                          now="2026-06-01", min_trust_domains=2)
    if q2["quorum"]:
        out.append(Finding("TRUST_THRESHOLD_NOT_MET", P0, "MODEL/quorum",
                           "same-domain signers counted as domain diversity",
                           {}))
    # two signers one domain with min_trust_domains=1: legitimate
    q3 = threshold_quorum([{"signer": "s1"}, {"signer": "s2"}], [root_a],
                          now="2026-06-01", min_trust_domains=1)
    if not q3["quorum"]:
        out.append(Finding("TRUST_THRESHOLD_NOT_MET", P0, "MODEL/quorum",
                           "legitimate threshold rejected", {}))
    return out


MODELS = (
    ("lattice_fail_closed", model_lattice_fail_closed),
    ("genome_sensitivity", model_genome_sensitivity),
    ("ledger_append_only", model_ledger_append_only),
    ("quorum_diversity", model_quorum_diversity),
)


def run_models() -> dict:
    results = {}
    findings = []
    for name, fn in MODELS:
        fs = fn()
        results[name] = "HOLD" if not fs else "VIOLATED"
        findings.extend(fs)
    return {"models": results, "findings": findings,
            "all_hold": all(v == "HOLD" for v in results.values())}
