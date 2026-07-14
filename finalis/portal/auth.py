"""Minimal real auth: PBKDF2 password hashing + HMAC-signed session tokens,
tenant context, RBAC roles. Dev-grade by design; SSO is a future interface
(see founder report). No external dependencies.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Optional

from .db import Database

SECRET = os.environ.get("FINALIS_SECRET", "dev-secret-change-me")
TOKEN_TTL_S = 12 * 3600
ROLES = {"owner", "manager", "operator", "viewer", "ai_worker"}


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return base64.b64encode(salt).decode() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, digest_hex = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                        salt, 100_000).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False


def _sign(payload: bytes) -> str:
    return hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()


def issue_token(*, user_id: str, tenant_id: str, role: str,
                now: Optional[float] = None) -> str:
    body = json.dumps({"uid": user_id, "tid": tenant_id, "role": role,
                       "exp": (now or time.time()) + TOKEN_TTL_S})
    payload = base64.urlsafe_b64encode(body.encode()).decode()
    return f"{payload}.{_sign(payload.encode())}"


def verify_token(token: str) -> Optional[dict]:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload.encode()), sig):
            return None
        body = json.loads(base64.urlsafe_b64decode(payload))
        if body["exp"] < time.time():
            return None
        return body
    except Exception:
        return None


class AuthService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_user(self, *, tenant_id: str, email: str, password: str,
                    role: str, display_name: str = "") -> str:
        if role not in ROLES:
            raise ValueError(f"unknown role {role}")
        uid = str(uuid.uuid4())
        self.db.insert("users", {"id": uid, "tenant_id": tenant_id,
                                 "email": email,
                                 "password_hash": hash_password(password),
                                 "role": role,
                                 "display_name": display_name})
        return uid

    def login(self, email: str, password: str) -> Optional[dict]:
        row = self.db.one("SELECT * FROM users WHERE email=?", email)
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        token = issue_token(user_id=row["id"], tenant_id=row["tenant_id"],
                            role=row["role"])
        return {"token": token, "user_id": row["id"],
                "tenant_id": row["tenant_id"], "role": row["role"],
                "display_name": row["display_name"]}
