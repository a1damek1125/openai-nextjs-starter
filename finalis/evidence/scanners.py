"""Scanner / CDR verdict lattices + risk contribution (V-E, Gap 4).

Provider INTERFACES only — the mock scanner is honestly labeled and can
never certify production safety; a real ClamAV/YARA/CDR provider slots
in behind the same shape later. No data leaves Finalis; nothing external
is called.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .policy import SCANNER_POLICY_VERSION

# --- verdict lattices (ordered severity, lowest → highest) --------------------
SCAN_VERDICTS = ["UNKNOWN", "NOT_RUN", "MOCKED_CLEAN", "CLEAN",
                 "SUSPICIOUS", "MALWARE_SUSPECTED", "FAILED", "UNSUPPORTED"]
CDR_VERDICTS = ["NOT_APPLICABLE", "NOT_RUN", "PLACEHOLDER_ONLY",
                "CDR_CLEANED", "CDR_FAILED", "CDR_REQUIRED", "UNSUPPORTED"]


def scan_rank(v: str) -> int:
    return SCAN_VERDICTS.index(v) if v in SCAN_VERDICTS else 0


@dataclass
class ScanVerdict:
    verdict: str = "NOT_RUN"
    is_mock: bool = True
    provider: str = "scanner-mock"
    policy_version: str = SCANNER_POLICY_VERSION
    detail: str = ""
    certifies_production_safety: bool = False   # a mock NEVER certifies


@dataclass
class CdrVerdict:
    verdict: str = "NOT_RUN"
    is_mock: bool = True
    provider: str = "cdr-scaffold"
    status: str = "SCAFFOLDED_ONLY"
    detail: str = ""


class EvidenceScannerProvider(Protocol):
    name: str
    is_mock: bool

    def scan(self, data: bytes, *, active_content: bool) -> ScanVerdict: ...


class EvidenceCdrProvider(Protocol):
    name: str
    is_mock: bool

    def disarm(self, data: bytes) -> CdrVerdict: ...


# EICAR-style deterministic marker — a real AV replaces this.
MOCK_MALWARE_MARKER = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$"


class MockScannerProvider:
    """MOCKED_AND_TESTED — deterministic verdict, not production antivirus."""
    name = "scanner-mock"
    is_mock = True

    def scan(self, data: bytes, *, active_content: bool = False
             ) -> ScanVerdict:
        if MOCK_MALWARE_MARKER in data:
            return ScanVerdict(verdict="MALWARE_SUSPECTED",
                               detail="mock marker matched")
        return ScanVerdict(verdict="MOCKED_CLEAN",
                           detail="mock scan — cannot certify production "
                                  "safety")


class ScaffoldCdrProvider:
    """SCAFFOLDED_ONLY — declares CDR need; never actually disarms."""
    name = "cdr-scaffold"
    is_mock = True

    def disarm(self, data: bytes) -> CdrVerdict:
        return CdrVerdict(verdict="CDR_REQUIRED",
                          detail="content-disarm not implemented — a real "
                                 "CDR provider is required")


# --- risk contribution (feeds FileRiskScore; hard blockers still win) ---------
def scanner_risk_contribution(verdict: str, *, scanner_required: bool = True,
                              active_content: bool = False) -> float:
    if verdict == "MALWARE_SUSPECTED":
        return 1.00
    if verdict == "FAILED" and scanner_required:
        return 0.85
    if verdict == "UNSUPPORTED" and active_content:
        return 0.70
    if verdict == "NOT_RUN" and active_content:
        return 0.55
    if verdict == "MOCKED_CLEAN":
        return 0.35
    if verdict == "CLEAN":
        return 0.10
    if verdict in ("NOT_APPLICABLE",):
        return 0.00
    return 0.20                     # UNKNOWN / other → mild uncertainty


# --- file treatment decision (combines scan + CDR + active content) -----------
FILE_TREATMENT_DECISIONS = {"ADMIT_CANDIDATE", "REQUIRE_CDR_OR_DERIVATIVE",
                            "REQUIRE_HUMAN_REVIEW", "BLOCK"}


@dataclass
class FileTreatmentDecision:
    decision: str
    reasons: list
    scan: ScanVerdict
    cdr: Optional[CdrVerdict] = None


def decide_file_treatment(*, scan: ScanVerdict, active_content: bool,
                          cdr: Optional[CdrVerdict] = None,
                          scanner_required: bool = True
                          ) -> FileTreatmentDecision:
    if scan.verdict == "MALWARE_SUSPECTED":
        return FileTreatmentDecision(
            "BLOCK", ["malware suspected — file rejected"], scan, cdr)
    if scan.verdict == "FAILED" and scanner_required:
        return FileTreatmentDecision(
            "BLOCK", ["required scan failed — admissibility blocked"],
            scan, cdr)
    if active_content:
        if cdr is None or cdr.verdict in ("NOT_RUN", "CDR_REQUIRED",
                                          "PLACEHOLDER_ONLY"):
            return FileTreatmentDecision(
                "REQUIRE_CDR_OR_DERIVATIVE",
                ["active content needs content-disarm or a safe "
                 "derivative or human review before agent use"], scan, cdr)
        if cdr.verdict == "CDR_FAILED":
            return FileTreatmentDecision(
                "REQUIRE_HUMAN_REVIEW",
                ["content-disarm failed — human review required"],
                scan, cdr)
    if scan.verdict == "UNSUPPORTED":
        return FileTreatmentDecision(
            "REQUIRE_HUMAN_REVIEW",
            ["scanner does not support this file type"], scan, cdr)
    return FileTreatmentDecision(
        "ADMIT_CANDIDATE",
        ["passed mock scan (not production-certified)"], scan, cdr)
