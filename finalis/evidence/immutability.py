"""Local WORM / Object-Lock capability layer (V-E, Gap 5).

The local provider has NO native WORM — it says so. It can enforce a
SIMULATED retention policy (governance / compliance modes), honestly
labeled as not-native. A real MinIO/S3 Object Lock adapter replaces the
capability implementation later. Legal hold and retention both block
hard delete; compliance mode cannot be bypassed by an owner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .policy import RETENTION_POLICY_VERSION

OBJECT_LOCK_MODES = {"NONE", "SIMULATED_GOVERNANCE", "SIMULATED_COMPLIANCE",
                     "EXTERNAL_WORM_REQUIRED"}


@dataclass
class RetentionPolicy:
    tenant_id: str
    evidence_id: str
    mode: str = "NONE"                    # OBJECT_LOCK_MODES
    retention_until: Optional[datetime] = None
    native_worm: bool = False            # local storage: never native
    policy_version: str = RETENTION_POLICY_VERSION
    label: str = ("simulated retention — NOT native WORM/Object Lock "
                  "(local dev storage)")

    def __post_init__(self) -> None:
        if self.mode not in OBJECT_LOCK_MODES:
            raise ValueError(f"unknown object-lock mode {self.mode}")


@dataclass
class WORMCapabilityDecision:
    native_worm: bool
    simulated_modes: list
    note: str


def storage_worm_capability(provider_name: str) -> WORMCapabilityDecision:
    """Local provider: no native WORM; simulated modes available."""
    return WORMCapabilityDecision(
        native_worm=False,
        simulated_modes=["SIMULATED_GOVERNANCE", "SIMULATED_COMPLIANCE"],
        note=f"{provider_name} is local dev storage with NO native "
             "WORM/Object Lock; retention is simulated at the domain "
             "layer. Connect MinIO/S3 Object Lock for native immutability "
             "(BLOCKED_BY_EXTERNAL_PROVIDER).")


@dataclass
class RetentionProof:
    hard_delete_allowed: bool
    reasons: list = field(default_factory=list)
    mode: str = "NONE"


def hard_delete_allowed(*, legal_hold_active: bool,
                        policy: Optional[RetentionPolicy],
                        now: datetime,
                        compliance_override: bool = False,
                        actor_role: str = "operator") -> RetentionProof:
    """The decision algebra. Compliance mode cannot be bypassed by a
    normal owner; governance mode needs an explicit compliance override."""
    reasons = []
    mode = policy.mode if policy else "NONE"
    if legal_hold_active:
        return RetentionProof(False, ["legal hold active — hard delete "
                                      "blocked"], mode)
    if policy and policy.retention_until and now < policy.retention_until:
        if policy.mode == "SIMULATED_COMPLIANCE":
            return RetentionProof(
                False, [f"compliance retention until "
                        f"{policy.retention_until:%Y-%m-%d} cannot be "
                        "bypassed (even by owner)"], mode)
        if policy.mode == "SIMULATED_GOVERNANCE" and not compliance_override:
            return RetentionProof(
                False, ["governance retention active — requires an "
                        "explicit compliance override"], mode)
    if actor_role not in ("owner", "compliance_admin") \
            and not compliance_override:
        return RetentionProof(
            False, ["hard delete requires owner or compliance"], mode)
    return RetentionProof(True, ["no hold, retention satisfied"], mode)
