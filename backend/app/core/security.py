import hashlib
import hmac
import secrets
import time
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.db import utcnow


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _token(sub: str, kind: str, delta: timedelta, extra: dict | None = None) -> str:
    s = get_settings()
    now = utcnow()
    payload = {"sub": sub, "type": kind, "iat": now, "exp": now + delta, **(extra or {})}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: int, extra: dict | None = None) -> str:
    return _token(str(user_id), "access", timedelta(minutes=get_settings().access_token_minutes), extra)


def create_refresh_token(user_id: int) -> str:
    return _token(str(user_id), "refresh", timedelta(days=get_settings().refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return hashlib.sha256((get_settings().jwt_secret + otp).encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_hex(16)


# --- Rotating QR (anti-cheat): HMAC of branch secret + time window ---
def rotating_qr_token(secret: str, at: float | None = None) -> str:
    window = int((at or time.time()) // get_settings().rotating_qr_window_seconds)
    return hmac.new(secret.encode(), str(window).encode(), hashlib.sha256).hexdigest()[:12]


def verify_rotating_qr_token(secret: str, token: str) -> bool:
    now = time.time()
    w = get_settings().rotating_qr_window_seconds
    # accept current and previous window to tolerate scan delay
    return any(hmac.compare_digest(rotating_qr_token(secret, now - i * w), token) for i in (0, 1))
