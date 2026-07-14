"""Append-only test execution ledger and rerun accounting (SP0009 FUNCTION E,
§10.6, D-0009-18/19, AC-0009-093..099).

Every attempt is an immutable record. A passing rerun links to the failed
attempt it re-ran (rerun_of) but never erases, replaces or reinterprets it: the
original failure remains a first-class fact of the candidate's history. A rerun
pass proves only that the second attempt passed — never that the first failure
"was flaky" (flake classification needs controlled evidence, flakes.py) and
never product correctness. TIMEOUT and ENVIRONMENT_INVALID stay distinct from
FAIL so environmental noise cannot masquerade as product truth (or vice versa).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import ATTEMPT_RESULTS, Finding, P0


class ExecutionLedger:
    """Append-only test attempt ledger. No update, no delete."""

    def __init__(self) -> None:
        self._attempts: list[dict] = []

    def record(self, *, candidate_genome: str, test_id: str, result: str,
               environment_fingerprint: str, failure_signature=None,
               duration_ms=None, rerun_of=None) -> dict:
        if result not in ATTEMPT_RESULTS:
            raise ValueError(f"unknown attempt result {result!r}")
        if rerun_of is not None and not any(
                a["attempt_id"] == rerun_of for a in self._attempts):
            raise ValueError(f"rerun_of references unknown attempt {rerun_of}")
        prior = [a for a in self._attempts
                 if a["test_id"] == test_id
                 and a["candidate_genome"] == candidate_genome]
        rec = {
            "candidate_genome": candidate_genome,
            "test_id": test_id,
            "attempt_number": len(prior) + 1,
            "result": result,
            "environment_fingerprint": environment_fingerprint,
            "failure_signature": failure_signature,
            "duration_ms": duration_ms,
            "rerun_of": rerun_of,
        }
        rec["attempt_id"] = "TA-" + hash_obj(rec)[:20]
        self._attempts.append(rec)
        return rec

    def attempts(self, test_id=None, candidate_genome=None) -> list:
        out = list(self._attempts)
        if test_id is not None:
            out = [a for a in out if a["test_id"] == test_id]
        if candidate_genome is not None:
            out = [a for a in out
                   if a["candidate_genome"] == candidate_genome]
        return out

    def failures(self, test_id=None) -> list:
        """Every FAIL/TIMEOUT ever recorded — permanent regardless of reruns."""
        return [a for a in self.attempts(test_id)
                if a["result"] in ("FAIL", "TIMEOUT")]

    def effective_state(self, test_id: str, candidate_genome: str) -> dict:
        """The honest per-test summary: latest result AND full failure history.
        `ever_failed` never becomes False because of a later pass."""
        atts = self.attempts(test_id, candidate_genome)
        fails = [a for a in atts if a["result"] in ("FAIL", "TIMEOUT")]
        return {
            "test_id": test_id,
            "attempt_count": len(atts),
            "latest_result": atts[-1]["result"] if atts else None,
            "ever_failed": bool(fails),
            "failure_attempts": [a["attempt_id"] for a in fails],
            "rerun_passed_after_failure": bool(
                fails and atts and atts[-1]["result"] == "PASS"),
        }

    def ledger_hash(self) -> str:
        return hash_obj(self._attempts)


def rerun_accounting(ledger: ExecutionLedger, candidate_genome: str) -> dict:
    """The Rerun Accounting Ledger: how many attempts were reruns, how many
    failures were later followed by passes — all visible, none erased."""
    atts = ledger.attempts(candidate_genome=candidate_genome)
    reruns = [a for a in atts if a.get("rerun_of")]
    by_test: dict = {}
    for a in atts:
        by_test.setdefault(a["test_id"], []).append(a)
    laundering_candidates = [
        t for t, seq in sorted(by_test.items())
        if any(x["result"] in ("FAIL", "TIMEOUT") for x in seq)
        and seq[-1]["result"] == "PASS"]
    return {
        "total_attempts": len(atts),
        "reruns": len(reruns),
        "tests_with_failure_then_pass": laundering_candidates,
        "note": "a pass after failure is NOT proof of flakiness and does not "
                "erase the failure (D-0009-18/19)",
    }


def anti_laundering_findings(ledger: ExecutionLedger,
                             reported_failures: list,
                             candidate_genome: str) -> list:
    """If a report claims fewer failures than the ledger recorded, that is
    rerun laundering — a P0 proof-integrity violation."""
    actual = {a["attempt_id"] for a in ledger.failures()}
    reported = set(reported_failures)
    hidden = actual - reported
    out = []
    for aid in sorted(hidden):
        out.append(Finding(
            "TEST_FAILURE_RECORDED", P0, aid,
            "recorded failure missing from the reported failure set: a rerun "
            "or summary erased a failure (rerun laundering, INV-0009-10)",
            {"candidate_genome": candidate_genome}))
    return out
