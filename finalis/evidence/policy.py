"""Evidence policy versioning + drift detection (V-E, Gap 7).

Every deterministic decision (requirement profile, scanner, derivative,
retention, causal guard) is fingerprinted so a stored contract can later
be replayed and told whether the policy that produced it still holds.
Drift is informational — it never rewrites history.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

# Bump a sub-version when the corresponding policy's math/rules change.
REQUIREMENT_POLICY_VERSION = "req-v1"
SCANNER_POLICY_VERSION = "scan-v1"
DERIVATIVE_POLICY_VERSION = "deriv-v1"
RETENTION_POLICY_VERSION = "ret-v1"
CAUSAL_GUARD_POLICY_VERSION = "causal-v1"


@dataclass(frozen=True)
class EvidencePolicySnapshot:
    requirement_profiles: tuple
    scanner_policy_version: str = SCANNER_POLICY_VERSION
    derivative_policy_version: str = DERIVATIVE_POLICY_VERSION
    retention_policy_version: str = RETENTION_POLICY_VERSION
    causal_guard_policy_version: str = CAUSAL_GUARD_POLICY_VERSION
    requirement_policy_version: str = REQUIREMENT_POLICY_VERSION


def _current_profiles() -> tuple:
    from .requirements import REQUIREMENT_PROFILES
    return tuple(sorted(REQUIREMENT_PROFILES))


def current_snapshot() -> EvidencePolicySnapshot:
    return EvidencePolicySnapshot(requirement_profiles=_current_profiles())


def policy_fingerprint(snapshot: Optional[EvidencePolicySnapshot] = None
                       ) -> str:
    """SHA-256 over the sorted profile list + every sub-policy version."""
    s = snapshot or current_snapshot()
    body = json.dumps({
        "profiles": list(s.requirement_profiles),
        "scanner": s.scanner_policy_version,
        "derivative": s.derivative_policy_version,
        "retention": s.retention_policy_version,
        "causal": s.causal_guard_policy_version,
        "requirement": s.requirement_policy_version,
    }, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def current_policy_version() -> str:
    return policy_fingerprint()[:16]


@dataclass
class EvidencePolicyDriftReport:
    stored_version: str
    current_version: str
    drift: bool
    detail: str = ""

    @classmethod
    def compare(cls, stored_version: str,
                current: Optional[str] = None) -> "EvidencePolicyDriftReport":
        cur = current or current_policy_version()
        drift = bool(stored_version) and stored_version != cur
        return cls(stored_version=stored_version, current_version=cur,
                   drift=drift,
                   detail=("policy changed since this decision was "
                           "recorded — replay may differ" if drift
                           else "policy unchanged"))
