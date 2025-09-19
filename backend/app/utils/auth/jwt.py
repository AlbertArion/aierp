import os
import time
from typing import Any, Dict, Optional, List
import hmac
import hashlib
import base64
import json

# 说明：轻量JWT(HMAC-SHA256)实现，签发/校验与角色检查


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64urldecode(data: str) -> bytes:
    pad = 4 - (len(data) % 4)
    if pad and pad < 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data.encode())


def _sign(secret: str, header_payload: str) -> str:
    digest = hmac.new(secret.encode(), header_payload.encode(), hashlib.sha256).digest()
    return _b64url(digest)


def create_token(sub: str, roles: List[str], expire_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload: Dict[str, Any] = {"sub": sub, "roles": roles, "iat": now, "exp": now + expire_seconds}
    secret = os.getenv("JWT_SECRET", "dev-secret")
    header_b64 = _b64url(json.dumps(header, separators=(',', ':')).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(',', ':')).encode())
    sig = _sign(secret, f"{header_b64}.{payload_b64}")
    return f"{header_b64}.{payload_b64}.{sig}"


def verify_token(token: str) -> Dict[str, Any]:
    secret = os.getenv("JWT_SECRET", "dev-secret")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")
    header_b64, payload_b64, sig = parts
    expect = _sign(secret, f"{header_b64}.{payload_b64}")
    if not hmac.compare_digest(sig, expect):
        raise ValueError("invalid signature")
    payload = json.loads(_b64urldecode(payload_b64).decode())
    if int(time.time()) >= int(payload.get("exp", 0)):
        raise ValueError("token expired")
    return payload


def has_role(payload: Dict[str, Any], required: str) -> bool:
    roles = payload.get("roles", [])
    return required in roles


