"""Evidence Trust Fabric scores — clamped 0..1, spec weights.

Scores inform gates; they NEVER override hard blockers (tested): high
trust cannot admit malware, low risk cannot cross a tenant boundary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class EvidenceThresholds:
    max_auto_file_risk: float = 0.60      # above → human review
    min_decision_trust: float = 0.60
    limits_band_trust: float = 0.75       # below → ADMISSIBLE_WITH_LIMITS
    max_injection_for_raw_ai: float = 0.40
    access_anomaly_alert: float = 0.70
    max_size_mb: int = 25


def file_risk_score(*, file_type_risk: float, source_risk: float,
                    size_anomaly_risk: float, mime_mismatch_risk: float,
                    scanner_uncertainty: float, content_active_risk: float,
                    sensitivity_risk: float,
                    historical_source_risk: float) -> float:
    return _clamp(0.20 * _clamp(file_type_risk)
                  + 0.15 * _clamp(source_risk)
                  + 0.15 * _clamp(size_anomaly_risk)
                  + 0.15 * _clamp(mime_mismatch_risk)
                  + 0.10 * _clamp(scanner_uncertainty)
                  + 0.10 * _clamp(content_active_risk)
                  + 0.10 * _clamp(sensitivity_risk)
                  + 0.05 * _clamp(historical_source_risk))


def evidence_trust_score(*, source_identity_confidence: float,
                         file_integrity_confidence: float,
                         scan_confidence: float,
                         chain_of_custody_score: float, recency: float,
                         human_verification: float,
                         case_relevance: float) -> float:
    return _clamp(0.20 * _clamp(source_identity_confidence)
                  + 0.20 * _clamp(file_integrity_confidence)
                  + 0.15 * _clamp(scan_confidence)
                  + 0.15 * _clamp(chain_of_custody_score)
                  + 0.10 * _clamp(recency)
                  + 0.10 * _clamp(human_verification)
                  + 0.10 * _clamp(case_relevance))


def chain_of_custody_score(*, uploader_identity_known: float,
                           upload_token_valid: float,
                           tenant_case_scope_verified: float,
                           checksum_recorded: float,
                           storage_provider_integrity: float,
                           audit_completeness: float,
                           no_version_tampering: float,
                           access_history_clean: float) -> float:
    return _clamp(0.20 * _clamp(uploader_identity_known)
                  + 0.15 * _clamp(upload_token_valid)
                  + 0.15 * _clamp(tenant_case_scope_verified)
                  + 0.15 * _clamp(checksum_recorded)
                  + 0.10 * _clamp(storage_provider_integrity)
                  + 0.10 * _clamp(audit_completeness)
                  + 0.10 * _clamp(no_version_tampering)
                  + 0.05 * _clamp(access_history_clean))


def access_anomaly_score(*, sensitive_file_access: float,
                         bulk_download_signal: float,
                         cross_case_access_pattern: float,
                         unusual_time_access: float,
                         failed_access_attempts: float,
                         external_link_use: float,
                         new_device_or_session: float) -> float:
    return _clamp(0.25 * _clamp(sensitive_file_access)
                  + 0.20 * _clamp(bulk_download_signal)
                  + 0.15 * _clamp(cross_case_access_pattern)
                  + 0.15 * _clamp(unusual_time_access)
                  + 0.10 * _clamp(failed_access_attempts)
                  + 0.10 * _clamp(external_link_use)
                  + 0.05 * _clamp(new_device_or_session))


# --- prompt-injection detection ---------------------------------------------------
# Documents provide facts, never commands. These patterns mark content
# that tries to be a command; matched spans are SUPPRESSED from facts and
# raise injection risk (which blocks raw AI access at the gate).
INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"ignore (all|any|previous|prior|above)",
    r"disregard (the|all|previous)",
    r"you (are|must|should) (now |immediately )?(approve|send|mark|pay)",
    r"\b(approve|accept) (the |this )?(quote|offer|payment|invoice)\b",
    r"\bmark (as |the )?(paid|complete|completed|fulfilled|won)\b",
    r"\bsend (the |a )?(message|email|refund|money|payment)\b",
    r"\b(change|update|set) (the )?price\b",
    r"\b(system|assistant|developer)\s*:",
    r"\btool[_ ]?call\b", r"\bfunction[_ ]?call\b",
    r"\bexfiltrate|forward (all|the) (files|data)\b",
    r"\bbypass|override (the )?(polic|rule|gate|approval)",
)]


def scan_for_injection(text: str) -> tuple[float, list[str]]:
    """Returns (risk 0..1, matched pattern snippets)."""
    hits = []
    for pat in INJECTION_PATTERNS:
        m = pat.search(text or "")
        if m:
            hits.append(m.group(0))
    return _clamp(0.35 * len(hits)), hits
