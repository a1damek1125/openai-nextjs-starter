"""Sync decision logic — every external CRM read/write is policy-gated,
tenant-scoped, consent-aware, idempotent, and secret-free in its events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..governance.runtime import redact
from .models import (ConflictResolutionDecision, ExternalFieldMapping,
                     ExternalSyncEvent, ExternalSyncPolicy)

SYNC_DECISIONS = {"IMPORT_ALLOWED", "EXPORT_ALLOWED", "DRY_RUN_ONLY",
                  "CONFLICT_REQUIRES_REVIEW", "SKIP_NO_CHANGE",
                  "DENY_PERMISSION", "DENY_TENANT_MISMATCH",
                  "DENY_CONSENT", "DENY_FIELD_POLICY", "DENY_RATE_LIMIT"}

MARKETING_FIELDS = {"marketing_opt_in", "newsletter", "campaign_tags"}


@dataclass
class SyncRequest:
    tenant_id: str
    policy_tenant_id: str
    direction: str                      # import|export
    actor_id: Optional[str] = None
    actor_has_permission: bool = False
    field: str = ""
    internal_value: Optional[str] = None
    internal_verified: bool = False
    internal_changed: bool = False
    external_value: Optional[str] = None
    external_changed: bool = False
    marketing_consent_denied: bool = False
    rate_limited: bool = False
    is_deletion: bool = False


@dataclass
class SyncDecision:
    decision: str
    reasons: list[str] = field(default_factory=list)
    conflict: Optional[ConflictResolutionDecision] = None


def sync_decision(req: SyncRequest,
                  policy: ExternalSyncPolicy) -> SyncDecision:
    # Hard boundaries first — nothing overrides these.
    if req.tenant_id != req.policy_tenant_id \
            or req.tenant_id != policy.tenant_id:
        return SyncDecision("DENY_TENANT_MISMATCH",
                            ["sync policy belongs to another tenant"])
    if req.direction == "export" and (not req.actor_id
                                      or not req.actor_has_permission):
        return SyncDecision("DENY_PERMISSION",
                            ["external CRM writes need an actor with "
                             "permission"])
    if req.rate_limited:
        return SyncDecision("DENY_RATE_LIMIT",
                            ["provider rate limit reached — retry later"])
    if req.field in MARKETING_FIELDS and (req.marketing_consent_denied
                                          or not policy
                                          .sync_marketing_fields):
        return SyncDecision("DENY_CONSENT",
                            ["marketing data does not sync against "
                             "consent/policy"])
    if req.is_deletion:
        return SyncDecision("CONFLICT_REQUIRES_REVIEW",
                            ["deletions never propagate silently"])
    mapping = next((m for m in policy.field_mappings
                    if m.canonical_field == req.field), None)
    if req.field and mapping is None:
        return SyncDecision("DENY_FIELD_POLICY",
                            [f"field '{req.field}' has no sync mapping"])
    if mapping and mapping.sync_direction == "none":
        return SyncDecision("DENY_FIELD_POLICY",
                            [f"field '{req.field}' is not syncable"])
    if req.internal_value == req.external_value:
        return SyncDecision("SKIP_NO_CHANGE", ["values already match"])
    # Weaker external data never overwrites verified internal data.
    if req.direction == "import" and req.internal_verified:
        return SyncDecision(
            "CONFLICT_REQUIRES_REVIEW",
            ["internal value is human-verified — external data cannot "
             "overwrite it without review"],
            ConflictResolutionDecision(
                field=req.field, internal_value=str(req.internal_value),
                external_value=str(req.external_value),
                resolution="review"))
    if req.internal_changed and req.external_changed:
        return SyncDecision(
            "CONFLICT_REQUIRES_REVIEW",
            ["both sides changed since the last sync"],
            ConflictResolutionDecision(
                field=req.field, internal_value=str(req.internal_value),
                external_value=str(req.external_value),
                resolution="review"))
    if not policy.enabled or policy.dry_run:
        return SyncDecision("DRY_RUN_ONLY",
                            ["policy is disabled or in dry-run — nothing "
                             "written"])
    if req.direction == "import":
        if not policy.allow_import:
            return SyncDecision("DENY_FIELD_POLICY",
                                ["imports disabled by policy"])
        return SyncDecision("IMPORT_ALLOWED", ["import within policy"])
    if not policy.allow_export:
        return SyncDecision("DENY_FIELD_POLICY",
                            ["exports disabled by policy"])
    return SyncDecision("EXPORT_ALLOWED", ["export within policy"])


def record_sync_event(*, tenant_id: str, provider: str, direction: str,
                      object_kind: str, decision: SyncDecision,
                      detail: Optional[dict[str, Any]] = None,
                      idempotency_key: Optional[str] = None,
                      audit=None) -> ExternalSyncEvent:
    """Secrets never enter sync events — every string value is passed
    through the governance redactor."""
    safe_detail = {k: redact(str(v)) for k, v in (detail or {}).items()}
    event = ExternalSyncEvent(tenant_id=tenant_id, provider=provider,
                              direction=direction, object_kind=object_kind,
                              decision=decision.decision,
                              detail=safe_detail,
                              idempotency_key=idempotency_key)
    if audit is not None:
        audit.append(event_type="CRM_SYNC_EVENT", actor=provider,
                     payload={"direction": direction,
                              "object_kind": object_kind,
                              "decision": decision.decision,
                              "detail": safe_detail})
    return event
