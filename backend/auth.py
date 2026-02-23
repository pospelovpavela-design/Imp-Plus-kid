"""
Simple single-user auth.
Uses HMAC-SHA256 signed tokens — no external crypto library needed.
Format: base64url(payload_json).base64url(hmac_sha256_signature)
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, Security, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_EXPIRY_SECONDS = 30 * 24 * 3600  # 30 days

security = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    s = os.environ.get("SESSION_SECRET", "")
    if not s:
        raise RuntimeError("SESSION_SECRET is not set in .env")
    return s.encode()


def _password() -> str:
    p = os.environ.get("IMP_PASSWORD", "")
    if not p:
        raise RuntimeError("IMP_PASSWORD is not set in .env")
    return p


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token() -> str:
    payload = json.dumps({
        "sub": "mind",
        "iat": int(time.time()),
        "exp": int(time.time()) + _EXPIRY_SECONDS,
    }).encode()
    payload_b64 = _b64_encode(payload)
    sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def verify_password(password: str) -> bool:
    return password == _password()


def _decode_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("bad format")
        payload_b64, sig_b64 = parts
        expected_sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
        given_sig = _b64_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, given_sig):
            raise ValueError("invalid signature")
        payload = json.loads(_b64_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Токен истёк")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Недействительный токен")


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    token: str | None = Query(default=None),   # for SSE (EventSource can't set headers)
) -> dict:
    raw = None
    if credentials:
        raw = credentials.credentials
    elif token:
        raw = token
    if not raw:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    return _decode_token(raw)
