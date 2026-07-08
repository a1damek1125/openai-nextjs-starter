"""External CRM adapter CONTRACTS — no real provider in CRM-A.

HubSpot/Salesforce/Pipedrive/Zoho/Odoo/Suite/Espo/Twenty are optional,
replaceable adapter targets behind these interfaces. Finalis stays the
source of operational truth for case work; external references are
mappings, not core objects.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol

from .models import CANONICAL_CRM_OBJECTS, ExternalSyncPolicy


@dataclass
class CrmProviderCapabilities:
    provider: str
    supports_webhooks: bool = False
    supports_incremental_sync: bool = False
    supports_custom_fields: bool = False
    supports_idempotency: bool = False
    rate_limit_per_minute: int = 60


@dataclass
class CrmObjectMapping:
    provider: str
    canonical_kind: str                  # CANONICAL_CRM_OBJECTS
    external_kind: str                   # provider's object name

    def __post_init__(self) -> None:
        if self.canonical_kind not in CANONICAL_CRM_OBJECTS:
            raise ValueError(f"unknown canonical object "
                             f"{self.canonical_kind}")


@dataclass
class CrmConflictPolicy:
    default: str = "review"              # keep_internal|take_external|review
    per_field: dict[str, str] = field(default_factory=dict)


@dataclass
class CrmRateLimitState:
    provider: str
    remaining: int = 0
    reset_at: Optional[datetime] = None

    @property
    def throttled(self) -> bool:
        return self.remaining <= 0


@dataclass
class CrmWebhookEvent:
    provider: str
    tenant_id: str
    object_kind: str
    external_id: str
    change_kind: str                     # created|updated|deleted
    received_at: datetime = field(default_factory=datetime.utcnow)


def idempotency_key(*, tenant_id: str, provider: str, object_kind: str,
                    external_id: str, operation: str,
                    payload_fingerprint: str = "") -> str:
    """Deterministic — the same intended write always produces the same
    key, so retries can never double-write."""
    body = f"{tenant_id}|{provider}|{object_kind}|{external_id}|" \
           f"{operation}|{payload_fingerprint}"
    return hashlib.sha256(body.encode()).hexdigest()


class CrmIdempotencyKey:
    """Registry guard: a key is spendable exactly once."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def claim(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


class ExternalCrmAdapter(Protocol):
    """Contract every future provider adapter must satisfy."""
    provider: str
    is_mock: bool

    def capabilities(self) -> CrmProviderCapabilities: ...
    def fetch_changes(self, *, tenant_id: str,
                      cursor_token: str) -> list[dict]: ...
    def push_object(self, *, tenant_id: str, object_kind: str,
                    payload: dict, idempotency_key: str,
                    dry_run: bool) -> dict: ...


class NullCrmAdapter:
    """SCAFFOLDED_ONLY — proves the contract; talks to nothing. Every
    push honours dry_run and requires an idempotency key."""
    provider = "null-crm"
    is_mock = True

    def __init__(self) -> None:
        self.pushed: list[dict] = []
        self._keys = CrmIdempotencyKey()

    def capabilities(self) -> CrmProviderCapabilities:
        return CrmProviderCapabilities(provider=self.provider)

    def fetch_changes(self, *, tenant_id: str,
                      cursor_token: str = "") -> list[dict]:
        return []                        # nothing external exists

    def push_object(self, *, tenant_id: str, object_kind: str,
                    payload: dict, idempotency_key: str,
                    dry_run: bool = True) -> dict:
        if not idempotency_key:
            raise ValueError("external writes require an idempotency key")
        if dry_run:
            return {"dry_run": True, "would_write": object_kind,
                    "provider": self.provider, "is_mock": True}
        if not self._keys.claim(idempotency_key):
            return {"skipped": "duplicate idempotency key",
                    "is_mock": True}
        self.pushed.append({"tenant_id": tenant_id,
                            "object_kind": object_kind,
                            "payload": payload})
        return {"written": True, "is_mock": True}


def default_policy(tenant_id: str,
                   provider: str = "null-crm") -> ExternalSyncPolicy:
    """Conservative defaults: disabled, dry-run, import-only."""
    return ExternalSyncPolicy(tenant_id=tenant_id, provider=provider)
