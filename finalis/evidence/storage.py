"""Evidence storage — replaceable provider interface + local provider.

LocalEvidenceStorageProvider is the ONLY implementation in V-A (own-IP
rule: storage stays a swappable seam; MinIO/S3/WORM adapters are future
options, never the core). Keys are generated — the original filename is
metadata only and never touches a path. No public serving, no raw
download tokens: bytes come out only through get_bytes() behind gates.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional, Protocol

from dataclasses import dataclass

from .models import EvidenceStoragePointer


@dataclass
class StorageCapabilities:
    """What a backend can enforce natively. Missing capabilities are
    compensated at the domain layer (retention/legal-hold logic in the
    RetentionDecisionEngine) — honestly, not silently."""
    supports_versioning: bool = False
    supports_worm: bool = False
    supports_retention: bool = False
    supports_legal_hold: bool = False
    supports_content_hash_addressing: bool = False
    supports_encryption_at_rest: bool = False


class EvidenceStorageProvider(Protocol):
    name: str
    is_mock: bool

    def capabilities(self) -> StorageCapabilities: ...

    def put_bytes(self, *, tenant_id: str,
                  data: bytes) -> tuple[EvidenceStoragePointer, str]: ...
    def get_bytes(self, pointer: EvidenceStoragePointer) -> bytes: ...
    def exists(self, pointer: EvidenceStoragePointer) -> bool: ...
    def stat(self, pointer: EvidenceStoragePointer) -> Optional[dict]: ...
    def delete_soft(self, pointer: EvidenceStoragePointer) -> None: ...
    def delete_hard_if_allowed(self, pointer: EvidenceStoragePointer,
                               *, allowed: bool) -> bool: ...
    def verify_integrity(self, pointer: EvidenceStoragePointer,
                         expected_sha256: str) -> bool: ...


class LocalEvidenceStorageProvider:
    """Local filesystem vault under a dedicated directory (never a
    webroot). Content-addressed-ish: <tenant>/<uuid> — no user input in
    the path. Soft delete moves bytes into a .trash/ area (recoverable,
    auditable); hard delete requires an explicit allowed=True decision
    from the RetentionDecisionEngine."""
    name = "local-evidence-vault"
    is_mock = False        # real local storage — the MOCKS are scanners etc.

    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> StorageCapabilities:
        # Honest: a plain local directory enforces none of these natively
        # (hashes are recorded and verified by the fabric, retention and
        # legal hold by the domain engine). MinIO/S3 Object Lock adapters
        # can report worm/retention/legal_hold True later.
        return StorageCapabilities()

    def _path(self, pointer: EvidenceStoragePointer) -> Path:
        p = (self.base / pointer.key).resolve()
        if self.base.resolve() not in p.parents:
            raise ValueError("storage key escapes the vault")   # traversal
        return p

    def put_bytes(self, *, tenant_id: str,
                  data: bytes) -> tuple[EvidenceStoragePointer, str]:
        key = f"{tenant_id}/{uuid.uuid4().hex}"
        pointer = EvidenceStoragePointer(provider=self.name, key=key,
                                         is_mock=False)
        path = self._path(pointer)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return pointer, hashlib.sha256(data).hexdigest()

    def get_bytes(self, pointer: EvidenceStoragePointer) -> bytes:
        return self._path(pointer).read_bytes()

    def exists(self, pointer: EvidenceStoragePointer) -> bool:
        return self._path(pointer).exists()

    def stat(self, pointer: EvidenceStoragePointer) -> Optional[dict]:
        p = self._path(pointer)
        if not p.exists():
            return None
        return {"size_bytes": p.stat().st_size, "key": pointer.key}

    def delete_soft(self, pointer: EvidenceStoragePointer) -> None:
        p = self._path(pointer)
        if p.exists():
            trash = self.base / ".trash" / pointer.key
            trash.parent.mkdir(parents=True, exist_ok=True)
            p.rename(trash)

    def delete_hard_if_allowed(self, pointer: EvidenceStoragePointer,
                               *, allowed: bool) -> bool:
        if not allowed:
            return False
        for candidate in (self._path(pointer),
                          self.base / ".trash" / pointer.key):
            if candidate.exists():
                candidate.unlink()
        return True

    def verify_integrity(self, pointer: EvidenceStoragePointer,
                         expected_sha256: str) -> bool:
        p = self._path(pointer)
        if not p.exists():
            return False
        return hashlib.sha256(p.read_bytes()).hexdigest() \
            == expected_sha256
