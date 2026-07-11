"""Provider Conformance Harness + Golden Canonical Workloads + Differential
Testing (SP0004 D-0004-31..35, §11.8/§11.9/§11.10, INV-0004-10).

A Golden Canonical Workload describes Finalis INTENT (canonical input + required
contract properties), never a provider-native API request (D-0004-33,
AC-0004-064). Effectful workloads default to NO_EXTERNAL_EFFECT (AC-0004-065). A
DeterministicReferenceProvider lets conformance run offline with fault injection
(D-0004-31). Provider equivalence is NOT Boolean — CONTRACT_EQUIVALENT /
FUNCTIONALLY_ACCEPTABLE / PARTIALLY_SUBSTITUTABLE / NON_EQUIVALENT / UNKNOWN,
per capability (D-0004-35).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, SUBSTITUTABILITY, PROVIDER_CONFORMANCE_FAILURE,
                    INVALID_TDR)


def validate_workload(w: dict) -> list[Finding]:
    out: list[Finding] = []
    wid = w.get("workload_id", "-")
    if not w.get("provider_class"):
        out.append(Finding(INVALID_TDR, P1, wid, "workload missing provider_class",
                           {}))
    # provider-neutral: canonical_input must not carry a provider-native request
    ci = w.get("canonical_input", {})
    if isinstance(ci, dict) and (ci.get("provider_native") or ci.get("raw_request")
                                 or ci.get("endpoint")):
        out.append(Finding(INVALID_TDR, P1, wid,
                           "canonical workload contains a provider-native request "
                           "(must be provider-neutral, AC-0004-064)", {}))
    # any declared effect_mode other than NO_EXTERNAL_EFFECT is rejected,
    # regardless of the optional `effectful` flag (red-team F2, AC-0004-065)
    if w.get("effect_mode", "NO_EXTERNAL_EFFECT") != "NO_EXTERNAL_EFFECT":
        out.append(Finding(INVALID_TDR, P0, wid,
                           "canonical workload declares an external effect mode; "
                           "the corpus defaults to NO_EXTERNAL_EFFECT "
                           "(AC-0004-065)", {}))
    return out


class DeterministicReferenceProvider:
    """A stdlib-only, deterministic reference implementation of a capability
    contract for conformance/replay/fault-injection (D-0004-31). It produces the
    same output for the same canonical input and can inject named faults."""

    def __init__(self, provider_class: str, fault: str | None = None):
        self.provider_class = provider_class
        self.fault = fault
        self.name = f"reference::{provider_class}"

    def handle(self, workload: dict) -> dict:
        if self.fault:
            # deterministic fault injection
            return {"outcome": "FAILED" if self.fault != "UNKNOWN_OUTCOME"
                    else "UNKNOWN_OUTCOME", "error": self.fault,
                    "workload_id": workload.get("workload_id")}
        # deterministic canonical response derived from the input
        from .canon import sha256_hex, canonical_json
        digest = sha256_hex(canonical_json(workload.get("canonical_input", {})))
        return {"outcome": "SUCCESS", "workload_id": workload.get("workload_id"),
                "canonical_output_hash": digest,
                "properties": workload.get("required_properties", [])}


def run_conformance(provider, corpus: list[dict]) -> dict:
    """Run a provider adapter against the golden corpus. Returns per-workload
    results + PASS/FAIL/UNSUPPORTED_CAPABILITY (§11.8)."""
    results = []
    passed = failed = unsupported = 0
    for w in corpus:
        try:
            resp = provider.handle(w)
        except NotImplementedError:
            unsupported += 1
            results.append({"workload_id": w.get("workload_id"),
                            "result": "UNSUPPORTED_CAPABILITY"})
            continue
        ok = resp.get("outcome") in ("SUCCESS", "UNKNOWN_OUTCOME")
        # required properties must be present in the response
        req = set(w.get("required_properties", []))
        got = set(resp.get("properties", []))
        prop_ok = req.issubset(got) or resp.get("outcome") != "SUCCESS"
        verdict = "PASS" if (ok and prop_ok) else "FAIL"
        passed += verdict == "PASS"
        failed += verdict == "FAIL"
        results.append({"workload_id": w.get("workload_id"), "result": verdict,
                        "outcome": resp.get("outcome")})
    return {"provider": getattr(provider, "name", "?"),
            "passed": passed, "failed": failed, "unsupported": unsupported,
            "results": results,
            "verdict": "PASS" if failed == 0 else "FAIL"}


def differential(provider_a, provider_b, corpus: list[dict]) -> dict:
    """Compare two providers on the same canonical workloads (§11.9). Does NOT
    require byte-identical nondeterministic output; compares contract compliance
    and outcome class."""
    per = []
    agree = 0
    for w in corpus:
        ra = provider_a.handle(w)
        rb = provider_b.handle(w)
        same_outcome = ra.get("outcome") == rb.get("outcome")
        agree += same_outcome
        per.append({"workload_id": w.get("workload_id"),
                    "outcome_a": ra.get("outcome"), "outcome_b": rb.get("outcome"),
                    "agree": same_outcome})
    n = len(corpus) or 1
    return {"provider_a": getattr(provider_a, "name", "a"),
            "provider_b": getattr(provider_b, "name", "b"),
            "agreement": round(agree / n, 4), "workloads": n, "detail": per}


def substitutability(differential_result: dict, *, contract_deterministic: bool
                     ) -> str:
    """Map a differential result to a capability substitutability class (not
    Boolean, D-0004-35). All five classes are reachable: with no comparable
    workloads there is no evidence, so the honest answer is UNKNOWN (never a
    fabricated equivalence)."""
    if not differential_result.get("workloads"):
        return "UNKNOWN"
    agree = differential_result.get("agreement", 0.0)
    if agree >= 1.0:
        return "CONTRACT_EQUIVALENT" if contract_deterministic \
            else "FUNCTIONALLY_ACCEPTABLE"
    if agree >= 0.8:
        return "FUNCTIONALLY_ACCEPTABLE"
    if agree > 0.0:
        return "PARTIALLY_SUBSTITUTABLE"
    return "NON_EQUIVALENT"
